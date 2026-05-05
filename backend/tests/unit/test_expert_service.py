"""Unit tests for ExpertService (M-09).

Coverage target: 31% -> ~65%.
FR-EXPV-02: review queue; FR-EXPV-03: anonymized detail; FR-EXPV-04: annotation;
FR-EXPV-07: golden label.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.expert_review import AnnotationCreate, ExpertAnalysisDetail, ExpertQueueItem
from app.services.expert import ExpertService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_service():
    analysis_repo = AsyncMock()
    review_repo = AsyncMock()
    rag_doc_repo = AsyncMock()
    service = ExpertService(
        analysis_repo=analysis_repo,
        review_repo=review_repo,
        rag_doc_repo=rag_doc_repo,
    )
    return service, analysis_repo, review_repo, rag_doc_repo


def _make_mock_analysis(**overrides):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.user_id = uuid.uuid4()
    a.exercise_type = "squat"
    a.exercise_variant = None
    a.confidence_score = 0.85
    a.form_score_overall = 7.5
    a.flagged_for_review = False
    a.is_golden_dataset = False
    a.created_at = datetime(2026, 4, 20)
    a.summary_json = {}
    a.quality_gate_result = {}
    a.form_score_safety = 8.0
    a.form_score_technique = 7.0
    a.form_score_path_balance = 7.5
    a.form_score_control = 7.0
    a.rep_metrics = []
    a.coaching_result = None
    a.retrieval_context = None
    a.eval_scores = None
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


# ---------------------------------------------------------------------------
# get_review_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_review_queue_all_returns_items():
    """queue_type='all' calls list_all and wraps results as ExpertQueueItem."""
    service, analysis_repo, review_repo, _ = _make_service()
    mock_analysis = _make_mock_analysis()
    analysis_repo.list_all.return_value = [mock_analysis]
    review_repo.count_by_analysis.return_value = 3

    items = await service.get_review_queue(queue_type="all", limit=10, offset=0)

    analysis_repo.list_all.assert_awaited_once_with(
        limit=10, offset=0, status_filter="completed"
    )
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, ExpertQueueItem)
    assert item.analysis_id == mock_analysis.id
    assert item.exercise_type == "squat"
    assert item.confidence_score == 0.85
    assert item.annotation_count == 3
    assert item.flagged_for_review is False


@pytest.mark.asyncio
async def test_get_review_queue_flagged_calls_list_flagged():
    """queue_type='flagged' calls list_flagged, not list_all."""
    service, analysis_repo, review_repo, _ = _make_service()
    mock_analysis = _make_mock_analysis(flagged_for_review=True)
    analysis_repo.list_flagged.return_value = [mock_analysis]
    review_repo.count_by_analysis.return_value = 0

    items = await service.get_review_queue(queue_type="flagged", limit=5, offset=0)

    analysis_repo.list_flagged.assert_awaited_once_with(limit=5, offset=0)
    analysis_repo.list_all.assert_not_called()
    assert len(items) == 1
    assert items[0].flagged_for_review is True


@pytest.mark.asyncio
async def test_get_review_queue_low_quality_calls_get_below_confidence():
    """queue_type='low_quality' calls get_below_confidence with threshold 0.5."""
    service, analysis_repo, review_repo, _ = _make_service()
    mock_analysis = _make_mock_analysis(confidence_score=0.45)
    analysis_repo.get_below_confidence.return_value = [mock_analysis]
    review_repo.count_by_analysis.return_value = 0

    items = await service.get_review_queue(queue_type="low_quality", limit=20, offset=0)

    analysis_repo.get_below_confidence.assert_awaited_once_with(threshold=0.5)
    assert len(items) == 1
    assert items[0].confidence_score == 0.45


@pytest.mark.asyncio
async def test_get_review_queue_empty_returns_empty_list():
    """Returns empty list when no analyses are found."""
    service, analysis_repo, review_repo, _ = _make_service()
    analysis_repo.list_all.return_value = []

    items = await service.get_review_queue(queue_type="all")

    assert items == []
    review_repo.count_by_analysis.assert_not_called()


# ---------------------------------------------------------------------------
# get_analysis_detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_analysis_detail_not_found_returns_none():
    """Returns None when analysis does not exist (FR-EXPV-03)."""
    service, analysis_repo, _, _ = _make_service()
    analysis_repo.get_by_id_with_relations.return_value = None

    result = await service.get_analysis_detail(uuid.uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_analysis_detail_does_not_contain_user_id():
    """ExpertAnalysisDetail must never expose user_id (FR-EXPV-03 anonymization)."""
    service, analysis_repo, _, _ = _make_service()
    mock_analysis = _make_mock_analysis()
    analysis_repo.get_by_id_with_relations.return_value = mock_analysis

    detail = await service.get_analysis_detail(mock_analysis.id)

    assert detail is not None
    assert isinstance(detail, ExpertAnalysisDetail)
    # user_id must not appear on the schema at all
    assert not hasattr(detail, "user_id")
    assert "user_id" not in ExpertAnalysisDetail.model_fields


@pytest.mark.asyncio
async def test_get_analysis_detail_includes_all_score_fields():
    """All four dimension scores and overall must be present in detail response."""
    service, analysis_repo, _, _ = _make_service()
    mock_analysis = _make_mock_analysis()
    analysis_repo.get_by_id_with_relations.return_value = mock_analysis

    detail = await service.get_analysis_detail(mock_analysis.id)

    assert detail is not None
    assert detail.form_score_safety == 8.0
    assert detail.form_score_technique == 7.0
    assert detail.form_score_path_balance == 7.5
    assert detail.form_score_control == 7.0
    assert detail.form_score_overall == 7.5


@pytest.mark.asyncio
async def test_get_analysis_detail_maps_basic_fields():
    """id, exercise_type, confidence_score, flagged, golden, created_at are mapped."""
    service, analysis_repo, _, _ = _make_service()
    mock_analysis = _make_mock_analysis(
        exercise_type="bench", confidence_score=0.72, flagged_for_review=True
    )
    analysis_repo.get_by_id_with_relations.return_value = mock_analysis

    detail = await service.get_analysis_detail(mock_analysis.id)

    assert detail.id == mock_analysis.id
    assert detail.exercise_type == "bench"
    assert detail.confidence_score == 0.72
    assert detail.flagged_for_review is True
    assert detail.is_golden_dataset is False
    assert detail.created_at == datetime(2026, 4, 20)


# ---------------------------------------------------------------------------
# submit_annotation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_annotation_creates_review():
    """submit_annotation calls review_repo.create and returns the result (FR-EXPV-04)."""
    service, analysis_repo, review_repo, _ = _make_service()
    analysis_id = uuid.uuid4()
    annotator_id = uuid.uuid4()
    mock_created = MagicMock()
    review_repo.create.return_value = mock_created

    data = AnnotationCreate(
        issues_identified={"knee_valgus": "mild"},
        coaching_quality_score=7.5,
        is_golden_label=False,
    )

    result = await service.submit_annotation(analysis_id, annotator_id, data)

    review_repo.create.assert_awaited_once()
    # Verify the AnalysisExpertReview passed to create carries correct IDs
    created_arg = review_repo.create.call_args[0][0]
    assert created_arg.analysis_id == analysis_id
    assert created_arg.annotator_id == annotator_id
    assert created_arg.coaching_quality_score == 7.5
    assert result is mock_created


@pytest.mark.asyncio
async def test_submit_annotation_without_golden_label_does_not_update_analysis():
    """When is_golden_label=False, analysis_repo.update is NOT called."""
    service, analysis_repo, review_repo, _ = _make_service()
    review_repo.create.return_value = MagicMock()

    data = AnnotationCreate(is_golden_label=False)
    await service.submit_annotation(uuid.uuid4(), uuid.uuid4(), data)

    analysis_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_submit_annotation_with_golden_label_marks_analysis():
    """When is_golden_label=True, analysis.is_golden_dataset is set and update called (FR-EXPV-07)."""
    service, analysis_repo, review_repo, _ = _make_service()
    mock_analysis = _make_mock_analysis()
    analysis_repo.get_by_id.return_value = mock_analysis
    review_repo.create.return_value = MagicMock()

    data = AnnotationCreate(is_golden_label=True)
    await service.submit_annotation(mock_analysis.id, uuid.uuid4(), data)

    assert mock_analysis.is_golden_dataset is True
    analysis_repo.update.assert_awaited_once_with(mock_analysis)


@pytest.mark.asyncio
async def test_submit_annotation_golden_label_analysis_not_found_does_not_raise():
    """Golden label side-effect is skipped gracefully when analysis is missing."""
    service, analysis_repo, review_repo, _ = _make_service()
    analysis_repo.get_by_id.return_value = None
    review_repo.create.return_value = MagicMock()

    data = AnnotationCreate(is_golden_label=True)
    # Must not raise even when analysis lookup returns None
    await service.submit_annotation(uuid.uuid4(), uuid.uuid4(), data)

    analysis_repo.update.assert_not_called()


# ---------------------------------------------------------------------------
# set_golden_label
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_golden_label_analysis_not_found_returns_empty_dict():
    """Returns {} when analysis does not exist (FR-EXPV-07)."""
    service, analysis_repo, _, _ = _make_service()
    analysis_repo.get_by_id.return_value = None

    result = await service.set_golden_label(uuid.uuid4(), is_golden=True)

    assert result == {}
    analysis_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_set_golden_label_sets_flag_and_returns():
    """Returns id + is_golden_dataset after updating the analysis (FR-EXPV-07)."""
    service, analysis_repo, _, _ = _make_service()
    mock_analysis = _make_mock_analysis()
    mock_analysis.is_golden_dataset = False
    analysis_repo.get_by_id.return_value = mock_analysis

    # Simulate that update flips the flag (MagicMock attribute is already set above)
    result = await service.set_golden_label(mock_analysis.id, is_golden=True)

    assert mock_analysis.is_golden_dataset is True
    analysis_repo.update.assert_awaited_once_with(mock_analysis)
    assert result["id"] == mock_analysis.id
    assert result["is_golden_dataset"] is True


@pytest.mark.asyncio
async def test_set_golden_label_can_unset_flag():
    """set_golden_label(is_golden=False) clears the golden flag."""
    service, analysis_repo, _, _ = _make_service()
    mock_analysis = _make_mock_analysis()
    mock_analysis.is_golden_dataset = True
    analysis_repo.get_by_id.return_value = mock_analysis

    result = await service.set_golden_label(mock_analysis.id, is_golden=False)

    assert mock_analysis.is_golden_dataset is False
    assert result["is_golden_dataset"] is False


@pytest.mark.asyncio
async def test_get_review_queue_first_run_calls_get_first_run_analyses():
    """queue_type='first_run' calls _get_first_run_analyses (covers line 51, 165-173)."""
    service, analysis_repo, review_repo, _ = _make_service()
    # _get_first_run_analyses calls list_all then filters by count=0
    mock_analysis_no_annotations = _make_mock_analysis()
    mock_analysis_with_annotations = _make_mock_analysis()

    analysis_repo.list_all.return_value = [
        mock_analysis_no_annotations,
        mock_analysis_with_annotations,
    ]
    # First analysis has 0 annotations, second has 2
    review_repo.count_by_analysis.side_effect = [
        0,  # for the inner loop in _get_first_run_analyses
        2,  # for the inner loop in _get_first_run_analyses
        0,  # for the outer loop in get_review_queue (annotation_count)
    ]

    items = await service.get_review_queue(queue_type="first_run", limit=20, offset=0)

    # list_all should be called (for the 200-limit scan in _get_first_run_analyses)
    analysis_repo.list_all.assert_awaited()
    # Only the analysis with 0 annotations passes the filter
    assert len(items) == 1
    assert items[0].analysis_id == mock_analysis_no_annotations.id


@pytest.mark.asyncio
async def test_get_analysis_detail_includes_rep_metrics_and_coaching_result():
    """When analysis has rep_metrics and coaching_result, they appear in the detail (lines 85-86, 94-95)."""
    service, analysis_repo, _, _ = _make_service()

    # Create rep metrics with real values
    mock_rm = MagicMock()
    mock_rm.rep_index = 0
    mock_rm.metrics_json = {"depth_angle": 92.0}
    mock_rm.confidence_score = 0.88

    # Create coaching result
    mock_cr = MagicMock()
    mock_cr.structured_output_json = {"summary": "good squat"}
    mock_cr.agent_trace_json = {"mode": "deterministic"}

    mock_analysis = _make_mock_analysis(
        rep_metrics=[mock_rm],
        coaching_result=mock_cr,
    )
    analysis_repo.get_by_id_with_relations.return_value = mock_analysis

    detail = await service.get_analysis_detail(mock_analysis.id)

    assert detail is not None
    # rep_metrics should be populated
    assert len(detail.rep_metrics) == 1
    assert detail.rep_metrics[0]["rep_index"] == 0
    assert detail.rep_metrics[0]["metrics_json"] == {"depth_angle": 92.0}
    # coaching_result should be populated
    assert detail.coaching_result is not None
    assert detail.coaching_result["structured_output_json"] == {"summary": "good squat"}
    assert detail.coaching_result["agent_trace_json"] == {"mode": "deterministic"}
