"""
Unit tests for app/services/pipeline.py — run_cv_pipeline orchestration (B-053).

All CV functions are mocked; no real video or MediaPipe required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.cv.exercise_detection import DetectionResult
from app.cv.metric_extraction import RepMetrics
from app.cv.quality_gates import GateCheckResult, QualityGateResult
from app.cv.rep_detection import DetectedRep
from app.models.analysis import Analysis
from app.services.pipeline import (
    PipelineResult,
    QualityGateRejection,
    run_cv_pipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ANALYSIS_ID = uuid.uuid4()
_FRAME_WIDTH = 1280
_FRAME_HEIGHT = 720
_FPS = 30.0
_NUM_FRAMES = 90  # 3 seconds


def _make_landmark_frame(visibility: float = 0.9) -> np.ndarray:
    """Return a (33, 5) landmark array with uniform values."""
    frame = np.zeros((33, 5), dtype=np.float32)
    frame[:, 0] = 0.5  # x
    frame[:, 1] = 0.5  # y
    frame[:, 3] = visibility  # col 3 = visibility
    frame[:, 4] = visibility  # col 4 = presence (needed for Tier 1–5 confidence)
    return frame


def _make_landmarks(n: int = _NUM_FRAMES, visibility: float = 0.9) -> list[np.ndarray]:
    return [_make_landmark_frame(visibility) for _ in range(n)]


def _make_analysis(status: str = "quality_gate_pending") -> Analysis:
    """Build a mock Analysis fixture for run_cv_pipeline tests.

    Default status is ``quality_gate_pending`` because that's the status
    the worker pipeline expects to find when it picks up a job —
    ``AnalysisService.start_analysis`` performs the
    ``queued → quality_gate_pending`` transition before enqueueing,
    so the row is already at ``quality_gate_pending`` by the time
    ``run_cv_pipeline`` runs. The pipeline's first transition is
    ``quality_gate_pending → processing``.
    """
    a = Analysis()
    a.id = _ANALYSIS_ID
    a.status = status
    a.exercise_type = "squat"
    a.exercise_variant = "default"
    a.video_path = None
    return a


def _make_gate_result(passed: bool = True) -> QualityGateResult:
    check = GateCheckResult(
        passed=passed,
        name="body_visibility",
        level="error",
        metric_value=0.9 if passed else 0.1,
        threshold=0.3,
        user_message="ok" if passed else "Body not visible",
    )
    return QualityGateResult(
        passed=passed,
        status="passed" if passed else "rejected",
        checks=[check],
    )


def _make_reps() -> list[DetectedRep]:
    return [
        DetectedRep(rep_index=0, start_frame=0, end_frame=30, confidence_score=0.85, min_angle=80.0),
        DetectedRep(rep_index=1, start_frame=31, end_frame=60, confidence_score=0.90, min_angle=75.0),
    ]


def _make_rep_metrics(reps: list[DetectedRep]) -> list[RepMetrics]:
    return [
        RepMetrics(
            rep_index=r.rep_index,
            start_frame=r.start_frame,
            end_frame=r.end_frame,
            metrics={"hip_angle_min": r.min_angle},
        )
        for r in reps
    ]


def _make_angle_timeseries(n: int = _NUM_FRAMES) -> dict[str, np.ndarray]:
    return {
        "hip_angle": np.linspace(160, 80, n, dtype=np.float32),
    }


def _make_bar_path() -> dict:
    return {
        "centroids": [(0.5, 0.5)] * _NUM_FRAMES,
        "ap_deviation_px": 0.01,
        "vertical_range_px": 0.2,
        "path_consistency": 0.95,
    }


# ---------------------------------------------------------------------------
# Patch target constants
# ---------------------------------------------------------------------------

_PKG = "app.services.pipeline"


@pytest.fixture(autouse=True)
def _stub_persist_timing_telemetry(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default no-op stub for the fresh-session telemetry helper.

    Without this, pipeline tests that don't explicitly patch the helper
    would open real DB connections (and fail noisily in CI with no DB).
    Tests that need to observe the helper's calls opt out via the
    `real_persist_helper` marker (see `test_persist_timing_telemetry_*`).
    """
    if request.node.get_closest_marker("real_persist_helper") is not None:
        return
    import app.services.pipeline as pipeline_mod

    async def _noop(_analysis_id, _timing_dict):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(pipeline_mod, "_persist_timing_telemetry", _noop)


