"""Barbell detection and bar path tracking (B-020).

SRS requirements: FR-BDET-01 through FR-BDET-07.

All functions are pure — no DB access, no side effects beyond reading pixel
data.  Designed for use in the ARQ worker via loop.run_in_executor.
"""

from __future__ import annotations

import numpy as np
import cv2


# ---------------------------------------------------------------------------
# HoughCircles parameters (per task spec)
# ---------------------------------------------------------------------------
_DP = 1.2
_MIN_DIST = 50
_PARAM1 = 100
_PARAM2 = 30
_MIN_RADIUS = 10
_MAX_RADIUS = 100

# ---------------------------------------------------------------------------
# D-035 downscale constants — HoughCircles runs on a 480p-max-dim frame
# ---------------------------------------------------------------------------
# Scaled ~4× from 1080p defaults above. maxRadius bumped to 40 (not 25) so
# that the existing 640x480 / radius-40 unit fixture remains detectable after
# the 1.33× downscale to 480x360. Source-resolution plate sizes of up to
# ~160 px diameter (radius 40 after scaling) are still covered.
_DETECTION_MAX_DIM = 480
_MIN_DIST_480P = 12
_MIN_RADIUS_480P = 3
_MAX_RADIUS_480P = 40


def detect_barbell_in_frame(frame: np.ndarray) -> tuple[float, float] | None:
    """Detect the circular end of a barbell plate in *frame*.

    Strategy: downscale to 480 px (longest dim) → grayscale → GaussianBlur →
    HoughCircles. The downscale step (D-035) keeps per-frame cost under
    ~60 ms on 1080p input; centroid is scaled back to source coordinates
    before return so callers see the same coordinate space as today.

    Parameters
    ----------
    frame:
        BGR image as a uint8 NumPy array of shape (H, W, 3).

    Returns
    -------
    (centroid_x, centroid_y) in *source-frame* pixel coordinates, or None
    if no circle is detected. When multiple circles are found the one with
    the highest accumulator response (first HoughCircles result) is returned.
    """
    scaled, scale_factor = _downscale_for_detection(frame)
    gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=_DP,
        minDist=_MIN_DIST_480P,
        param1=_PARAM1,
        param2=_PARAM2,
        minRadius=_MIN_RADIUS_480P,
        maxRadius=_MAX_RADIUS_480P,
    )

    if circles is None:
        return None

    # circles shape: (1, N, 3) — x, y, radius
    circles = np.round(circles[0]).astype(int)
    x, y, _r = circles[0]
    return (float(x) * scale_factor, float(y) * scale_factor)


def track_barbell(
    frames: list[np.ndarray],
) -> list[tuple[float, float] | None]:
    """Apply barbell detection to every frame in *frames*.

    Parameters
    ----------
    frames:
        Ordered list of BGR images.

    Returns
    -------
    List of centroids (one per frame).  Entries are None where no barbell
    plate was detected.
    """
    return [detect_barbell_in_frame(f) for f in frames]


