"""Synthetic video fixture generator for Spelix test suite (B-054).

Generates three ~3-second 720p 30fps MP4 files with simple geometric animations
representing squat, deadlift, and bench press movements.  No real video or
MediaPipe required — these are lightweight pixel-level stubs used to verify the
CV pipeline can consume valid video files without crashing.

Usage:
    uv run python tests/fixtures/generate_fixtures.py

Idempotent: skips generation if the output file already exists.
"""

from __future__ import annotations

import math
import os

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WIDTH = 1280
HEIGHT = 720
FPS = 30
DURATION_S = 3
TOTAL_FRAMES = FPS * DURATION_S  # 90

_OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# BGR colours
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)
_BLUE = (255, 80, 40)
_GREEN = (40, 200, 80)
_RED = (40, 80, 220)

# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def _blank_frame() -> np.ndarray:
    """Return a white 720p BGR frame."""
    return np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)


def _draw_stick_figure(
    frame: np.ndarray,
    cx: int,
    hip_y: int,
    knee_y: int,
    ankle_y: int,
    shoulder_y: int,
    elbow_y: int,
    wrist_y: int,
    colour: tuple[int, int, int],
) -> None:
    """Draw a minimal stick figure with joints as circles and limbs as lines.

    All joints are centred horizontally at *cx* with horizontal offsets for
    legs/arms to create a plausible silhouette.
    """
    r = 12  # joint circle radius
    lw = 3  # line width

    # Joint positions (x, y) — slight horizontal spread for limbs
    shoulder = (cx, shoulder_y)
    hip = (cx, hip_y)
    l_knee = (cx - 60, knee_y)
    r_knee = (cx + 60, knee_y)
    l_ankle = (cx - 70, ankle_y)
    r_ankle = (cx + 70, ankle_y)
    l_elbow = (cx - 100, elbow_y)
    r_elbow = (cx + 100, elbow_y)
    l_wrist = (cx - 130, wrist_y)
    r_wrist = (cx + 130, wrist_y)

    # Torso
    cv2.line(frame, shoulder, hip, colour, lw)

    # Left leg
    cv2.line(frame, hip, l_knee, colour, lw)
    cv2.line(frame, l_knee, l_ankle, colour, lw)

    # Right leg
    cv2.line(frame, hip, r_knee, colour, lw)
    cv2.line(frame, r_knee, r_ankle, colour, lw)

    # Left arm
    cv2.line(frame, shoulder, l_elbow, colour, lw)
    cv2.line(frame, l_elbow, l_wrist, colour, lw)

    # Right arm
    cv2.line(frame, shoulder, r_elbow, colour, lw)
    cv2.line(frame, r_elbow, r_wrist, colour, lw)

    # Draw circles at joints
    for pt in [shoulder, hip, l_knee, r_knee, l_ankle, r_ankle, l_elbow, r_elbow, l_wrist, r_wrist]:
        cv2.circle(frame, pt, r, colour, -1)
        cv2.circle(frame, pt, r, _BLACK, 1)


# ---------------------------------------------------------------------------
# Per-exercise frame renderers
# ---------------------------------------------------------------------------