# ---------------------------------------------------------------------------
# Test: Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_all_steps_execute():
    """Full pipeline runs end-to-end; all CV functions called; result populated."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()
    bar_path = _make_bar_path()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)) as mock_landmarks,
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)) as mock_gates,
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts) as mock_angles,
        patch(f"{_PKG}.detect_reps", return_value=reps) as mock_reps,
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics) as mock_metrics,
        patch(f"{_PKG}.compute_session_confidence", return_value=0.875) as mock_confidence,
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=bar_path) as mock_bar,
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4") as mock_annotated,
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png") as mock_plot,
        patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock) as mock_upload,
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,  # no upload
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    # All major CV functions were called
    mock_landmarks.assert_called_once()
    mock_gates.assert_called_once()
    mock_angles.assert_called_once()
    mock_reps.assert_called_once()
    mock_metrics.assert_called_once()
    mock_confidence.assert_called_once()  # args are Tier 5 values from compute_confidence_result
    mock_bar.assert_called_once()
    mock_annotated.assert_called_once()
    mock_plot.assert_called_once()

    # PipelineResult fields populated
    assert isinstance(result, PipelineResult)
    assert result.landmarks_per_frame is landmarks
    assert result.fps == _FPS
    assert result.frame_width == _FRAME_WIDTH
    assert result.frame_height == _FRAME_HEIGHT
    assert result.reps is reps
    assert result.rep_metrics is rep_metrics
    assert result.session_confidence == pytest.approx(0.875)
    assert result.bar_path == bar_path
    assert result.detection_result is not None
    assert result.detection_result.method == "heuristic"

    # Status transitions happened
    assert analysis.status == "processing"
    assert analysis.confidence_score == pytest.approx(0.875)

    # DB updates called
    assert repo.update.call_count >= 3

    # Heartbeat written multiple times
    assert write_heartbeat.call_count >= 3

    # No upload because storage_client=None
    mock_upload.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Quality gate rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_gate_rejection_raises():
    """When quality gates fail, QualityGateRejection is raised and status set."""
    landmarks = _make_landmarks(visibility=0.1)  # low visibility → would fail

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=False)),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        with pytest.raises(QualityGateRejection):
            await run_cv_pipeline(
                analysis=analysis,
                repo=repo,
                rep_metric_repo=rep_metric_repo,
                storage_client=None,
                redis=redis,
                write_heartbeat=write_heartbeat,
            )

    assert analysis.status == "quality_gate_rejected"
    # gate result written to DB
    assert analysis.quality_gate_result is not None
    assert analysis.quality_gate_result["passed"] is False
    assert analysis.quality_gate_result["status"] == "rejected"


# ---------------------------------------------------------------------------
# Test: RuntimeError during CV propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cv_runtime_error_propagates():
    """RuntimeError from extract_landmarks propagates out of the pipeline."""
    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", side_effect=RuntimeError("MediaPipe crashed")),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        with pytest.raises(RuntimeError, match="MediaPipe crashed"):
            await run_cv_pipeline(
                analysis=analysis,
                repo=repo,
                rep_metric_repo=rep_metric_repo,
                storage_client=None,
                redis=redis,
                write_heartbeat=write_heartbeat,
            )


# ---------------------------------------------------------------------------
# Test: Bar path from landmarks (always-on in Phase 0)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bar_path_from_landmarks_called():
    """Pipeline calls compute_bar_path_from_landmarks and stores result."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()
    expected_bar_path = _make_bar_path()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=expected_bar_path) as mock_bar,
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    mock_bar.assert_called_once_with(landmarks, "squat")
    assert result.bar_path == expected_bar_path


# ---------------------------------------------------------------------------
# Test: No storage client — artifacts generated locally but not uploaded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_storage_client_skips_upload():
    """When storage_client=None, generate artifacts locally but skip upload."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4") as mock_annotated,
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png") as mock_plot,
        patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock) as mock_upload,
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,  # <-- no client
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    # Artifact generation still happens
    mock_annotated.assert_called_once()
    mock_plot.assert_called_once()

    # Upload never called
    mock_upload.assert_not_called()

    # Storage paths NOT set on analysis or result
    assert analysis.annotated_video_path is None
    assert analysis.plot_path is None
    assert result.annotated_video_storage_path is None
    assert result.plot_storage_path is None


# ---------------------------------------------------------------------------
# Test: With storage client — artifacts uploaded and paths stored
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_with_storage_client_uploads_artifacts():
    """When storage_client is provided, artifacts are uploaded and paths stored."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    # Mock a Supabase storage client
    storage_mock = AsyncMock()
    storage_mock.storage.from_.return_value.remove = AsyncMock(return_value=None)

    annotated_storage = f"artifacts/{_ANALYSIS_ID}/annotated.mp4"
    plot_storage = f"artifacts/{_ANALYSIS_ID}/angles.png"

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock, return_value="ok") as mock_upload,
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=storage_mock,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    assert mock_upload.call_count == 2
    assert analysis.annotated_video_path == annotated_storage
    assert analysis.plot_path == plot_storage
    assert result.annotated_video_storage_path == annotated_storage
    assert result.plot_storage_path == plot_storage


