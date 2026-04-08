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


def detect_barbell_in_frame(frame: np.ndarray) -> tuple[float, float] | None:
    """Detect the circular end of a barbell plate in *frame*.

    Strategy: grayscale → GaussianBlur → HoughCircles (HOUGH_GRADIENT).

    Parameters
    ----------
    frame:
        BGR image as a uint8 NumPy array of shape (H, W, 3).

    Returns
    -------
    (centroid_x, centroid_y) in pixel coordinates, or None if no circle is
    detected.  When multiple circles are found the one with the highest
    accumulator response (first HoughCircles result) is returned.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=_DP,
        minDist=_MIN_DIST,
        param1=_PARAM1,
        param2=_PARAM2,
        minRadius=_MIN_RADIUS,
        maxRadius=_MAX_RADIUS,
    )

    if circles is None:
        return None

    # circles shape: (1, N, 3) — x, y, radius
    circles = np.round(circles[0]).astype(int)
    # Return the first detected circle (highest accumulator score)
    x, y, _r = circles[0]
    return (float(x), float(y))


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
