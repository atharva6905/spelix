"""
Heuristic exercise-type detection from MediaPipe landmarks.

Requirements: FR-XDET-03, FR-XDET-04, FR-XDET-07

Phase 1: Analyze landmark geometry across sampled frames to classify
squat / bench / deadlift. If heuristic confidence < 0.7, falls back
to GPT-4o vision via KeyframeAnalysisService.

All functions are pure (no side effects, no DB, no IO).
Designed to be called via ``loop.run_in_executor`` for the heuristic,
and awaited directly for the GPT-4o fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

# MediaPipe BlazePose landmark indices
_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_HIP = 23
_RIGHT_HIP = 24
_LEFT_KNEE = 25
_RIGHT_KNEE = 26
_LEFT_ANKLE = 27
_RIGHT_ANKLE = 28
_LEFT_ELBOW = 13
_RIGHT_ELBOW = 14
_LEFT_WRIST = 15
_RIGHT_WRIST = 16

# Columns in (33, 5) landmark array
_X, _Y, _Z, _VIS, _PRES = 0, 1, 2, 3, 4

ExerciseTypeLiteral = Literal["squat", "bench", "deadlift"]


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """Exercise auto-detection result for FR-XDET-07 display."""

    detected_type: ExerciseTypeLiteral
    detected_variant: str
    confidence: float
    method: Literal["heuristic", "vision_fallback"]
    details: dict


def _midpoint(frame: np.ndarray, a: int, b: int, col: int) -> float:
    """Average of two landmarks along one axis."""
    return float((frame[a, col] + frame[b, col]) / 2.0)


def _mean_visibility(frame: np.ndarray, indices: list[int]) -> float:
    """Mean visibility of specified landmarks."""
    return float(np.mean([frame[i, _VIS] for i in indices]))


def _angle_3pts(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle at point b (in degrees) formed by points a-b-c in 2D (x,y)."""
    ba = a[:2] - b[:2]
    bc = c[:2] - b[:2]
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))


def _classify_single_frame(frame: np.ndarray) -> dict[str, float]:
    """Compute feature signals from one (33, 5) frame.

    Returns dict of signals used for classification:
    - torso_vertical: angle of torso from vertical (0 = upright, 90 = horizontal)
    - hip_angle: angle at hip (shoulder-hip-knee)
    - knee_angle: angle at knee (hip-knee-ankle)
    - elbow_angle: angle at elbow (shoulder-elbow-wrist)
    - shoulder_y: mean shoulder height (normalized 0-1, 0=top)
    - hip_y: mean hip height
    - body_horizontal: whether torso is close to horizontal
    """
    # Torso vector: midpoint(hips) to midpoint(shoulders)
    mid_shoulder_y = _midpoint(frame, _LEFT_SHOULDER, _RIGHT_SHOULDER, _Y)
    mid_hip_y = _midpoint(frame, _LEFT_HIP, _RIGHT_HIP, _Y)
    mid_shoulder_x = _midpoint(frame, _LEFT_SHOULDER, _RIGHT_SHOULDER, _X)
    mid_hip_x = _midpoint(frame, _LEFT_HIP, _RIGHT_HIP, _X)

    # Torso angle from vertical (y-axis goes down in image coords)
    dx = mid_shoulder_x - mid_hip_x
    dy = mid_hip_y - mid_shoulder_y  # flip so positive = upright
    torso_from_vertical = float(np.degrees(np.arctan2(abs(dx), dy + 1e-9)))

    # Joint angles (average left and right)
    hip_angle_l = _angle_3pts(frame[_LEFT_SHOULDER], frame[_LEFT_HIP], frame[_LEFT_KNEE])
    hip_angle_r = _angle_3pts(frame[_RIGHT_SHOULDER], frame[_RIGHT_HIP], frame[_RIGHT_KNEE])
    hip_angle = (hip_angle_l + hip_angle_r) / 2.0

    knee_angle_l = _angle_3pts(frame[_LEFT_HIP], frame[_LEFT_KNEE], frame[_LEFT_ANKLE])
    knee_angle_r = _angle_3pts(frame[_RIGHT_HIP], frame[_RIGHT_KNEE], frame[_RIGHT_ANKLE])
    knee_angle = (knee_angle_l + knee_angle_r) / 2.0

    elbow_angle_l = _angle_3pts(frame[_LEFT_SHOULDER], frame[_LEFT_ELBOW], frame[_LEFT_WRIST])
    elbow_angle_r = _angle_3pts(frame[_RIGHT_SHOULDER], frame[_RIGHT_ELBOW], frame[_RIGHT_WRIST])
    elbow_angle = (elbow_angle_l + elbow_angle_r) / 2.0

    return {
        "torso_vertical": torso_from_vertical,
        "hip_angle": hip_angle,
        "knee_angle": knee_angle,
        "elbow_angle": elbow_angle,
        "shoulder_y": mid_shoulder_y,
        "hip_y": mid_hip_y,
    }