def _render_squat_frame(frame_idx: int) -> np.ndarray:
    """Vertical hip oscillation simulating a squat rep cycle.

    Hip and knee descend on the first half of each rep, then rise.
    """
    frame = _blank_frame()
    cx = WIDTH // 2

    # Normalised phase [0..1] over TOTAL_FRAMES with 2 rep cycles
    phase = (frame_idx / TOTAL_FRAMES) * 2 * math.pi * 2
    # depth_factor: 0 = standing, 1 = bottom
    depth = (1.0 - math.cos(phase)) / 2.0

    # Standing: hip at ~38%, knee at ~55%, ankle at ~72%
    # Bottom:   hip drops ~12%, knee drops ~6%
    hip_y = int(HEIGHT * (0.38 + 0.12 * depth))
    knee_y = int(HEIGHT * (0.55 + 0.06 * depth))
    ankle_y = int(HEIGHT * 0.72)
    shoulder_y = int(HEIGHT * (0.22 - 0.04 * depth))  # torso leans slightly
    elbow_y = shoulder_y + 60
    wrist_y = elbow_y + 60

    _draw_stick_figure(frame, cx, hip_y, knee_y, ankle_y, shoulder_y, elbow_y, wrist_y, _BLUE)

    # Label
    cv2.putText(frame, f"squat f{frame_idx}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, _BLACK, 2)
    return frame


def _render_deadlift_frame(frame_idx: int) -> np.ndarray:
    """Hip hinge motion simulating a deadlift rep cycle."""
    frame = _blank_frame()
    cx = WIDTH // 2

    phase = (frame_idx / TOTAL_FRAMES) * 2 * math.pi * 2
    depth = (1.0 - math.cos(phase)) / 2.0

    # Hip drops and torso hinges forward at the bottom
    hip_y = int(HEIGHT * (0.40 + 0.15 * depth))
    knee_y = int(HEIGHT * 0.58)  # knees barely bend in deadlift
    ankle_y = int(HEIGHT * 0.72)
    shoulder_y = int(HEIGHT * (0.25 + 0.10 * depth))  # torso tilts forward
    elbow_y = shoulder_y + 70
    wrist_y = int(HEIGHT * (0.50 + 0.12 * depth))  # wrists follow bar

    _draw_stick_figure(frame, cx, hip_y, knee_y, ankle_y, shoulder_y, elbow_y, wrist_y, _GREEN)

    cv2.putText(frame, f"deadlift f{frame_idx}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, _BLACK, 2)
    return frame


def _render_bench_frame(frame_idx: int) -> np.ndarray:
    """Arm extension / elbow flexion simulating a bench press rep cycle."""
    frame = _blank_frame()
    cx = WIDTH // 2

    phase = (frame_idx / TOTAL_FRAMES) * 2 * math.pi * 2
    depth = (1.0 - math.cos(phase)) / 2.0

    # Body is horizontal (lying on bench) — represent from side view
    shoulder_y = int(HEIGHT * 0.45)
    hip_y = int(HEIGHT * 0.45)  # flat body
    knee_y = int(HEIGHT * 0.50)
    ankle_y = int(HEIGHT * 0.55)

    # Arms: lockout = elbow low (arms extended), bottom = elbow high (flexed)
    elbow_y = int(HEIGHT * (0.38 - 0.08 * depth))  # rises at bottom
    wrist_y = int(HEIGHT * (0.32 - 0.12 * depth))  # wrists track bar

    _draw_stick_figure(frame, cx, hip_y, knee_y, ankle_y, shoulder_y, elbow_y, wrist_y, _RED)

    cv2.putText(frame, f"bench f{frame_idx}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, _BLACK, 2)
    return frame


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def _write_video(output_path: str, renderer) -> None:
    """Write TOTAL_FRAMES rendered frames to *output_path* as MP4."""
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, float(FPS), (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError(f"VideoWriter could not open: {output_path}")
    try:
        for i in range(TOTAL_FRAMES):
            frame = renderer(i)
            writer.write(frame)
    finally:
        writer.release()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def generate_all() -> None:
    fixtures = [
        ("squat_synthetic.mp4", _render_squat_frame),
        ("deadlift_synthetic.mp4", _render_deadlift_frame),
        ("bench_synthetic.mp4", _render_bench_frame),
    ]

    for filename, renderer in fixtures:
        out = os.path.join(_OUTPUT_DIR, filename)
        if os.path.isfile(out):
            size = os.path.getsize(out)
            print(f"[skip] {filename} already exists ({size} bytes)")
            continue

        print(f"[gen]  {filename} ...", end=" ", flush=True)
        _write_video(out, renderer)
        size = os.path.getsize(out)
        print(f"done ({size} bytes)")

    print("All fixtures ready.")


if __name__ == "__main__":
    generate_all()