# ---------------------------------------------------------------------------
# Test: Quality gate result stored as JSONB-compatible dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_gate_result_written_to_analysis():
    """Gate result is serialised to a dict before saving to the analysis row."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    qg = analysis.quality_gate_result
    assert isinstance(qg, dict)
    assert qg["passed"] is True
    assert qg["status"] == "passed"
    assert isinstance(qg["checks"], list)
    assert len(qg["checks"]) == 1
    check = qg["checks"][0]
    assert "name" in check
    assert "passed" in check
    assert "level" in check
    assert "metric_value" in check
    assert "threshold" in check
    assert "user_message" in check


# ---------------------------------------------------------------------------
# Test: Rep metrics batch-inserted when reps are present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rep_metrics_batch_inserted():
    """Rep metrics are batch-inserted into the DB when reps are detected."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    rep_metric_repo.create_batch.assert_called_once()
    inserted = rep_metric_repo.create_batch.call_args[0][0]
    assert len(inserted) == len(rep_metrics)
    # Each inserted row carries the correct analysis_id
    for row in inserted:
        assert row.analysis_id == _ANALYSIS_ID


# ---------------------------------------------------------------------------
# Test: No reps — skip batch insert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_reps_skips_batch_insert():
    """When no reps are detected, rep_metric_repo.create_batch is not called."""
    landmarks = _make_landmarks()
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=[]),
        patch(f"{_PKG}.extract_rep_metrics", return_value=[]),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.0),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=None),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    rep_metric_repo.create_batch.assert_not_called()
    assert result.reps == []
    assert result.rep_metrics == []


# ---------------------------------------------------------------------------
# Test: PipelineResult default values
# ---------------------------------------------------------------------------


def test_pipeline_result_defaults():
    """PipelineResult initialises with safe defaults."""
    result = PipelineResult()
    assert result.landmarks_per_frame == []
    assert result.fps == 30.0
    assert result.frame_width == 0
    assert result.frame_height == 0
    assert result.angle_timeseries == {}
    assert result.reps == []
    assert result.rep_metrics == []
    assert result.session_confidence == 0.0
    assert result.bar_path is None
    assert result.annotated_video_storage_path is None
    assert result.plot_storage_path is None


# ---------------------------------------------------------------------------
# Test: QualityGateRejection is an Exception
# ---------------------------------------------------------------------------


def test_quality_gate_rejection_is_exception():
    exc = QualityGateRejection("test message")
    assert isinstance(exc, Exception)
    assert str(exc) == "test message"


# ---------------------------------------------------------------------------
# Test: GPT-4o fallback wiring (FR-XDET-04)
# ---------------------------------------------------------------------------


def _make_low_conf_detection() -> DetectionResult:
    """Heuristic detection with confidence below 0.7 threshold."""
    return DetectionResult(
        detected_type="squat",
        detected_variant="high_bar",
        confidence=0.45,
        method="heuristic",
        details={"scores": {"squat": 0.45, "bench": 0.3, "deadlift": 0.25}, "frames_analyzed": 20},
    )


def _make_high_conf_detection() -> DetectionResult:
    """Heuristic detection with confidence above 0.7 threshold."""
    return DetectionResult(
        detected_type="squat",
        detected_variant="high_bar",
        confidence=0.85,
        method="heuristic",
        details={"scores": {"squat": 0.85, "bench": 0.1, "deadlift": 0.05}, "frames_analyzed": 20},
    )


