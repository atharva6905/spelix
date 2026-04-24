"""
Quality gates for Phase 0 CV pipeline (FR-CVPL-03 through FR-CVPL-11).

All functions are pure — no side effects, no DB, no IO (except check_video_file
which shells out to ffprobe).
Landmark arrays: shape (33, 5) per frame — [x, y, z, visibility, presence].

MediaPipe gotcha: visibility/presence values may be pre-sigmoid logits
(outside [0, 1]).  Always apply sigmoid() before thresholding.
See GitHub #4411, #4462.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Body-visibility gate — landmark indices (shoulders, elbows, hips, knees)
_VISIBILITY_LANDMARK_INDICES: list[int] = [11, 12, 13, 14, 23, 24, 25, 26]

_BODY_VISIBILITY_THRESHOLD: float = 0.30

# Framing gate — fraction of total frame area
# Calibrated 2026-04-24 against commercial-gym fixtures (atharva-{squat,bench,deadlift}).
# Was 0.30 (lab fixtures, ~1.5 m camera distance). Real users at 3-4 m fill ~12-20 % of
# portrait frame. See ADR-QGATE-COMMERCIAL-GYM.
_FRAMING_MIN_FRACTION: float = 0.20
_FRAMING_MAX_FRACTION: float = 0.80
# Minimum number of post-sigmoid-visibility >= 0.5 landmarks needed to compute a
# meaningful bbox. Below this, the sample is dropped (mirrors check_body_visibility's
# NO_POSE skip pattern). Out of 33 BlazePose landmarks.
_MIN_VISIBLE_LANDMARKS_FOR_BBOX: int = 10

# Visibility threshold (post-sigmoid) for a landmark to count as "visible"
# when computing the bounding box for the framing gate.
_LANDMARK_VISIBLE_THRESHOLD: float = 0.50

# Column indices within a (33, 5) landmark array
_COL_X = 0
_COL_Y = 1
_COL_VISIBILITY = 3

# Video file gate — maximum duration in seconds (FR-UPLD-02)
_MAX_VIDEO_DURATION_S: float = 120.0

# single_person gate (FR-CVPL-06) — anchor-based identity-jump detection.
# See docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md
# and ADR-QGATE-COMMERCIAL-GYM. Replaces the prior "any large hip jump = multiple
# people" rule, which produced false positives on commercial-gym videos where
# MediaPipe re-acquires onto a clearly-visible bystander during tracking-loss
# events.
_HIP_LANDMARKS: list[int] = [23, 24]  # left hip, right hip (MediaPipe BlazePose)
_ANCHOR_FROM_FIRST_N_SAMPLES: int = 3
_OFF_ANCHOR_DISTANCE_FRAC: float = 0.25
_MAX_CONSECUTIVE_OFF_ANCHOR: int = 4
_MAX_OFF_ANCHOR_FRACTION: float = 0.30

# Resolution gate — minimum dimension in pixels (FR-CVPL-07)
_MIN_RESOLUTION_DIM: int = 720

# Lighting gate — mean brightness thresholds (FR-CVPL-08)
_LIGHTING_MIN_BRIGHTNESS: float = 60.0
_LIGHTING_MAX_BRIGHTNESS: float = 240.0

# Camera stability gate — optical flow magnitude threshold (FR-CVPL-09)
_STABILITY_FLOW_THRESHOLD: float = 3.0

# Frame sampling — replaces hardcoded [:5] and [:10] slicing (ADR-053)
_FRAMING_SAMPLE_COUNT: int = 30
_FRAMING_PERCENTILE: float = 90.0
_VISIBILITY_SAMPLE_COUNT: int = 20
_SINGLE_PERSON_SAMPLE_COUNT: int = 30

# Occlusion warning — per-exercise landmark map
_EXERCISE_LANDMARKS: dict[str, dict[int, str]] = {
    "squat": {
        23: "left hip",
        24: "right hip",
        25: "left knee",
        26: "right knee",
        27: "left ankle",
        28: "right ankle",
    },
    "deadlift": {
        23: "left hip",
        24: "right hip",
        25: "left knee",
        26: "right knee",
        27: "left ankle",
        28: "right ankle",
    },
    "bench": {
        11: "left shoulder",
        12: "right shoulder",
        13: "left elbow",
        14: "right elbow",
        15: "left wrist",
        16: "right wrist",
    },
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class GateCheckResult:
    """Result of a single quality-gate check."""

    passed: bool
    name: str
    level: str  # "error" | "warning"
    metric_value: float
    threshold: float
    user_message: str


@dataclass
class QualityGateResult:
    """Aggregated result of all quality-gate checks for one analysis."""

    passed: bool
    status: str  # "passed" | "rejected"
    checks: list[GateCheckResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def sigmoid(x: float) -> float:
    """Numerically stable logistic sigmoid: 1 / (1 + exp(-x))."""
    return 1.0 / (1.0 + math.exp(-float(x)))


def _is_no_pose_frame(frame: np.ndarray) -> bool:
    """Detect the NO_POSE zero-fill sentinel from pose extraction."""
    return bool(np.all(frame[:, :2] == 0.0))


def _sample_indices(total: int, max_samples: int) -> list[int]:
    """Return up to *max_samples* evenly-spaced indices from [0, total)."""
    if total <= max_samples:
        return list(range(total))
    return np.linspace(0, total - 1, max_samples, dtype=int).tolist()


# ---------------------------------------------------------------------------
# Gate P0-00: Video file validation (FFprobe) — FR-UPLD-14, FR-UPLD-02
# ---------------------------------------------------------------------------


def check_video_file(video_path: str) -> GateCheckResult:
    """Validate video file using FFprobe — check codec readability and duration.

    Gate P0-00: FR-UPLD-14 (corrupt/unsupported), FR-UPLD-02 (duration max 120s).

    Parameters
    ----------
    video_path:
        Absolute path to the video file.

    Returns
    -------
    GateCheckResult
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return GateCheckResult(
                passed=False,
                name="video_file_check",
                level="error",
                metric_value=0.0,
                threshold=0.0,
                user_message="Video file appears corrupt or unsupported. Please re-export and try again.",
            )

        duration = float(result.stdout.strip())
        if duration > _MAX_VIDEO_DURATION_S:
            return GateCheckResult(
                passed=False,
                name="video_duration",
                level="error",
                metric_value=duration,
                threshold=_MAX_VIDEO_DURATION_S,
                user_message=f"Video exceeds maximum duration of {int(_MAX_VIDEO_DURATION_S)} seconds.",
            )

        return GateCheckResult(
            passed=True,
            name="video_file_check",
            level="error",
            metric_value=duration,
            threshold=_MAX_VIDEO_DURATION_S,
            user_message="",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return GateCheckResult(
            passed=False,
            name="video_file_check",
            level="error",
            metric_value=0.0,
            threshold=0.0,
            user_message="Video file appears corrupt or unsupported. Please re-export and try again.",
        )


# ---------------------------------------------------------------------------
# Gate 1: Body Visibility
# ---------------------------------------------------------------------------

_BODY_VISIBILITY_REJECT_MSG: str = (
    "Your body is not clearly visible. Please ensure good lighting and that "
    "your full body (shoulders to feet) is in the camera frame."
)
_BODY_VISIBILITY_PASS_MSG: str = "Body visibility is sufficient."


def check_body_visibility(landmarks_per_frame: list[np.ndarray]) -> GateCheckResult:
    """Gate P0-01: body visibility.

    Samples up to 20 evenly-spaced frames, skips NO_POSE sentinels,
    rejects if mean sigmoid-visibility of key landmarks is below 0.30.
    """
    indices = _sample_indices(len(landmarks_per_frame), _VISIBILITY_SAMPLE_COUNT)

    vis_values: list[float] = []
    for i in indices:
        frame = landmarks_per_frame[i]
        if _is_no_pose_frame(frame):
            continue
        for idx in _VISIBILITY_LANDMARK_INDICES:
            raw_vis = float(frame[idx, _COL_VISIBILITY])
            vis_values.append(sigmoid(raw_vis))

    mean_vis = float(np.mean(vis_values)) if vis_values else 0.0
    passed = mean_vis >= _BODY_VISIBILITY_THRESHOLD

    return GateCheckResult(
        passed=passed,
        name="body_visibility",
        level="error",
        metric_value=mean_vis,
        threshold=_BODY_VISIBILITY_THRESHOLD,
        user_message=_BODY_VISIBILITY_PASS_MSG if passed else _BODY_VISIBILITY_REJECT_MSG,
    )


# ---------------------------------------------------------------------------
# Gate 2: Framing
# ---------------------------------------------------------------------------

_FRAMING_TOO_SMALL_MSG: str = (
    "You appear too far from the camera. Please move closer so your body "
    "fills at least 30% of the frame."
)
_FRAMING_TOO_LARGE_MSG: str = (
    "You are too close to the camera. Please step back so your full body "
    "is visible."
)
_FRAMING_PASS_MSG: str = "Framing is good."


def check_framing(
    landmarks_per_frame: list[np.ndarray],
    frame_width: int,
    frame_height: int,
) -> GateCheckResult:
    """Gate P0-02: subject framing (ADR-053, ADR-054, ADR-QGATE-COMMERCIAL-GYM).

    Samples up to 30 evenly-spaced frames, skips NO_POSE sentinels,
    computes bbox from landmarks with sigmoid(visibility) >= 0.5 only
    (hallucinated low-confidence landmarks cluster near body centre and
    under-report the lifter's true frame coverage). Skips samples with
    fewer than _MIN_VISIBLE_LANDMARKS_FOR_BBOX reliable landmarks.
    Checks 90th-percentile area fraction against [20 %, 80 %].
    """
    indices = _sample_indices(len(landmarks_per_frame), _FRAMING_SAMPLE_COUNT)

    fractions: list[float] = []
    for i in indices:
        frame = landmarks_per_frame[i]
        if _is_no_pose_frame(frame):
            continue

        # Visibility-gated bbox (ADR-QGATE-COMMERCIAL-GYM).
        # Hallucinated low-confidence landmarks cluster near body centre and
        # under-report the lifter's true frame coverage. Use only landmarks
        # with sigmoid(visibility) >= _LANDMARK_VISIBLE_THRESHOLD.
        visibilities = np.array(
            [sigmoid(float(v)) for v in frame[:, _COL_VISIBILITY]]
        )
        visible_mask = visibilities >= _LANDMARK_VISIBLE_THRESHOLD
        if int(visible_mask.sum()) < _MIN_VISIBLE_LANDMARKS_FOR_BBOX:
            continue

        xs = frame[visible_mask, _COL_X]
        ys = frame[visible_mask, _COL_Y]
        bbox_width = float(np.max(xs) - np.min(xs))
        bbox_height = float(np.max(ys) - np.min(ys))
        fractions.append(bbox_width * bbox_height)

    if not fractions:
        return GateCheckResult(
            passed=False,
            name="framing",
            level="error",
            metric_value=0.0,
            threshold=_FRAMING_MIN_FRACTION,
            user_message=_FRAMING_TOO_SMALL_MSG,
        )

    metric = float(np.percentile(fractions, _FRAMING_PERCENTILE))

    aspect = frame_width / frame_height if frame_height > 0 else 1.0
    min_threshold = (
        _FRAMING_MIN_FRACTION * aspect if aspect < 1.0 else _FRAMING_MIN_FRACTION
    )

    if metric < min_threshold:
        passed = False
        user_message = _FRAMING_TOO_SMALL_MSG
        threshold = min_threshold
    elif metric > _FRAMING_MAX_FRACTION:
        passed = False
        user_message = _FRAMING_TOO_LARGE_MSG
        threshold = _FRAMING_MAX_FRACTION
    else:
        passed = True
        user_message = _FRAMING_PASS_MSG
        threshold = min_threshold

    return GateCheckResult(
        passed=passed,
        name="framing",
        level="error",
        metric_value=metric,
        threshold=threshold,
        user_message=user_message,
    )


# ---------------------------------------------------------------------------
# Gate 3: Single person (FR-CVPL-06)
# ---------------------------------------------------------------------------


def check_single_person(
    landmarks_per_frame: list[np.ndarray],
    frame_width: int,
) -> GateCheckResult:
    """Reject when MediaPipe is tracking different people across the clip.

    Anchors on the lifter from the first 3 high-visibility samples (median hip
    midpoint x), then counts samples whose hip midpoint drifts >25 % of frame
    width from the anchor. Rejects if 4+ consecutive off-anchor samples or
    >=30 % of valid samples are off-anchor. Skips samples where either hip's
    post-sigmoid visibility is below ``_LANDMARK_VISIBLE_THRESHOLD`` — those
    are MediaPipe guesses on occluded frames and would otherwise dominate the
    decision (see ADR-QGATE-COMMERCIAL-GYM).

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame.
    frame_width:
        Frame width in pixels.

    Returns
    -------
    GateCheckResult
    """
    indices = _sample_indices(len(landmarks_per_frame), _SINGLE_PERSON_SAMPLE_COUNT)

    midpoints: list[float] = []
    for i in indices:
        frame = landmarks_per_frame[i]
        if _is_no_pose_frame(frame):
            continue
        left_vis = sigmoid(float(frame[_HIP_LANDMARKS[0], _COL_VISIBILITY]))
        right_vis = sigmoid(float(frame[_HIP_LANDMARKS[1], _COL_VISIBILITY]))
        if left_vis < _LANDMARK_VISIBLE_THRESHOLD or right_vis < _LANDMARK_VISIBLE_THRESHOLD:
            continue
        left_x = float(frame[_HIP_LANDMARKS[0], _COL_X])
        right_x = float(frame[_HIP_LANDMARKS[1], _COL_X])
        midpoints.append((left_x + right_x) / 2.0)

    # Need at least N samples to anchor reliably. Fewer = cannot distinguish
    # single-lifter-with-occlusion from genuinely-no-lifter.
    if len(midpoints) < _ANCHOR_FROM_FIRST_N_SAMPLES:
        return GateCheckResult(
            passed=False,
            name="single_person",
            level="error",
            metric_value=float(len(midpoints)),
            threshold=float(_ANCHOR_FROM_FIRST_N_SAMPLES),
            user_message=(
                "Could not consistently track a single lifter — try filming "
                "side-on with your full body in frame."
            ),
        )

    anchor = float(np.median(midpoints[:_ANCHOR_FROM_FIRST_N_SAMPLES]))

    off_anchor_flags = [
        abs(m - anchor) > _OFF_ANCHOR_DISTANCE_FRAC for m in midpoints
    ]

    # Longest consecutive run of off-anchor samples
    longest_run = 0
    current_run = 0
    for flag in off_anchor_flags:
        if flag:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0

    off_anchor_fraction = sum(off_anchor_flags) / len(off_anchor_flags)
    rejected_by_run = longest_run >= _MAX_CONSECUTIVE_OFF_ANCHOR
    rejected_by_fraction = off_anchor_fraction > _MAX_OFF_ANCHOR_FRACTION

    passed = not (rejected_by_run or rejected_by_fraction)

    # Report whichever metric drove the decision (or longest_run when passing
    # — gives the operator a sense of margin). Threshold reported is the run
    # threshold; the fraction threshold is informational and lives in the spec.
    return GateCheckResult(
        passed=passed,
        name="single_person",
        level="error",
        metric_value=float(longest_run),
        threshold=float(_MAX_CONSECUTIVE_OFF_ANCHOR),
        user_message=(
            ""
            if passed
            else (
                "Could not consistently track a single lifter — try filming "
                "side-on with your full body in frame."
            )
        ),
    )


# ---------------------------------------------------------------------------
# Gate 4: Minimum resolution (FR-CVPL-07)
# ---------------------------------------------------------------------------


def check_minimum_resolution(frame_width: int, frame_height: int) -> GateCheckResult:
    """Reject if video resolution is below 720p (min dimension < 720).

    Parameters
    ----------
    frame_width, frame_height:
        Pixel dimensions of the source video frame.

    Returns
    -------
    GateCheckResult
    """
    min_dim = min(frame_width, frame_height)
    passed = min_dim >= _MIN_RESOLUTION_DIM
    return GateCheckResult(
        passed=passed,
        name="resolution",
        level="error",
        metric_value=float(min_dim),
        threshold=float(_MIN_RESOLUTION_DIM),
        user_message="" if passed else "Video resolution too low — record at 720p or higher.",
    )


# ---------------------------------------------------------------------------
# Gate 5: Occlusion warnings (warning-level, non-rejecting)
# ---------------------------------------------------------------------------


def check_occlusion(
    landmarks_per_frame: list[np.ndarray],
    exercise_type: str,
) -> list[GateCheckResult]:
    """Check per-landmark visibility and generate warnings for occluded joints.

    This gate never rejects — it produces warning-level results only.

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame.
    exercise_type:
        ``"squat"``, ``"bench"``, or ``"deadlift"``.

    Returns
    -------
    list[GateCheckResult]
        Warning results for any occluded joints (may be empty).
    """
    lm_map = _EXERCISE_LANDMARKS.get(exercise_type, _EXERCISE_LANDMARKS["squat"])
    warnings: list[GateCheckResult] = []
    for lm_idx, joint_name in lm_map.items():
        visibilities = [sigmoid(float(frame[lm_idx, _COL_VISIBILITY])) for frame in landmarks_per_frame]
        mean_vis = float(np.mean(visibilities)) if visibilities else 0.0
        if mean_vis < _BODY_VISIBILITY_THRESHOLD:
            warnings.append(
                GateCheckResult(
                    passed=True,  # Warning only — does not reject
                    name=f"occlusion_{joint_name.replace(' ', '_')}",
                    level="warning",
                    metric_value=mean_vis,
                    threshold=_BODY_VISIBILITY_THRESHOLD,
                    user_message=(
                        f"{joint_name.title()} alignment could not be assessed"
                        " — barbell occluded keypoints."
                    ),
                )
            )
    return warnings


# ---------------------------------------------------------------------------
# Gate 6: Lighting warning (FR-CVPL-08)
# ---------------------------------------------------------------------------


def check_lighting(frames_gray: list[np.ndarray]) -> GateCheckResult:
    """Warn if mean brightness across first 10 grayscale frames is too low or too high.

    Parameters
    ----------
    frames_gray:
        List of 2-D uint8 grayscale frame arrays. Only first 10 used.

    Returns
    -------
    GateCheckResult
        Warning-level only — never rejects.
    """
    sample = frames_gray[:10]
    if not sample:
        return GateCheckResult(
            passed=True,
            name="lighting",
            level="warning",
            metric_value=0.0,
            threshold=_LIGHTING_MIN_BRIGHTNESS,
            user_message="",
        )

    import cv2

    brightness_values = [float(cv2.mean(f)[0]) for f in sample]
    mean_brightness = float(np.mean(brightness_values))

    if mean_brightness < _LIGHTING_MIN_BRIGHTNESS:
        return GateCheckResult(
            passed=True,  # Warning only — does not reject
            name="lighting",
            level="warning",
            metric_value=mean_brightness,
            threshold=_LIGHTING_MIN_BRIGHTNESS,
            user_message="Poor lighting detected — try filming in a brighter environment for better results.",
        )
    if mean_brightness > _LIGHTING_MAX_BRIGHTNESS:
        return GateCheckResult(
            passed=True,
            name="lighting",
            level="warning",
            metric_value=mean_brightness,
            threshold=_LIGHTING_MAX_BRIGHTNESS,
            user_message="Poor lighting detected — the scene appears overexposed. Reduce direct lighting.",
        )

    return GateCheckResult(
        passed=True,
        name="lighting",
        level="warning",
        metric_value=mean_brightness,
        threshold=_LIGHTING_MIN_BRIGHTNESS,
        user_message="",
    )


# ---------------------------------------------------------------------------
# Gate 7: Camera stability warning (FR-CVPL-09)
# ---------------------------------------------------------------------------


def check_camera_stability(frames_gray: list[np.ndarray]) -> GateCheckResult:
    """Warn if mean optical flow magnitude exceeds threshold, suggesting camera movement.

    Uses Farneback dense optical flow on up to 5 consecutive frame pairs.

    Parameters
    ----------
    frames_gray:
        List of 2-D uint8 grayscale frame arrays. Needs at least 2 frames.

    Returns
    -------
    GateCheckResult
        Warning-level only — never rejects.
    """
    if len(frames_gray) < 2:
        return GateCheckResult(
            passed=True,
            name="camera_stability",
            level="warning",
            metric_value=0.0,
            threshold=_STABILITY_FLOW_THRESHOLD,
            user_message="",
        )

    import cv2

    pairs = min(5, len(frames_gray) - 1)
    magnitudes: list[float] = []
    for i in range(pairs):
        flow = cv2.calcOpticalFlowFarneback(
            frames_gray[i],
            frames_gray[i + 1],
            None,  # type: ignore[arg-type]
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        magnitudes.append(float(np.mean(mag)))

    mean_flow = float(np.mean(magnitudes))

    if mean_flow > _STABILITY_FLOW_THRESHOLD:
        return GateCheckResult(
            passed=True,  # Warning only
            name="camera_stability",
            level="warning",
            metric_value=mean_flow,
            threshold=_STABILITY_FLOW_THRESHOLD,
            user_message="Camera appears to be moving — use a tripod or stable surface for better results.",
        )

    return GateCheckResult(
        passed=True,
        name="camera_stability",
        level="warning",
        metric_value=mean_flow,
        threshold=_STABILITY_FLOW_THRESHOLD,
        user_message="",
    )


# ---------------------------------------------------------------------------
# Combined runner
# ---------------------------------------------------------------------------


def run_quality_gates(
    landmarks_per_frame: list[np.ndarray],
    frame_width: int,
    frame_height: int,
    video_path: str | None = None,
    exercise_type: str = "squat",
    frames_gray: list[np.ndarray] | None = None,
) -> QualityGateResult:
    """
    Run all Phase 0 quality gates and return an aggregated result.

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame.
    frame_width, frame_height:
        Pixel dimensions of the source video frame.
    video_path:
        Optional path to the video file.  When provided, FFprobe-based
        file validation (duration + codec readability) runs first.
    exercise_type:
        Exercise type for occlusion warnings (``"squat"``, ``"bench"``,
        ``"deadlift"``).  Defaults to ``"squat"``.
    frames_gray:
        Optional list of 2-D uint8 grayscale frame arrays for lighting
        and camera stability gates (FR-CVPL-08, FR-CVPL-09).

    Returns
    -------
    QualityGateResult
        passed=True only if every gate with level="error" passed.
        status is "passed" or "rejected".
    """
    checks: list[GateCheckResult] = []

    # Optional: video file validation via FFprobe (runs first if path provided)
    if video_path is not None:
        file_check = check_video_file(video_path)
        checks.append(file_check)
        if not file_check.passed:
            # Fail fast — no point running landmark-based gates on a bad file
            return QualityGateResult(passed=False, status="rejected", checks=checks)

    # Resolution gate (uses frame dimensions, not landmarks)
    resolution_check = check_minimum_resolution(frame_width, frame_height)
    checks.append(resolution_check)

    # Landmark-based gates
    visibility_check = check_body_visibility(landmarks_per_frame)
    framing_check = check_framing(landmarks_per_frame, frame_width, frame_height)
    single_person_check = check_single_person(landmarks_per_frame, frame_width)

    checks.extend([visibility_check, framing_check, single_person_check])

    # Occlusion warnings (non-rejecting)
    occlusion_warnings = check_occlusion(landmarks_per_frame, exercise_type)
    checks.extend(occlusion_warnings)

    # Frame-based warning gates (FR-CVPL-08, FR-CVPL-09)
    if frames_gray is not None:
        checks.append(check_lighting(frames_gray))
        checks.append(check_camera_stability(frames_gray))

    # Overall pass only if no error-level gate failed
    overall_passed = all(c.passed for c in checks if c.level == "error")
    status = "passed" if overall_passed else "rejected"

    return QualityGateResult(
        passed=overall_passed,
        status=status,
        checks=checks,
    )
