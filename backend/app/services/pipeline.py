"""CV pipeline orchestration — full analysis pipeline (B-022).

Executes the complete CV pipeline: download → quality gates → pose extraction →
smoothing → rep detection → metric extraction → confidence scoring → barbell
detection → artifact generation → upload → cleanup.

All CPU-bound work runs via ``loop.run_in_executor(None, fn)``.

Requirements: FR-UPLD-15, FR-UPLD-18, all FR-CVPL, all FR-REPM, all FR-BDET
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import update as sa_update

from app.db import async_session
from app.cv.artifact_generation import (
    generate_angle_plot,
    generate_annotated_video,
    get_artifact_storage_path,
    get_temp_dir,
    upload_artifact,
)
from app.cv.barbell_detection import (
    compute_bar_path,
    compute_bar_path_from_landmarks,
    track_barbell_from_video,
)
from app.cv.confidence import (
    compute_session_confidence,
)
from app.cv.metric_extraction import extract_rep_metrics
from app.cv.pose_extraction import extract_landmarks
from app.cv.quality_gates import run_quality_gates
from app.cv.rep_detection import detect_reps
from app.cv.signal_processing import compute_angle_timeseries
from app.cv.video_probe import probe_duration_seconds
from app.models.analysis import Analysis
from app.models.rep_metric import RepMetric
from app.repositories.analysis import AnalysisRepository
from app.repositories.rep_metric import RepMetricRepository
from app.services.status import transition
from app.services.timing import StageTimer

logger = logging.getLogger(__name__)

# Storage bucket name
_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "videos")

# D-035: hard cap on clip duration to avoid timeout DoS via long uploads.
# Frontend enforces the same cap; this is defense-in-depth.
_MAX_DURATION_FREE_TIER_S = 60.0
_MAX_DURATION_EXTENDED_S = 120.0


async def _persist_timing_telemetry(
    analysis_id: UUID, timing_dict: dict[str, Any]
) -> None:
    """Write timing_json in a fresh session that commits immediately.

    D-035 fix: the main pipeline session rolls back on timeout/error (see
    analysis_worker.py::process_analysis except handler), which wipes every
    in-session write — including any telemetry we meant to persist. Using
    a dedicated short-lived session here means per-stage timing survives
    that rollback, which is the entire point of the early-write
    instrumentation.
    """
    async with async_session() as session:
        await session.execute(
            sa_update(Analysis)
            .where(Analysis.id == analysis_id)
            .values(timing_json=timing_dict)
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Pipeline dataclass for intermediate results
# ---------------------------------------------------------------------------


class PipelineResult:
    """Holds intermediate CV pipeline results for downstream consumption."""

    __slots__ = (
        "landmarks_per_frame",
        "fps",
        "frame_width",
        "frame_height",
        "angle_timeseries",
        "reps",
        "rep_metrics",
        "session_confidence",
        "confidence_results",
        "score_result",
        "bar_path",
        "keyframes",
        "annotated_video_storage_path",
        "plot_storage_path",
        "detection_result",
    )

    def __init__(self) -> None:
        self.landmarks_per_frame: list[np.ndarray] = []
        self.fps: float = 30.0
        self.frame_width: int = 0
        self.frame_height: int = 0
        self.angle_timeseries: dict[str, np.ndarray] = {}
        self.reps: list = []
        self.rep_metrics: list = []
        self.session_confidence: float = 0.0
        self.confidence_results: list = []
        self.score_result: Any = None
        self.bar_path: dict | None = None
        self.keyframes: list = []
        self.annotated_video_storage_path: str | None = None
        self.plot_storage_path: str | None = None
        self.detection_result: Any = None


# ---------------------------------------------------------------------------
# Video download
# ---------------------------------------------------------------------------


async def download_video(
    storage_client: Any,
    bucket: str,
    video_path: str,
    local_path: str,
) -> str:
    """Download video from Supabase Storage to local path.

    Parameters
    ----------
    storage_client:
        Supabase client.
    bucket:
        Storage bucket name.
    video_path:
        Storage path of the video.
    local_path:
        Local destination path.

    Returns
    -------
    str
        The *local_path*.
    """
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    data = await storage_client.storage.from_(bucket).download(video_path)
    with open(local_path, "wb") as f:
        f.write(data)
    return local_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aggregate_rep_metrics(
    rep_metrics: list,
    reps: list,
    session_confidence: float,
) -> dict[str, float]:
    """Flatten per-rep metrics into a single dict for scoring.

    Takes the mean of each metric key across all reps. Also adds:
    - confidence_score: session-level confidence
    - rep_duration_std: std dev of rep durations (for ControlScore)
    - depth_angle_std: std dev of depth angles (for TechniqueScore)
    """
    if not rep_metrics:
        return {"confidence_score": session_confidence}

    # Collect all metric keys and their values across reps
    all_keys: dict[str, list[float]] = {}
    for rm in rep_metrics:
        for k, v in rm.metrics.items():
            if isinstance(v, (int, float)):
                all_keys.setdefault(k, []).append(float(v))

    # Mean of each metric
    result: dict[str, float] = {}
    for k, values in all_keys.items():
        result[k] = sum(values) / len(values) if values else 0.0

    # Add std dev for control/technique scoring
    if "rep_duration_s" in all_keys and len(all_keys["rep_duration_s"]) > 1:
        vals = all_keys["rep_duration_s"]
        mean = sum(vals) / len(vals)
        result["rep_duration_std"] = (
            sum((v - mean) ** 2 for v in vals) / len(vals)
        ) ** 0.5

    if "depth_angle" in all_keys and len(all_keys["depth_angle"]) > 1:
        vals = all_keys["depth_angle"]
        mean = sum(vals) / len(vals)
        result["depth_angle_std"] = (
            sum((v - mean) ** 2 for v in vals) / len(vals)
        ) ** 0.5

    result["confidence_score"] = session_confidence
    return result


# ---------------------------------------------------------------------------
# Frame sampling for GPT-4o fallback (FR-XDET-04)
# ---------------------------------------------------------------------------

_FALLBACK_CONFIDENCE_THRESHOLD = 0.7


def _extract_sample_frames_b64(
    video_path: str,
    count: int = 3,
) -> list[str]:
    """Extract ``count`` evenly-spaced frames from the video as base64 JPEG.

    Used to feed GPT-4o ``classify_exercise`` when the heuristic confidence
    falls below the threshold.  Runs in an executor (CPU-bound).
    """
    import base64

    import cv2

    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []

    indices = [int(i * (total - 1) / max(count - 1, 1)) for i in range(count)]
    result: list[str] = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        result.append(base64.b64encode(buf.tobytes()).decode())
    cap.release()
    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def run_cv_pipeline(
    analysis: Analysis,
    repo: AnalysisRepository,
    rep_metric_repo: RepMetricRepository,
    storage_client: Any,
    redis: Any,
    write_heartbeat: Any,
    openai_client: Any = None,
) -> PipelineResult:
    """Execute the full CV pipeline for an analysis.

    Status transitions handled:
      queued → quality_gate_pending → (quality_gate_rejected | processing)

    Parameters
    ----------
    analysis:
        The Analysis ORM object (must be in ``queued`` status).
    repo:
        Analysis repository for status updates.
    rep_metric_repo:
        RepMetric repository for batch insert.
    storage_client:
        Supabase client for Storage operations (or None in tests).
    redis:
        Redis connection for heartbeat writes.
    write_heartbeat:
        Async callable to write heartbeat.

    Returns
    -------
    PipelineResult
        Intermediate results for coaching stage consumption.

    Raises
    ------
    QualityGateRejection
        If the video fails quality gates.
    """
    loop = asyncio.get_event_loop()
    result = PipelineResult()
    timer = StageTimer()
    analysis_id = analysis.id
    exercise_type = analysis.exercise_type
    exercise_variant = analysis.exercise_variant

    # The row is already at ``quality_gate_pending`` when the worker picks
    # up the job — ``AnalysisService.start_analysis`` performs that
    # transition before enqueueing. Earlier versions of this pipeline did
    # ``transition(analysis.status, "quality_gate_pending")`` here, which
    # was a no-op self-transition that the status guard correctly rejected
    # the moment uploads actually started reaching the worker. The pipeline
    # now picks up where ``start_analysis`` left off and writes the
    # initial heartbeat to indicate progress.
    await write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 1: Download video from Supabase Storage
    # ------------------------------------------------------------------ #
    tmp_dir = get_temp_dir(analysis_id)
    video_local = os.path.join(tmp_dir, f"{analysis_id}.mp4")

    with timer.stage("download"):
        if storage_client is not None and analysis.video_path:
            await download_video(
                storage_client, _BUCKET, analysis.video_path, video_local,
            )
        else:
            # In test mode, video_path may already be a local path
            if analysis.video_path and os.path.isfile(analysis.video_path):
                video_local = analysis.video_path

    # D-035 Priority 1 + rollback fix: use a fresh session that commits
    # immediately so per-stage telemetry survives the main pipeline
    # session's rollback on timeout (see analysis_worker.py error handler).
    analysis.timing_json = timer.as_dict()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    # ------------------------------------------------------------------ #
    # D-035: defense-in-depth duration check after download
    # ------------------------------------------------------------------ #
    with timer.stage("duration_probe"):
        duration_s = await loop.run_in_executor(
            None, probe_duration_seconds, video_local,
        )
    cap_s = (
        _MAX_DURATION_EXTENDED_S
        if getattr(analysis, "extended_mode", False)
        else _MAX_DURATION_FREE_TIER_S
    )
    if duration_s > cap_s:
        analysis.quality_gate_result = {
            "passed": False,
            "status": "rejected",
            "checks": [
                {
                    "passed": False,
                    "name": "duration",
                    "level": "error",
                    "metric_value": duration_s,
                    "threshold": cap_s,
                    "user_message": (
                        f"Video is {duration_s:.1f}s — please trim to under {cap_s:.0f}s. "
                        "Long clips can take many minutes to analyse on the current tier."
                    ),
                }
            ],
        }
        analysis.status = transition(analysis.status, "quality_gate_rejected")
        analysis.timing_json = timer.as_dict()
        await repo.update(analysis)
        await repo.db.commit()
        raise QualityGateRejection(
            f"Clip duration {duration_s:.1f}s exceeds {cap_s:.0f}s cap"
        )

    analysis.timing_json = timer.as_dict()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    # ------------------------------------------------------------------ #
    # Step 2: Pose extraction (CPU-bound)
    # ------------------------------------------------------------------ #
    with timer.stage("extract_landmarks"):
        landmarks_per_frame, fps, frame_width, frame_height = await loop.run_in_executor(
            None, extract_landmarks, video_local,
        )
    result.landmarks_per_frame = landmarks_per_frame
    result.fps = fps
    result.frame_width = frame_width
    result.frame_height = frame_height

    analysis.timing_json = timer.as_dict()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    await write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 2b: Exercise auto-detection (FR-XDET-03, FR-XDET-04)
    # ------------------------------------------------------------------ #
    from app.cv.exercise_detection import DetectionResult, detect_exercise_heuristic

    with timer.stage("exercise_detection"):
        detection = await loop.run_in_executor(
            None, detect_exercise_heuristic, landmarks_per_frame,
        )
        logger.info(
            "Heuristic detection: %s (conf=%.2f) for analysis %s",
            detection.detected_type, detection.confidence, analysis_id,
        )

        # GPT-4o vision fallback when heuristic confidence is low (FR-XDET-04)
        if detection.confidence < _FALLBACK_CONFIDENCE_THRESHOLD and openai_client is not None:
            try:
                from app.services.keyframe_analysis import KeyframeAnalysisService

                frame_images = await loop.run_in_executor(
                    None, _extract_sample_frames_b64, video_local, 3,
                )
                if frame_images:
                    kf_svc = KeyframeAnalysisService(openai_client)
                    classification = await kf_svc.classify_exercise(
                        frame_images_b64=frame_images,
                    )
                    detection = DetectionResult(
                        detected_type=classification.exercise_type,  # type: ignore[arg-type]
                        detected_variant=classification.exercise_variant,
                        confidence=classification.confidence,
                        method="vision_fallback",
                        details={
                            "reasoning": classification.reasoning,
                            "heuristic_confidence": detection.confidence,
                            "heuristic_type": detection.detected_type,
                        },
                    )
                    logger.info(
                        "GPT-4o fallback: %s (conf=%.2f) for analysis %s",
                        detection.detected_type, detection.confidence, analysis_id,
                    )
            except Exception:
                logger.warning(
                    "GPT-4o exercise classification failed for %s — using heuristic result",
                    analysis_id,
                    exc_info=True,
                )

    result.detection_result = detection

    # Store detection result as JSONB on the analysis for FR-XDET-07
    analysis.detection_result = {
        "detected_type": detection.detected_type,
        "detected_variant": detection.detected_variant,
        "confidence": detection.confidence,
        "method": detection.method,
        "details": detection.details,
    }
    analysis.timing_json = timer.as_dict()
    await repo.update(analysis)
    await repo.db.commit()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    # ------------------------------------------------------------------ #
    # Step 3: Quality gates
    # ------------------------------------------------------------------ #
    with timer.stage("quality_gates"):
        gate_result = await loop.run_in_executor(
            None,
            run_quality_gates,
            landmarks_per_frame,
            frame_width,
            frame_height,
            video_local,
            exercise_type,
        )

    analysis.quality_gate_result = {
        "passed": gate_result.passed,
        "status": gate_result.status,
        "checks": [
            {
                "passed": c.passed,
                "name": c.name,
                "level": c.level,
                "metric_value": c.metric_value,
                "threshold": c.threshold,
                "user_message": c.user_message,
            }
            for c in gate_result.checks
        ],
    }
    analysis.timing_json = timer.as_dict()
    await repo.update(analysis)
    await repo.db.commit()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    if not gate_result.passed:
        analysis.status = transition(analysis.status, "quality_gate_rejected")
        analysis.timing_json = timer.as_dict()
        await repo.update(analysis)
        await repo.db.commit()
        raise QualityGateRejection(
            f"Quality gate rejected: {gate_result.status}"
        )

    # ------------------------------------------------------------------ #
    # Transition: quality_gate_pending → processing
    # ------------------------------------------------------------------ #
    analysis.status = transition(analysis.status, "processing")
    analysis.timing_json = timer.as_dict()
    await repo.update(analysis)
    await repo.db.commit()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())
    await write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 4: Angle timeseries + smoothing (CPU-bound)
    # ------------------------------------------------------------------ #
    with timer.stage("angle_timeseries"):
        angle_timeseries = await loop.run_in_executor(
            None, compute_angle_timeseries, landmarks_per_frame, exercise_type,
        )
    result.angle_timeseries = angle_timeseries
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    # ------------------------------------------------------------------ #
    # Step 5: Rep detection (CPU-bound)
    # ------------------------------------------------------------------ #
    # Get the primary angle series for rep detection
    if exercise_type.lower() == "bench":
        primary_key = "elbow_angle"
    else:
        primary_key = "hip_angle"

    primary_series = angle_timeseries.get(primary_key, np.array([]))

    with timer.stage("rep_detection"):
        reps = await loop.run_in_executor(
            None,
            detect_reps,
            primary_series,
            landmarks_per_frame,
            exercise_type,
            exercise_variant,
            fps,
        )
    result.reps = reps
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    await write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 6: Per-rep metric extraction (CPU-bound)
    # ------------------------------------------------------------------ #
    with timer.stage("metric_extraction"):
        rep_metrics = await loop.run_in_executor(
            None,
            extract_rep_metrics,
            reps,
            landmarks_per_frame,
            angle_timeseries,
            exercise_type,
            exercise_variant,
            fps,
        )
    result.rep_metrics = rep_metrics
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    # ------------------------------------------------------------------ #
    # Step 7: Tier 1–5 confidence scoring (FR-CVPL-20–25, replaces Phase 0)
    # ------------------------------------------------------------------ #
    from app.config import ThresholdConfig
    from app.cv.confidence import compute_confidence_result

    cfg = ThresholdConfig()
    with timer.stage("confidence_scoring"):
        confidence_results = []
        for rm in rep_metrics:
            # Find depth frame: frame with min primary angle within the rep range
            primary_angles = primary_series[rm.start_frame:rm.end_frame + 1]
            if len(primary_angles) > 0:
                depth_frame_idx = rm.start_frame + int(np.argmin(primary_angles))
            else:
                depth_frame_idx = (rm.start_frame + rm.end_frame) // 2

            conf_result = compute_confidence_result(
                landmarks_per_frame=landmarks_per_frame,
                start_frame=rm.start_frame,
                end_frame=rm.end_frame,
                exercise_type=exercise_type,
                depth_frame_idx=depth_frame_idx,
                cfg=cfg,
                rep_index=rm.rep_index,
            )
            confidence_results.append(conf_result)
            # Backfill DetectedRep.confidence_score with Tier 5 value
            if rm.rep_index < len(reps):
                reps[rm.rep_index].confidence_score = conf_result.tier5

        result.confidence_results = confidence_results
        rep_confidences = [cr.tier5 for cr in confidence_results]
        session_confidence = compute_session_confidence(rep_confidences)
        result.session_confidence = session_confidence

    analysis.confidence_score = session_confidence
    analysis.timing_json = timer.as_dict()
    await repo.update(analysis)
    await repo.db.commit()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    # ------------------------------------------------------------------ #
    # Step 8: Write rep metrics to DB
    # ------------------------------------------------------------------ #
    if rep_metrics:
        db_metrics = [
            RepMetric(
                analysis_id=analysis_id,
                rep_index=rm.rep_index,
                start_frame=rm.start_frame,
                end_frame=rm.end_frame,
                confidence_score=reps[rm.rep_index].confidence_score if rm.rep_index < len(reps) else None,
                metrics_json=rm.metrics,
            )
            for rm in rep_metrics
        ]
        await rep_metric_repo.create_batch(db_metrics)

    await write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 8b: Keyframe extraction (FR-AICP-01)
    # ------------------------------------------------------------------ #
    from app.cv.keyframe_extraction import extract_keyframes

    with timer.stage("keyframe_extraction"):
        keyframes = await loop.run_in_executor(
            None, extract_keyframes, video_local, reps, primary_series,
        )
    result.keyframes = keyframes
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    await write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 9: Barbell detection (pixel-based, with landmark fallback)
    # Streams frames from disk one at a time to avoid ~8.4 GB peak on
    # 1080p clips. See D-034 / ADR-056.
    # ------------------------------------------------------------------ #
    with timer.stage("barbell_tracking"):
        centroids = await loop.run_in_executor(
            None, track_barbell_from_video, video_local,
        )

        # Determine detection rate
        detected_count = sum(1 for c in centroids if c is not None)
        detection_rate = detected_count / len(centroids) if centroids else 0.0

        if detection_rate > 0.50:
            bar_path = await loop.run_in_executor(
                None,
                compute_bar_path,
                centroids,
                result.frame_width,
                result.frame_height,
            )
        else:
            logger.warning(
                "Barbell detected in only %.0f%% of frames for %s — using landmark proxy",
                detection_rate * 100,
                analysis_id,
            )
            bar_path = await loop.run_in_executor(
                None,
                compute_bar_path_from_landmarks,
                landmarks_per_frame,
                exercise_type,
            )
    result.bar_path = bar_path
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    # ------------------------------------------------------------------ #
    # Step 9b: Form scoring (FR-SCOR-01–08) — needs bar_path from Step 9
    # ------------------------------------------------------------------ #
    from app.cv.scoring import OverallFormScore

    with timer.stage("form_scoring"):
        scorer = OverallFormScore()
        # Aggregate per-rep metrics into a single dict (mean across reps)
        agg_metrics = _aggregate_rep_metrics(rep_metrics, reps, session_confidence)
        score_result = scorer.compute(agg_metrics, bar_path, cfg, exercise_type)
    result.score_result = score_result

    # Write form scores to analysis row
    safety_dim = score_result.get_dimension("safety")
    technique_dim = score_result.get_dimension("technique")
    path_dim = score_result.get_dimension("path_balance")
    control_dim = score_result.get_dimension("control")

    analysis.form_score_safety = safety_dim.score if safety_dim else None
    analysis.form_score_technique = technique_dim.score if technique_dim else None
    analysis.form_score_path_balance = path_dim.score if path_dim else None
    analysis.form_score_control = control_dim.score if control_dim else None
    analysis.form_score_overall = score_result.overall
    analysis.timing_json = timer.as_dict()
    await repo.update(analysis)
    await repo.db.commit()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    await write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 10: Artifact generation (CPU-bound)
    # ------------------------------------------------------------------ #
    annotated_path = os.path.join(tmp_dir, "annotated.mp4")
    plot_path = os.path.join(tmp_dir, "angles.png")

    with timer.stage("generate_annotated_video"):
        await loop.run_in_executor(
            None,
            generate_annotated_video,
            video_local,
            landmarks_per_frame,
            reps,
            exercise_type,
            angle_timeseries,
            annotated_path,
        )
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    with timer.stage("generate_angle_plot"):
        await loop.run_in_executor(
            None,
            generate_angle_plot,
            angle_timeseries,
            fps,
            exercise_type,
            plot_path,
        )
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    await write_heartbeat(redis)

    # ------------------------------------------------------------------ #
    # Step 11: Upload artifacts to Supabase Storage
    # ------------------------------------------------------------------ #
    if storage_client is not None:
        with timer.stage("upload_artifacts"):
            annotated_storage = get_artifact_storage_path(analysis_id, "annotated.mp4")
            plot_storage = get_artifact_storage_path(analysis_id, "angles.png")

            await upload_artifact(storage_client, _BUCKET, annotated_path, annotated_storage)
            await upload_artifact(storage_client, _BUCKET, plot_path, plot_storage)

            analysis.annotated_video_path = annotated_storage
            analysis.plot_path = plot_storage

        analysis.timing_json = timer.as_dict()
        await repo.update(analysis)
        await repo.db.commit()
        await _persist_timing_telemetry(analysis.id, timer.as_dict())

        result.annotated_video_storage_path = annotated_storage
        result.plot_storage_path = plot_storage

    # ------------------------------------------------------------------ #
    # Step 12: Delete video from Storage (lifecycle: after pipeline)
    # ------------------------------------------------------------------ #
    if storage_client is not None and analysis.video_path:
        try:
            await storage_client.storage.from_(_BUCKET).remove([analysis.video_path])
        except Exception as e:
            logger.warning("Failed to delete source video from Storage: %s", e)

    # Local temp files are cleaned up by the worker's finally block,
    # not here — PDF generation needs the local plot file after pipeline returns.

    analysis.timing_json = timer.as_dict()
    await repo.update(analysis)
    await repo.db.commit()
    await _persist_timing_telemetry(analysis.id, timer.as_dict())

    return result


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class QualityGateRejection(Exception):
    """Raised when a video fails quality gates — not an error, expected flow."""

    pass