@pytest.mark.asyncio
async def test_gpt4o_fallback_triggered_when_heuristic_low_confidence():
    """When heuristic confidence < 0.7 and openai_client provided, GPT-4o fallback runs."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()
    openai_client = MagicMock()

    from app.services.keyframe_analysis import ExerciseClassification

    mock_classification = ExerciseClassification(
        exercise_type="deadlift",
        exercise_variant="conventional",
        confidence=0.92,
        reasoning="Hip hinge pattern with bar starting on floor",
    )

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch("app.cv.exercise_detection.detect_exercise_heuristic", return_value=_make_low_conf_detection()),
        patch(f"{_PKG}._extract_sample_frames_b64", return_value=["frame1_b64", "frame2_b64", "frame3_b64"]),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
        patch("app.services.keyframe_analysis.KeyframeAnalysisService.classify_exercise", new_callable=AsyncMock, return_value=mock_classification) as mock_classify,
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
            openai_client=openai_client,
        )

    # Fallback was called
    mock_classify.assert_called_once()

    # Detection result should reflect GPT-4o fallback
    assert result.detection_result.method == "vision_fallback"
    assert result.detection_result.detected_type == "deadlift"
    assert result.detection_result.confidence == 0.92
    assert result.detection_result.details["heuristic_confidence"] == 0.45
    assert result.detection_result.details["heuristic_type"] == "squat"

    # Stored on analysis JSONB
    assert analysis.detection_result["method"] == "vision_fallback"
    assert analysis.detection_result["detected_type"] == "deadlift"


@pytest.mark.asyncio
async def test_gpt4o_fallback_not_triggered_when_high_confidence():
    """When heuristic confidence >= 0.7, GPT-4o fallback is NOT called."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()
    openai_client = MagicMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch("app.cv.exercise_detection.detect_exercise_heuristic", return_value=_make_high_conf_detection()),
        patch(f"{_PKG}._extract_sample_frames_b64") as mock_frames,
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
            openai_client=openai_client,
        )

    # Frame extraction never called — heuristic was confident
    mock_frames.assert_not_called()

    # Detection stays as heuristic
    assert result.detection_result.method == "heuristic"
    assert result.detection_result.confidence == 0.85


@pytest.mark.asyncio
async def test_gpt4o_fallback_not_triggered_when_no_openai_client():
    """When openai_client is None, GPT-4o fallback is skipped even if confidence is low."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch("app.cv.exercise_detection.detect_exercise_heuristic", return_value=_make_low_conf_detection()),
        patch(f"{_PKG}._extract_sample_frames_b64") as mock_frames,
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
            # openai_client=None (default)
        )

    # Frame extraction never called
    mock_frames.assert_not_called()

    # Heuristic result used despite low confidence
    assert result.detection_result.method == "heuristic"
    assert result.detection_result.confidence == 0.45


@pytest.mark.asyncio
async def test_gpt4o_fallback_error_falls_back_to_heuristic():
    """When GPT-4o classify_exercise raises, heuristic result is kept."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()
    openai_client = MagicMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch("app.cv.exercise_detection.detect_exercise_heuristic", return_value=_make_low_conf_detection()),
        patch(f"{_PKG}._extract_sample_frames_b64", return_value=["frame1", "frame2", "frame3"]),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
        patch("app.services.keyframe_analysis.KeyframeAnalysisService.classify_exercise", new_callable=AsyncMock, side_effect=RuntimeError("OpenAI timeout")),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
            openai_client=openai_client,
        )

    # Falls back to heuristic
    assert result.detection_result.method == "heuristic"
    assert result.detection_result.confidence == 0.45


# ---------------------------------------------------------------------------
# Test: Pipeline timing instrumentation (D-035)
# ---------------------------------------------------------------------------


