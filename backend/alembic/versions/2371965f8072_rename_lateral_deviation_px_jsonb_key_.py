"""rename lateral_deviation_px jsonb key to ap_deviation_px

Revision ID: 2371965f8072
Revises: 0906139da711
Create Date: 2026-05-22 04:02:14.082245

Per docs/audit/cv-dimension-audit-2026-05-11.md item E-1, the metric was
renamed in code from ``lateral_deviation_px`` to ``ap_deviation_px`` because
the metric measures anterior-posterior drift from a sagittal-view camera,
not lateral.

This migration rewrites the JSONB key in all existing
``rep_metrics.metrics_json`` rows so historical analyses remain readable
under the new key. The numeric value is preserved. Idempotent (WHERE guard);
reversible (downgrade reverses the rename).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2371965f8072'
down_revision: Union[str, Sequence[str], None] = '0906139da711'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename JSONB key lateral_deviation_px -> ap_deviation_px in rep_metrics.metrics_json."""
    op.execute(
        """
        UPDATE rep_metrics
        SET metrics_json = (metrics_json - 'lateral_deviation_px')
                      || jsonb_build_object('ap_deviation_px', metrics_json->'lateral_deviation_px')
        WHERE metrics_json ? 'lateral_deviation_px'
        """
    )


def downgrade() -> None:
    """Reverse: ap_deviation_px -> lateral_deviation_px in rep_metrics.metrics_json."""
    op.execute(
        """
        UPDATE rep_metrics
        SET metrics_json = (metrics_json - 'ap_deviation_px')
                      || jsonb_build_object('lateral_deviation_px', metrics_json->'ap_deviation_px')
        WHERE metrics_json ? 'ap_deviation_px'
        """
    )