def track_barbell_from_video(
    video_path: str,
) -> list[tuple[float, float] | None]:
    """Streaming barbell detection — reads frames one at a time.

    Equivalent to `track_barbell(extract_frames(video_path))` but never
    holds more than a single frame in memory. Critical for 1080p clips
    on memory-constrained hosts (D-034).

    Parameters
    ----------
    video_path:
        Absolute path to an OpenCV-readable video file.

    Returns
    -------
    List of centroids (one per frame).  Entries are None where no barbell
    plate was detected.  Empty list if the video cannot be opened.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return []

    centroids: list[tuple[float, float] | None] = []
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            centroids.append(detect_barbell_in_frame(frame))
    finally:
        cap.release()

    return centroids


def compute_bar_path(
    centroids: list[tuple[float, float] | None],
    frame_width: int,
    frame_height: int,
) -> dict | None:
    """Compute bar path metrics from a centroid trajectory.

    Parameters
    ----------
    centroids:
        List of (x, y) pixel positions, or None for frames where detection
        failed.
    frame_width, frame_height:
        Frame dimensions used to normalise centroid coordinates.

    Returns
    -------
    None if >50% of frames have None centroid (unreliable trajectory).

    Otherwise a dict with:
    - ``"centroids"``: list of (x, y) tuples normalised to [0, 1]
    - ``"lateral_deviation_px"``: max absolute horizontal deviation from mean x
    - ``"vertical_range_px"``: max y − min y
    - ``"path_consistency"``: 1 − (std(x) / mean(x)), clamped to [0, 1]
    """
    if not centroids:
        return None

    none_count = sum(1 for c in centroids if c is None)
    if none_count / len(centroids) > 0.5:
        return None

    # ------------------------------------------------------------------
    # Linear interpolation of missing centroids
    # ------------------------------------------------------------------
    filled = _interpolate_centroids(centroids)

    xs = np.array([c[0] for c in filled], dtype=float)
    ys = np.array([c[1] for c in filled], dtype=float)

    mean_x = float(np.mean(xs))
    lateral_deviation_px = float(np.max(np.abs(xs - mean_x)))
    vertical_range_px = float(np.max(ys) - np.min(ys))

    std_x = float(np.std(xs))
    if mean_x == 0.0:
        path_consistency = 1.0
    else:
        path_consistency = float(np.clip(1.0 - std_x / mean_x, 0.0, 1.0))

    # Normalise coordinates to [0, 1]
    norm_centroids = [
        (float(x / frame_width), float(y / frame_height))
        for x, y in zip(xs, ys)
    ]

    return {
        "centroids": norm_centroids,
        "lateral_deviation_px": lateral_deviation_px,
        "vertical_range_px": vertical_range_px,
        "path_consistency": path_consistency,
    }


def compute_bar_path_from_landmarks(
    landmarks_per_frame: list[np.ndarray],
    exercise_type: str,
) -> dict | None:
    """Estimate bar path using wrist landmarks when direct detection fails.

    Uses the midpoint of MediaPipe landmarks 15 (left wrist) and 16 (right
    wrist) as a proxy for barbell position.  Applicable to all three
    supported exercise types (squat, bench, deadlift).

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 4) landmark arrays in normalised [0, 1] coordinates
        (x, y, z, visibility).
    exercise_type:
        ``"squat"``, ``"bench"``, or ``"deadlift"``.  Kept for future
        per-exercise landmark selection; current Phase 0 always uses wrists.

    Returns
    -------
    None if *landmarks_per_frame* is empty.

    Otherwise the same dict format as :func:`compute_bar_path` but with
    coordinates already normalised (frame_width = frame_height = 1 notionally).
    Lateral deviation and vertical range are expressed in normalised units
    (not pixel units) since landmark coordinates are normalised.
    """
    if not landmarks_per_frame:
        return None

    centroids: list[tuple[float, float]] = []
    for lm in landmarks_per_frame:
        # landmarks 15 = left wrist, 16 = right wrist
        lm_15 = lm[15]
        lm_16 = lm[16]
        mid_x = float((lm_15[0] + lm_16[0]) / 2.0)
        mid_y = float((lm_15[1] + lm_16[1]) / 2.0)
        centroids.append((mid_x, mid_y))

    xs = np.array([c[0] for c in centroids], dtype=float)
    ys = np.array([c[1] for c in centroids], dtype=float)

    mean_x = float(np.mean(xs))
    lateral_deviation_px = float(np.max(np.abs(xs - mean_x)))
    vertical_range_px = float(np.max(ys) - np.min(ys))

    std_x = float(np.std(xs))
    if mean_x == 0.0:
        path_consistency = 1.0
    else:
        path_consistency = float(np.clip(1.0 - std_x / mean_x, 0.0, 1.0))

    # Coordinates are already normalised to [0, 1] from MediaPipe
    norm_centroids = [(float(x), float(y)) for x, y in zip(xs, ys)]

    return {
        "centroids": norm_centroids,
        "lateral_deviation_px": lateral_deviation_px,
        "vertical_range_px": vertical_range_px,
        "path_consistency": path_consistency,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _interpolate_centroids(
    centroids: list[tuple[float, float] | None],
) -> list[tuple[float, float]]:
    """Linearly interpolate None entries between known centroid points.

    Boundary Nones (leading / trailing) are filled by copying the nearest
    known value.
    """
    n = len(centroids)
    filled: list[tuple[float, float] | None] = list(centroids)

    # Collect indices of known values
    known_indices = [i for i, c in enumerate(filled) if c is not None]

    if not known_indices:
        # Should not happen (caller already checked >50% are known), but guard
        return [(0.0, 0.0)] * n

    # Fill leading Nones
    first_known = known_indices[0]
    for i in range(first_known):
        filled[i] = filled[first_known]

    # Fill trailing Nones
    last_known = known_indices[-1]
    for i in range(last_known + 1, n):
        filled[i] = filled[last_known]

    # Interpolate interior Nones
    for k in range(len(known_indices) - 1):
        i0 = known_indices[k]
        i1 = known_indices[k + 1]
        if i1 - i0 <= 1:
            continue
        x0, y0 = filled[i0]  # type: ignore[misc]
        x1, y1 = filled[i1]  # type: ignore[misc]
        for j in range(i0 + 1, i1):
            t = (j - i0) / (i1 - i0)
            filled[j] = (x0 + t * (x1 - x0), y0 + t * (y1 - y0))

    # At this point all entries should be filled — cast away None
    return [c for c in filled if c is not None]  # type: ignore[return-value]


def _downscale_for_detection(
    frame: np.ndarray, max_dim: int = _DETECTION_MAX_DIM
) -> tuple[np.ndarray, float]:
    """Downscale *frame* so its longest side is <= *max_dim*.

    Returns
    -------
    (scaled_frame, scale_factor) where scale_factor is the multiplier to
    convert a pixel coordinate in the scaled frame back to the source frame.
    Returns (frame, 1.0) unchanged when the frame is already small enough.
    """
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return frame, 1.0
    scale = max_dim / longest
    scaled = cv2.resize(
        frame, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA
    )
    return scaled, 1.0 / scale