class TestPipelineTimingInstrumentation:
    """Pipeline records per-stage wall durations to analysis.timing_json (D-035)."""

    @pytest.mark.asyncio
    async def test_timing_json_populated_with_expected_stages(self):
        """After successful pipeline run, timing_json has every documented stage."""
        landmarks = _make_landmarks()
        reps = _make_reps()
        rep_metrics = _make_rep_metrics(reps)
        angle_ts = _make_angle_timeseries()

        analysis = _make_analysis()
        repo = AsyncMock()
        rep_metric_repo = AsyncMock()
        redis = MagicMock()
        write_heartbeat = AsyncMock()

        with (
            patch(f"{_PKG}.probe_duration_seconds", return_value=10.0),  # under 60s cap
            patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
            patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
            patch("app.cv.exercise_detection.detect_exercise_heuristic", return_value=_make_high_conf_detection()),
            patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
            patch(f"{_PKG}.detect_reps", return_value=reps),
            patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
            patch(f"{_PKG}.compute_session_confidence", return_value=0.85),
            patch(f"{_PKG}.track_barbell_from_video", return_value=[None] * _NUM_FRAMES),
            patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
            patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
            patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
            patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock, return_value="public/url"),
            patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
            patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
            patch("os.path.isfile", return_value=False),
        ):
            await run_cv_pipeline(
                analysis=analysis,
                repo=repo,
                rep_metric_repo=rep_metric_repo,
                storage_client=None,
                redis=redis,
                write_heartbeat=write_heartbeat,
                openai_client=None,
            )

        assert isinstance(analysis.timing_json, dict)
        for stage in [
            "download",
            "extract_landmarks",
            "exercise_detection",
            "quality_gates",
        ]:
            assert stage in analysis.timing_json, (
                f"Missing stage {stage!r} in timing_json: {analysis.timing_json}"
            )
            assert isinstance(analysis.timing_json[stage], float)
            assert analysis.timing_json[stage] >= 0.0

    @pytest.mark.real_persist_helper
    @pytest.mark.asyncio
    async def test_persist_timing_telemetry_uses_fresh_session_and_commits(
        self, monkeypatch
    ):
        """D-035 fix: telemetry writes go through a dedicated session that
        commits immediately, so they survive a rollback of the main pipeline
        session on timeout/error.

        Without this, the main analysis_worker.py except handler's
        ``session.rollback()`` wipes every in-flight timing_json write —
        exactly the case Priority 1 was meant to observe. This test nails
        the fresh-session + commit contract directly.
        """
        from uuid import uuid4

        captured: dict = {}
        commit_count = 0
        enter_count = 0

        class FakeSession:
            async def __aenter__(self_inner):
                nonlocal enter_count
                enter_count += 1
                return self_inner

            async def __aexit__(self_inner, *exc):
                return False

            async def execute(self_inner, stmt):
                captured["stmt"] = stmt

            async def commit(self_inner):
                nonlocal commit_count
                commit_count += 1

        def fake_factory():
            return FakeSession()

        from app.services import pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod, "async_session", fake_factory)

        analysis_id = uuid4()
        timings = {"download": 42.5, "duration_probe": 1.1}
        await pipeline_mod._persist_timing_telemetry(analysis_id, timings)

        assert enter_count == 1, "must open exactly one session"
        assert commit_count == 1, "must commit exactly once"
        assert captured.get("stmt") is not None, "must execute an UPDATE"

    @pytest.mark.asyncio
    async def test_timing_json_survives_main_session_rollback(
        self, monkeypatch
    ):
        """D-035 fix: verify the pipeline uses _persist_timing_telemetry for the
        3 early stages (download, duration_probe, extract_landmarks), not
        ``repo.update`` — ensuring these writes survive the
        analysis_worker.py rollback path on timeout.
        """
        landmarks = _make_landmarks()
        reps = _make_reps()
        rep_metrics = _make_rep_metrics(reps)
        angle_ts = _make_angle_timeseries()

        analysis = _make_analysis()
        repo = AsyncMock()
        rep_metric_repo = AsyncMock()
        redis = MagicMock()
        write_heartbeat = AsyncMock()

        persist_calls: list[tuple] = []

        async def _fake_persist(aid, timing):
            persist_calls.append((aid, dict(timing)))

        from app.services import pipeline as pipeline_mod

        monkeypatch.setattr(
            pipeline_mod, "_persist_timing_telemetry", _fake_persist
        )

        with (
            patch(f"{_PKG}.probe_duration_seconds", return_value=10.0),
            patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
            patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
            patch("app.cv.exercise_detection.detect_exercise_heuristic", return_value=_make_high_conf_detection()),
            patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
            patch(f"{_PKG}.detect_reps", return_value=reps),
            patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
            patch(f"{_PKG}.compute_session_confidence", return_value=0.85),
            patch(f"{_PKG}.track_barbell_from_video", return_value=[None] * _NUM_FRAMES),
            patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
            patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
            patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
            patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock, return_value="public/url"),
            patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
            patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
            patch("os.path.isfile", return_value=False),
        ):
            await run_cv_pipeline(
                analysis=analysis,
                repo=repo,
                rep_metric_repo=rep_metric_repo,
                storage_client=None,
                redis=redis,
                write_heartbeat=write_heartbeat,
                openai_client=None,
            )

        assert len(persist_calls) >= 3, (
            f"_persist_timing_telemetry must be called at least 3 times "
            f"(after download, duration_probe, extract_landmarks); got {len(persist_calls)}"
        )

        stage_sets = [set(t.keys()) for _aid, t in persist_calls]
        assert {"download"} in stage_sets, (
            f"no post-download-only persist; got {stage_sets}"
        )
        assert {"download", "duration_probe"} in stage_sets, (
            f"no post-duration-probe persist; got {stage_sets}"
        )
        assert {"download", "duration_probe", "extract_landmarks"} in stage_sets, (
            f"no post-extract-landmarks persist (before exercise_detection); got {stage_sets}"
        )

    @pytest.mark.asyncio
    async def test_timing_json_persists_every_post_extract_stage(
        self, monkeypatch
    ):
        """D-035 full-stage telemetry: every pipeline stage after
        extract_landmarks must be flushed via _persist_timing_telemetry so
        the 24-min gap observed in session 37 becomes visible. Prior fix
        covered only download/duration_probe/extract_landmarks; this extends
        to every stage so we can pinpoint the real bottleneck.
        """
        landmarks = _make_landmarks()
        reps = _make_reps()
        rep_metrics = _make_rep_metrics(reps)
        angle_ts = _make_angle_timeseries()

        analysis = _make_analysis()
        repo = AsyncMock()
        rep_metric_repo = AsyncMock()
        redis = MagicMock()
        write_heartbeat = AsyncMock()

        persist_calls: list[tuple] = []

        async def _fake_persist(aid, timing):
            persist_calls.append((aid, dict(timing)))

        from app.services import pipeline as pipeline_mod

        monkeypatch.setattr(
            pipeline_mod, "_persist_timing_telemetry", _fake_persist
        )

        with (
            patch(f"{_PKG}.probe_duration_seconds", return_value=10.0),
            patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
            patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
            patch("app.cv.exercise_detection.detect_exercise_heuristic", return_value=_make_high_conf_detection()),
            patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
            patch(f"{_PKG}.detect_reps", return_value=reps),
            patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
            patch(f"{_PKG}.compute_session_confidence", return_value=0.85),
            patch(f"{_PKG}.track_barbell_from_video", return_value=[None] * _NUM_FRAMES),
            patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
            patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
            patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
            patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock, return_value="public/url"),
            patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
            patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
            patch("os.path.isfile", return_value=False),
        ):
            await run_cv_pipeline(
                analysis=analysis,
                repo=repo,
                rep_metric_repo=rep_metric_repo,
                storage_client=None,
                redis=redis,
                write_heartbeat=write_heartbeat,
                openai_client=None,
            )

        # Final telemetry call must contain the full stage set.
        assert persist_calls, "expected at least one _persist_timing_telemetry call"
        final_stages = set(persist_calls[-1][1].keys())

        expected_stages = {
            "download",
            "duration_probe",
            "extract_landmarks",
            "exercise_detection",
            "quality_gates",
            "angle_timeseries",
            "rep_detection",
            "metric_extraction",
            "confidence_scoring",
            "keyframe_extraction",
            "barbell_tracking",
            "form_scoring",
            "generate_annotated_video",
            "generate_angle_plot",
        }
        missing = expected_stages - final_stages
        assert not missing, (
            f"timing_json missing stages by pipeline end: {sorted(missing)}. "
            f"Got: {sorted(final_stages)}"
        )