def _compute_scores(features_list: list[dict[str, float]]) -> dict[str, float]:
    """Compute exercise-type confidence scores from aggregated frame features.

    Heuristic rules:
    - **Bench**: torso near-horizontal (high torso_from_vertical), shoulders at
      similar y to hips, significant elbow flexion variation.
    - **Squat**: torso mostly upright, significant knee and hip flexion, hips stay
      above or near knee level.
    - **Deadlift**: significant hip hinge (low hip angle), knees less flexed than
      squat, torso leans forward substantially.
    """
    n = len(features_list)
    if n == 0:
        return {"squat": 0.33, "bench": 0.33, "deadlift": 0.33}

    # Aggregate features across frames
    torso_angles = [f["torso_vertical"] for f in features_list]
    hip_angles = [f["hip_angle"] for f in features_list]
    knee_angles = [f["knee_angle"] for f in features_list]
    elbow_angles = [f["elbow_angle"] for f in features_list]
    shoulder_ys = [f["shoulder_y"] for f in features_list]
    hip_ys = [f["hip_y"] for f in features_list]

    mean_torso = float(np.mean(torso_angles))
    min_hip = float(np.min(hip_angles))
    min_knee = float(np.min(knee_angles))
    elbow_range = float(np.max(elbow_angles) - np.min(elbow_angles))

    # Shoulder-hip vertical distance (normalized): small = horizontal body
    shoulder_hip_dist = float(np.mean([
        abs(sy - hy) for sy, hy in zip(shoulder_ys, hip_ys)
    ]))

    scores: dict[str, float] = {"squat": 0.0, "bench": 0.0, "deadlift": 0.0}

    # --- Bench signals ---
    # Horizontal torso (>50 deg from vertical), small shoulder-hip distance,
    # significant elbow range of motion
    if mean_torso > 50:
        scores["bench"] += 0.35
    if shoulder_hip_dist < 0.15:
        scores["bench"] += 0.25
    if elbow_range > 30:
        scores["bench"] += 0.20
    if mean_torso > 70:
        scores["bench"] += 0.15

    # --- Squat signals ---
    # Upright torso (<35 deg), significant knee flexion, hip flexion
    if mean_torso < 35:
        scores["squat"] += 0.30
    if min_knee < 110:
        scores["squat"] += 0.25
    if min_hip < 110:
        scores["squat"] += 0.20
    # Both knee and hip flex substantially
    if min_knee < 100 and min_hip < 100:
        scores["squat"] += 0.15

    # --- Deadlift signals ---
    # Moderate torso lean (25-60 deg), hip hinge dominant, less knee bend
    if 25 < mean_torso < 60:
        scores["deadlift"] += 0.25
    if min_hip < 90:
        scores["deadlift"] += 0.30
    if min_knee > 90:  # knees not as bent as squat
        scores["deadlift"] += 0.20
    # Hip hinge more than knee bend
    if min_hip < min_knee - 15:
        scores["deadlift"] += 0.20

    # Normalize to sum to 1.0
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}
    else:
        scores = {"squat": 0.33, "bench": 0.33, "deadlift": 0.33}

    return scores


_DEFAULT_VARIANTS: dict[str, str] = {
    "squat": "high_bar",
    "bench": "flat",
    "deadlift": "conventional",
}


def detect_exercise_heuristic(
    landmarks_per_frame: list[np.ndarray],
    sample_count: int = 20,
) -> DetectionResult:
    """Classify exercise type from landmark geometry (FR-XDET-03).

    Samples up to ``sample_count`` evenly-spaced frames, computes joint angle
    features, and scores each exercise type. Returns the highest-scoring type
    with its confidence.

    Parameters
    ----------
    landmarks_per_frame:
        Full clip's landmark arrays — list of (33, 5) ndarrays.
    sample_count:
        Number of frames to sample (default 20, evenly spaced).

    Returns
    -------
    DetectionResult
        With method="heuristic".
    """
    n_frames = len(landmarks_per_frame)
    if n_frames == 0:
        return DetectionResult(
            detected_type="squat",
            detected_variant="high_bar",
            confidence=0.0,
            method="heuristic",
            details={"error": "no_frames"},
        )

    # Sample evenly spaced frames
    if n_frames <= sample_count:
        indices = list(range(n_frames))
    else:
        indices = [int(i * (n_frames - 1) / (sample_count - 1)) for i in range(sample_count)]

    # Filter out frames with low visibility on key landmarks
    key_landmarks = [
        _LEFT_SHOULDER, _RIGHT_SHOULDER, _LEFT_HIP, _RIGHT_HIP,
        _LEFT_KNEE, _RIGHT_KNEE, _LEFT_ANKLE, _RIGHT_ANKLE,
    ]
    features_list: list[dict[str, float]] = []
    for idx in indices:
        frame = landmarks_per_frame[idx]
        vis = _mean_visibility(frame, key_landmarks)
        if vis > 0.3:
            features_list.append(_classify_single_frame(frame))

    if not features_list:
        return DetectionResult(
            detected_type="squat",
            detected_variant="high_bar",
            confidence=0.0,
            method="heuristic",
            details={"error": "no_visible_frames"},
        )

    scores = _compute_scores(features_list)
    best_type: ExerciseTypeLiteral = max(scores, key=scores.get)  # type: ignore[arg-type]
    best_conf = scores[best_type]

    return DetectionResult(
        detected_type=best_type,
        detected_variant=_DEFAULT_VARIANTS[best_type],
        confidence=round(best_conf, 4),
        method="heuristic",
        details={"scores": {k: round(v, 4) for k, v in scores.items()},
                 "frames_analyzed": len(features_list)},
    )
