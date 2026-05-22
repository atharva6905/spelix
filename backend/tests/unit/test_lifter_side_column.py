"""Verify the lifter_side column is present on the Analysis model with the
correct nullable + CHECK constraint (Session 2, L2-LIFTER-SIDE-02).
"""
from sqlalchemy import inspect

from app.models.analysis import Analysis


def test_analysis_model_has_lifter_side_column() -> None:
    cols = {c.name: c for c in inspect(Analysis).columns}
    assert "lifter_side" in cols
    col = cols["lifter_side"]
    assert col.nullable is True
    assert col.type.length == 10


def test_analysis_model_has_lifter_side_check_constraint() -> None:
    constraints = {
        c.name for c in Analysis.__table__.constraints if c.name is not None
    }
    assert "ck_analyses_lifter_side" in constraints