# ---------------------------------------------------------------------------
# Test: Duration gate rejection (D-035)
# ---------------------------------------------------------------------------


class TestPipelineDurationGate:
    """Pipeline rejects clips longer than the configured cap (D-035)."""

    @pytest.mark.asyncio
    async def test_pipeline_rejects_too_long_clip(self):
        analysis = _make_analysis()
        repo = AsyncMock()
        rep_metric_repo = AsyncMock()
        redis = MagicMock()
        write_heartbeat = AsyncMock()

        with (
            patch(f"{_PKG}.probe_duration_seconds", return_value=180.0),  # 3 min, exceeds 60s cap
            patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
            patch("os.path.isfile", return_value=False),
        ):
            with pytest.raises(QualityGateRejection):
                await run_cv_pipeline(
                    analysis=analysis,
                    repo=repo,
                    rep_metric_repo=rep_metric_repo,
                    storage_client=None,
                    redis=redis,
                    write_heartbeat=write_heartbeat,
                )

        assert analysis.status == "quality_gate_rejected"
        gate = analysis.quality_gate_result
        assert gate["passed"] is False
        check = next(c for c in gate["checks"] if c["name"] == "duration")
        assert check["metric_value"] == 180.0
        assert check["threshold"] == 60.0


# ---------------------------------------------------------------------------
# D-041: Degenerate scoring short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_form_scores_set_to_none_when_rep_metrics_empty():
    """
    When detect_reps returns [] and therefore rep_metrics is [], all five
    analysis.form_score_* columns must be set to None — NOT defaulted to
    10.0 by scoring components on empty input (D-041).
    """
    landmarks = _make_landmarks()
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=[]),
        patch(f"{_PKG}.extract_rep_metrics", return_value=[]),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.0),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=None),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch(f"{_PKG}.probe_duration_seconds", return_value=10.0),
        patch("os.path.isfile", return_value=False),
    ):
        await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    assert analysis.form_score_safety is None
    assert analysis.form_score_technique is None
    assert analysis.form_score_path_balance is None
    assert analysis.form_score_control is None
    assert analysis.form_score_overall is None


