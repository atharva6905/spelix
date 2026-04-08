"""Video annotation — skeleton overlay, angle labels, rep counter (B-021).

Draws exercise-specific skeleton connections, angle labels at key joints,
and a cumulative rep counter on each video frame.

Requirements: FR-CVPL-19, FR-XPRT-01

All drawing functions are pure — they mutate the frame in-place but have
no side effects beyond pixel writes.  Designed for use via
``loop.run_in_executor`` in the ARQ worker.
"""

from __future__ import annotations

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Colours and style (per CLAUDE.md gotchas)
# ---------------------------------------------------------------------------

_SKELETON_COLOR = (0x88, 0xFF, 0x00)  # #00FF88 in BGR
_SKELETON_THICKNESS = 2
_LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
_LABEL_FONT_SCALE = 0.55  # approximate Arial 18px
_LABEL_COLOR = (255, 255, 255)  # white
_LABEL_OUTLINE_COLOR = (0, 0, 0)  # black
_LABEL_OUTLINE_THICKNESS = 1
_LABEL_THICKNESS = 1
_REP_FONT_SCALE = 0.75  # approximate Arial 24px bold
_REP_THICKNESS = 2
_REP_POSITION = (20, 40)  # top-left

# ---------------------------------------------------------------------------
# Landmark indices (MediaPipe BlazePose, left-side even indices per task spec)
# ---------------------------------------------------------------------------

_SHOULDER = 12
_ELBOW = 14
_WRIST = 16
_HIP = 24
_KNEE = 26
_ANKLE = 28

# ---------------------------------------------------------------------------
# Exercise-specific skeleton connections
# ---------------------------------------------------------------------------

# Squat / Deadlift: shoulders, hips, knees, ankles
_SQUAT_DL_CONNECTIONS: list[tuple[int, int]] = [
    (_SHOULDER, _HIP),
    (_HIP, _KNEE),
    (_KNEE, _ANKLE),
]

# Bench: shoulders, elbows, wrists, hips
_BENCH_CONNECTIONS: list[tuple[int, int]] = [
    (_SHOULDER, _ELBOW),
    (_ELBOW, _WRIST),
    (_SHOULDER, _HIP),
]

_CONNECTION_MAP: dict[str, list[tuple[int, int]]] = {
    "squat": _SQUAT_DL_CONNECTIONS,
    "deadlift": _SQUAT_DL_CONNECTIONS,
    "bench": _BENCH_CONNECTIONS,
}

# ---------------------------------------------------------------------------
# Exercise-specific angle label joints (3 per exercise)
# Each entry: (landmark_index, joint_name) — angle is read from angle_dict
# ---------------------------------------------------------------------------

_ANGLE_LABEL_JOINTS: dict[str, list[tuple[int, str]]] = {
    "squat": [
        (_HIP, "hip_angle"),
        (_KNEE, "knee_angle"),
        (_SHOULDER, "shoulder"),  # positional only — no angle series
    ],
    "deadlift": [
        (_HIP, "hip_angle"),
        (_KNEE, "knee_angle"),
        (_SHOULDER, "shoulder"),
    ],
    "bench": [
        (_ELBOW, "elbow_angle"),
        (_SHOULDER, "shoulder_angle"),
        (_WRIST, "wrist"),
    ],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _landmark_px(
    landmarks: np.ndarray,
    idx: int,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Convert normalised landmark to pixel coordinates."""
    x = int(landmarks[idx, 0] * width)
    y = int(landmarks[idx, 1] * height)
    return (x, y)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def draw_skeleton(
    frame: np.ndarray,
    landmarks: np.ndarray,
    exercise_type: str,
) -> None:
    """Draw exercise-specific skeleton connections on *frame* (in-place).

    Parameters
    ----------
    frame:
        BGR image (H, W, 3) uint8.
    landmarks:
        (33, 5) MediaPipe landmark array (normalised x, y, z, vis, pres).
    exercise_type:
        ``"squat"``, ``"bench"``, or ``"deadlift"``.
    """
    h, w = frame.shape[:2]
    connections = _CONNECTION_MAP.get(exercise_type.lower(), _SQUAT_DL_CONNECTIONS)

    for idx_a, idx_b in connections:
        pt_a = _landmark_px(landmarks, idx_a, w, h)
        pt_b = _landmark_px(landmarks, idx_b, w, h)
        cv2.line(frame, pt_a, pt_b, _SKELETON_COLOR, _SKELETON_THICKNESS)


def draw_angle_labels(
    frame: np.ndarray,
    landmarks: np.ndarray,
    exercise_type: str,
    angles: dict[str, float],
) -> None:
    """Draw angle labels at key joints on *frame* (in-place).

    Parameters
    ----------
    frame:
        BGR image (H, W, 3) uint8.
    landmarks:
        (33, 5) MediaPipe landmark array.
    exercise_type:
        ``"squat"``, ``"bench"``, or ``"deadlift"``.
    angles:
        Dict of joint_name -> angle (degrees) for this frame.
    """
    h, w = frame.shape[:2]
    label_joints = _ANGLE_LABEL_JOINTS.get(
        exercise_type.lower(), _ANGLE_LABEL_JOINTS["squat"]
    )

    for lm_idx, angle_key in label_joints:
        angle_val = angles.get(angle_key)
        if angle_val is None:
            continue

        pt = _landmark_px(landmarks, lm_idx, w, h)
        text = f"{int(angle_val)}"
        offset = (pt[0] + 8, pt[1] - 8)

        # Black outline
        cv2.putText(
            frame, text, offset, _LABEL_FONT, _LABEL_FONT_SCALE,
            _LABEL_OUTLINE_COLOR, _LABEL_THICKNESS + _LABEL_OUTLINE_THICKNESS,
            cv2.LINE_AA,
        )
        # White fill
        cv2.putText(
            frame, text, offset, _LABEL_FONT, _LABEL_FONT_SCALE,
            _LABEL_COLOR, _LABEL_THICKNESS, cv2.LINE_AA,
        )


def draw_rep_counter(
    frame: np.ndarray,
    completed_reps: int,
    total_reps: int,
) -> None:
    """Draw ``"Rep: N / M"`` counter at top-left of *frame* (in-place).

    Parameters
    ----------
    frame:
        BGR image (H, W, 3) uint8.
    completed_reps:
        Number of reps completed so far (cumulative).
    total_reps:
        Total reps detected.
    """
    text = f"Rep: {completed_reps} / {total_reps}"

    # Black outline
    cv2.putText(
        frame, text, _REP_POSITION, _LABEL_FONT, _REP_FONT_SCALE,
        _LABEL_OUTLINE_COLOR, _REP_THICKNESS + _LABEL_OUTLINE_THICKNESS,
        cv2.LINE_AA,
    )
    # White fill
    cv2.putText(
        frame, text, _REP_POSITION, _LABEL_FONT, _REP_FONT_SCALE,
        _LABEL_COLOR, _REP_THICKNESS, cv2.LINE_AA,
    )


def annotate_frame(
    frame: np.ndarray,
    landmarks: np.ndarray,
    exercise_type: str,
    angles: dict[str, float],
    completed_reps: int,
    total_reps: int,
) -> None:
    """Apply all annotations to a single frame (in-place).

    Combines skeleton, angle labels, and rep counter.
    """
    draw_skeleton(frame, landmarks, exercise_type)
    draw_angle_labels(frame, landmarks, exercise_type, angles)
    draw_rep_counter(frame, completed_reps, total_reps)
