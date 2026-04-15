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


def test_beta_request_email_nullable_false() -> None:
    assert BetaRequest.__table__.c.email.nullable is False
    assert BetaRequest.__table__.c.consented_to_beta_terms.nullable is False