@pytest.mark.asyncio
async def test_form_scores_set_to_none_when_session_confidence_below_050():
    """
    When session confidence is below the Very-Low boundary (0.50), form
    scores must be None — prevents the session 44 contradiction where
    "Very Low confidence" banner rendered alongside Technique 10.0 (D-041).
    """
    landmarks = _make_landmarks()
    angle_ts = _make_angle_timeseries()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)

    analysis = _make_analysis()
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.35),  # Very Low
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=None),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch(f"{_PKG}.probe_duration_seconds", return_value=10.0),
        patch("os.path.isfile", return_value=False),
    ):
        await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    assert analysis.form_score_safety is None
    assert analysis.form_score_technique is None
    assert analysis.form_score_path_balance is None
    assert analysis.form_score_control is None
    assert analysis.form_score_overall is None


# ---------------------------------------------------------------------------
# D-041: Pure-function guard
# ---------------------------------------------------------------------------


def test_is_degenerate_scoring_input_empty_metrics():
    from app.services.pipeline import _is_degenerate_scoring_input
    assert _is_degenerate_scoring_input([], 0.9) is True


def test_is_degenerate_scoring_input_very_low_confidence():
    from app.services.pipeline import _is_degenerate_scoring_input
    # Non-empty list content doesn't matter — the guard is list emptiness + threshold
    assert _is_degenerate_scoring_input([object()], 0.49) is True


def test_is_degenerate_scoring_input_boundary_050_not_degenerate():
    """0.50 is the Low boundary — at-or-above Low is NOT degenerate."""
    from app.services.pipeline import _is_degenerate_scoring_input
    assert _is_degenerate_scoring_input([object()], 0.50) is False


def test_is_degenerate_scoring_input_good_input():
    from app.services.pipeline import _is_degenerate_scoring_input
    assert _is_degenerate_scoring_input([object()], 0.85) is False


# ---------------------------------------------------------------------------
# Additional branch-coverage tests for pipeline.py missed lines
# ---------------------------------------------------------------------------


def test_aggregate_rep_metrics_empty_returns_confidence_only() -> None:
    """_aggregate_rep_metrics with empty rep_metrics returns dict with only confidence_score (line 217)."""
    from app.services.pipeline import _aggregate_rep_metrics

    result = _aggregate_rep_metrics([], [], session_confidence=0.72)
    assert result == {"confidence_score": 0.72}


def test_aggregate_rep_metrics_std_dev_computed_for_multi_rep() -> None:
    """_aggregate_rep_metrics computes rep_duration_std and depth_angle_std when multiple reps (lines 233-235, 240-242)."""
    from app.services.pipeline import _aggregate_rep_metrics

    rm1 = RepMetrics(rep_index=0, start_frame=0, end_frame=10, metrics={"rep_duration_s": 1.0, "depth_angle": 90.0})
    rm2 = RepMetrics(rep_index=1, start_frame=11, end_frame=20, metrics={"rep_duration_s": 1.5, "depth_angle": 85.0})

    result = _aggregate_rep_metrics([rm1, rm2], [], session_confidence=0.85)

    assert "rep_duration_std" in result
    assert "depth_angle_std" in result
    assert result["confidence_score"] == 0.85


def test_aggregate_rep_metrics_skips_non_numeric_values() -> None:
    """_aggregate_rep_metrics skips non-numeric metric values like strings (line 223->222)."""
    from app.services.pipeline import _aggregate_rep_metrics

    rm1 = RepMetrics(rep_index=0, start_frame=0, end_frame=10, metrics={"phase": "descent", "depth_angle": 90.0})

    result = _aggregate_rep_metrics([rm1], [], session_confidence=0.80)
    # "phase" is a string — it should be skipped
    assert "phase" not in result
    assert "depth_angle" in result


@pytest.mark.asyncio
async def test_download_video_calls_storage_and_writes_file(tmp_path) -> None:
    """download_video calls storage client and writes data to local path (lines 158-162)."""
    from app.services.pipeline import download_video

    video_data = b"fake video bytes"

    mock_storage_client = MagicMock()
    mock_storage_client.storage.from_("videos").download = AsyncMock(return_value=video_data)
    # Properly chain the mock calls
    mock_from_result = AsyncMock()
    mock_from_result.download = AsyncMock(return_value=video_data)
    mock_storage_client.storage.from_ = MagicMock(return_value=mock_from_result)

    local_path = str(tmp_path / "test_video.mp4")

    result = await download_video(
        storage_client=mock_storage_client,
        bucket="videos",
        video_path="artifacts/123/test.mp4",
        local_path=local_path,
    )

    assert result == local_path
    import os
    assert os.path.isfile(local_path)
    with open(local_path, "rb") as f:
        assert f.read() == video_data


