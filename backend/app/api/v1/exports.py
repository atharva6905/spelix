"""FastAPI router for analysis export endpoints.

Routes:
    GET /api/v1/analyses/{analysis_id}/export/csv — download analysis as CSV

Requirements: FR-XPRT-04, NFR-SECU-07 (GDPR Article 20)
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.repositories.analysis import AnalysisRepository
from app.services.export import ExportService

router = APIRouter(tags=["exports"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ExportService:
    repo = AnalysisRepository(db)
    return ExportService(repo)


@router.get("/{analysis_id}/export/csv")
async def export_csv(
    analysis_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ExportService = Depends(_get_service),
) -> StreamingResponse:
    """Download a specific analysis as a CSV file.

    Returns one header row and one data row per rep.  Analysis metadata
    (exercise type, variant, created_at, confidence_score) is repeated on
    every row.  All fields from ``metrics_json`` are flattened into columns.

    Raises:
        401 — missing or invalid JWT.
        403 — authenticated user does not own this analysis.
        404 — analysis does not exist.
    """
    csv_content = await service.generate_csv(analysis_id, user["id"])

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="analysis_{analysis_id}.csv"',
        },
    )
