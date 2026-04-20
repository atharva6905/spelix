"""Expert reviewer service — business logic for expert validation system.

FR-EXPV-01 through FR-EXPV-07.
Anonymization: never returns user_id in analysis responses.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.models.analysis import Analysis
from app.models.analysis_expert_review import AnalysisExpertReview
from app.repositories.analysis import AnalysisRepository
from app.repositories.analysis_expert_review import AnalysisExpertReviewRepository
from app.repositories.rag_document import RagDocumentRepository
from app.schemas.expert_review import AnnotationCreate, ExpertAnalysisDetail, ExpertQueueItem

logger = logging.getLogger(__name__)


class ExpertService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        review_repo: AnalysisExpertReviewRepository,
        rag_doc_repo: RagDocumentRepository,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._review_repo = review_repo
        self._rag_doc_repo = rag_doc_repo

    async def get_review_queue(
        self,
        *,
        queue_type: str = "all",
        limit: int = 20,
        offset: int = 0,
    ) -> list[ExpertQueueItem]:
        """Build the expert review queue (FR-EXPV-02).

        queue_type: flagged | low_quality | first_run | all
        """
        if queue_type == "flagged":
            analyses = await self._analysis_repo.list_flagged(limit=limit, offset=offset)
        elif queue_type == "low_quality":
            analyses = await self._analysis_repo.get_below_confidence(threshold=0.5)
            analyses = analyses[offset : offset + limit]
        elif queue_type == "first_run":
            analyses = await self._get_first_run_analyses(limit=limit, offset=offset)
        else:
            analyses = await self._analysis_repo.list_all(
                limit=limit, offset=offset, status_filter="completed"
            )

        items = []
        for a in analyses:
            count = await self._review_repo.count_by_analysis(a.id)
            items.append(
                ExpertQueueItem(
                    analysis_id=a.id,
                    exercise_type=a.exercise_type,
                    exercise_variant=getattr(a, "exercise_variant", None),
                    confidence_score=a.confidence_score,
                    form_score_overall=getattr(a, "form_score_overall", None),
                    flagged_for_review=a.flagged_for_review,
                    created_at=a.created_at,
                    annotation_count=count,
                )
            )
        return items

    async def get_analysis_detail(self, analysis_id: uuid.UUID) -> ExpertAnalysisDetail | None:
        """Get anonymized analysis detail (FR-EXPV-03).

        Intentionally excludes user_id — anonymization is enforced here.
        """
        analysis = await self._analysis_repo.get_by_id_with_relations(analysis_id)
        if analysis is None:
            return None

        rep_metrics_list = []
        if hasattr(analysis, "rep_metrics") and analysis.rep_metrics:
            for rm in analysis.rep_metrics:
                rep_metrics_list.append({
                    "rep_index": rm.rep_index,
                    "metrics_json": rm.metrics_json,
                    "confidence_score": rm.confidence_score,
                })

        coaching_result_dict = None
        if hasattr(analysis, "coaching_result") and analysis.coaching_result:
            cr = analysis.coaching_result
            coaching_result_dict = {
                "structured_output_json": cr.structured_output_json,
                "agent_trace_json": getattr(cr, "agent_trace_json", None),
            }

        return ExpertAnalysisDetail(
            id=analysis.id,
            exercise_type=analysis.exercise_type,
            exercise_variant=getattr(analysis, "exercise_variant", None),
            confidence_score=analysis.confidence_score,
            form_score_safety=getattr(analysis, "form_score_safety", None),
            form_score_technique=getattr(analysis, "form_score_technique", None),
            form_score_path_balance=getattr(analysis, "form_score_path_balance", None),
            form_score_control=getattr(analysis, "form_score_control", None),
            form_score_overall=getattr(analysis, "form_score_overall", None),
            summary_json=analysis.summary_json,
            quality_gate_result=analysis.quality_gate_result,
            coaching_result=coaching_result_dict,
            rep_metrics=rep_metrics_list,
            retrieval_context=getattr(analysis, "retrieval_context", None),
            eval_scores=getattr(analysis, "eval_scores", None),
            flagged_for_review=analysis.flagged_for_review,
            is_golden_dataset=analysis.is_golden_dataset,
            created_at=analysis.created_at,
        )

    async def submit_annotation(
        self,
        analysis_id: uuid.UUID,
        annotator_id: uuid.UUID,
        data: AnnotationCreate,
    ) -> AnalysisExpertReview:
        """Submit a structured annotation (FR-EXPV-04)."""
        review = AnalysisExpertReview(
            analysis_id=analysis_id,
            annotator_id=annotator_id,
            issues_identified=data.issues_identified,
            coaching_quality_score=data.coaching_quality_score,
            movement_advice_accurate=data.movement_advice_accurate,
            engagement_advice_accurate=data.engagement_advice_accurate,
            suggested_corrections=data.suggested_corrections,
            cited_sources=data.cited_sources,
            is_golden_label=data.is_golden_label,
        )
        created = await self._review_repo.create(review)

        # Side effect: if golden label, update the analysis (FR-EXPV-07)
        if data.is_golden_label:
            analysis = await self._analysis_repo.get_by_id(analysis_id)
            if analysis is not None:
                analysis.is_golden_dataset = True
                await self._analysis_repo.update(analysis)

        return created

    async def set_golden_label(
        self, analysis_id: uuid.UUID, is_golden: bool
    ) -> dict[str, Any]:
        """Set golden dataset flag on an analysis (FR-EXPV-07)."""
        analysis = await self._analysis_repo.get_by_id(analysis_id)
        if analysis is None:
            return {}
        analysis.is_golden_dataset = is_golden
        await self._analysis_repo.update(analysis)
        return {"id": analysis.id, "is_golden_dataset": analysis.is_golden_dataset}

    async def _get_first_run_analyses(
        self, limit: int = 20, offset: int = 0
    ) -> list[Analysis]:
        """Get completed analyses that have zero annotations (first-run variants)."""
        all_completed = await self._analysis_repo.list_all(
            limit=200, offset=0, status_filter="completed"
        )
        first_run = []
        for a in all_completed:
            count = await self._review_repo.count_by_analysis(a.id)
            if count == 0:
                first_run.append(a)
        return first_run[offset : offset + limit]