@pytest.mark.asyncio
async def test_local_video_path_used_when_no_storage_client_and_file_exists(tmp_path) -> None:
    """When storage_client=None and video_path is a local file, video_local is set to it (line 364)."""
    # Create a real local video file so os.path.isfile returns True
    local_video = str(tmp_path / "local_video.mp4")
    with open(local_video, "wb") as f:
        f.write(b"fake video")

    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    analysis.video_path = local_video  # set as local path

    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value=str(tmp_path)),
        # Do NOT mock os.path.isfile — we use a real file
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,  # no storage client
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    assert isinstance(result, PipelineResult)


@pytest.mark.asyncio
async def test_storage_client_with_video_path_downloads_and_deletes(tmp_path) -> None:
    """When storage_client is provided and video_path is set, video is downloaded and deleted (lines 358-362, 815-818)."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = _make_angle_timeseries()

    analysis = _make_analysis()
    analysis.video_path = "storage/path/video.mp4"  # triggers download

    # Mock the storage client
    fake_video_data = b"fake video content"
    mock_from = MagicMock()
    mock_from.download = AsyncMock(return_value=fake_video_data)
    mock_from.remove = AsyncMock(return_value=None)
    storage_mock = MagicMock()
    storage_mock.storage.from_ = MagicMock(return_value=mock_from)

    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps),
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value=str(tmp_path / "annotated.mp4")),
        patch(f"{_PKG}.generate_angle_plot", return_value=str(tmp_path / "angles.png")),
        patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock, return_value="ok"),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value=str(tmp_path)),
        patch("os.path.isfile", return_value=False),
    ):
        result = await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=storage_mock,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    assert isinstance(result, PipelineResult)
    # Storage download should have been called
    mock_from.download.assert_called_once_with("storage/path/video.mp4")
    # Storage delete should have been called for source video
    mock_from.remove.assert_called_once()


@pytest.mark.asyncio
async def test_bench_exercise_uses_elbow_angle_for_rep_detection() -> None:
    """Bench exercise uses elbow_angle (not hip_angle) for primary rep detection series (line 566)."""
    landmarks = _make_landmarks()
    reps = _make_reps()
    rep_metrics = _make_rep_metrics(reps)
    angle_ts = {
        "hip_angle": np.linspace(160, 80, _NUM_FRAMES, dtype=np.float32),
        "elbow_angle": np.linspace(160, 90, _NUM_FRAMES, dtype=np.float32),
    }

    analysis = _make_analysis()
    analysis.exercise_type = "bench"  # bench triggers elbow_angle primary key
    repo = AsyncMock()
    rep_metric_repo = AsyncMock()
    redis = MagicMock()
    write_heartbeat = AsyncMock()

    with (
        patch(f"{_PKG}.extract_landmarks", return_value=(landmarks, _FPS, _FRAME_WIDTH, _FRAME_HEIGHT)),
        patch(f"{_PKG}.run_quality_gates", return_value=_make_gate_result(passed=True)),
        patch(f"{_PKG}.compute_angle_timeseries", return_value=angle_ts),
        patch(f"{_PKG}.detect_reps", return_value=reps) as mock_detect_reps,
        patch(f"{_PKG}.extract_rep_metrics", return_value=rep_metrics),
        patch(f"{_PKG}.compute_session_confidence", return_value=0.8),
        patch(f"{_PKG}.compute_bar_path_from_landmarks", return_value=_make_bar_path()),
        patch(f"{_PKG}.generate_annotated_video", return_value="/tmp/annotated.mp4"),
        patch(f"{_PKG}.generate_angle_plot", return_value="/tmp/angles.png"),
        patch(f"{_PKG}.upload_artifact", new_callable=AsyncMock),
        patch(f"{_PKG}.get_artifact_storage_path", side_effect=lambda aid, fn: f"artifacts/{aid}/{fn}"),
        patch(f"{_PKG}.get_temp_dir", return_value="/tmp/spelix/test"),
        patch("os.path.isfile", return_value=False),
    ):
        await run_cv_pipeline(
            analysis=analysis,
            repo=repo,
            rep_metric_repo=rep_metric_repo,
            storage_client=None,
            redis=redis,
            write_heartbeat=write_heartbeat,
        )

    # detect_reps should have been called with the elbow_angle series
    assert mock_detect_reps.call_count == 1
    call_args = mock_detect_reps.call_args
    primary_series_arg = call_args[0][0]  # first positional arg is the primary series
    np.testing.assert_array_equal(primary_series_arg, angle_ts["elbow_angle"])
