"""
Unit tests for app/services/pipeline.py — run_cv_pipeline orchestration (B-053).

All CV functions are mocked; no real video or MediaPipe required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.cv.metric_extraction import RepMetrics
from app.cv.quality_gates import GateCheckResult, QualityGateResult
from app.cv.rep_detection import DetectedRep
from app.models.analysis import Analysis
from app.services.pipeline import PipelineResult, QualityGateRejection, run_cv_pipeline


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


def _make_analysis(status: str = "queued") -> Analysis:
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
        "lateral_deviation_px": 0.01,
        "vertical_range_px": 0.2,
        "path_consistency": 0.95,
    }


# ---------------------------------------------------------------------------
# Patch target constants
# ---------------------------------------------------------------------------

_PKG = "app.services.pipeline"


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
