"""Unit tests for the BetaRequest SQLAlchemy model."""

from app.models.beta_request import BetaRequest


def test_beta_request_tablename_and_columns() -> None:
    assert BetaRequest.__tablename__ == "beta_requests"
    cols = {c.name for c in BetaRequest.__table__.columns}
    assert cols == {
        "id",
        "email",
        "source",
        "consented_to_beta_terms",
        "status",
        "created_at",
        "approved_at",
        "approved_by",
        "invite_sent_at",
        "invite_token",
    }


def test_beta_request_status_has_check_constraint() -> None:
    # Per root CLAUDE.md: status is VARCHAR(30) with CHECK.
    status_col = BetaRequest.__table__.c.status
    assert status_col.type.length == 30
    constraint_names = {
        c.name for c in BetaRequest.__table__.constraints if c.name
    }
    assert "ck_beta_requests_status" in constraint_names


def test_beta_request_email_nullable_false() -> None:
    assert BetaRequest.__table__.c.email.nullable is False
    assert BetaRequest.__table__.c.consented_to_beta_terms.nullable is False


def test_beta_request_email_has_unique_index_on_model() -> None:
    # Regression guard: migration 008 creates `uq_beta_requests_email`, but
    # CI uses `scripts/create_test_tables.py` (Base.metadata.create_all), which
    # only emits indexes declared on the model. Without this, the duplicate-
    # email integration test passes locally but fails in CI. See PR #45.
    indexes_by_name = {idx.name: idx for idx in BetaRequest.__table__.indexes}
    assert "uq_beta_requests_email" in indexes_by_name
    idx = indexes_by_name["uq_beta_requests_email"]
    assert idx.unique is True
    assert [c.name for c in idx.columns] == ["email"]
