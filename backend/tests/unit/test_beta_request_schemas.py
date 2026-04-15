"""Unit tests for BetaRequest Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.beta_request import BetaRequestCreate


def test_valid_payload_passes() -> None:
    payload = BetaRequestCreate(
        email="A.User+Beta@Example.COM",
        source="hero",
        consented_to_beta_terms=True,
    )
    # Pydantic validator lowercases + strips the email.
    assert payload.email == "a.user+beta@example.com"
    assert payload.source == "hero"
    assert payload.consented_to_beta_terms is True


def test_invalid_email_rejected() -> None:
    with pytest.raises(ValidationError):
        BetaRequestCreate(
            email="not-an-email",
            source="hero",
            consented_to_beta_terms=True,
        )


def test_invalid_source_rejected() -> None:
    with pytest.raises(ValidationError):
        BetaRequestCreate(
            email="a@b.com",
            source="facebook_ad",
            consented_to_beta_terms=True,
        )


def test_consent_false_rejected() -> None:
    with pytest.raises(ValidationError):
        BetaRequestCreate(
            email="a@b.com",
            source="hero",
            consented_to_beta_terms=False,
        )


def test_whitespace_stripped_and_lowercased() -> None:
    payload = BetaRequestCreate(
        email="  User@Example.com  ",
        source="final_cta",
        consented_to_beta_terms=True,
    )
    assert payload.email == "user@example.com"


def test_consent_omitted_rejected() -> None:
    # Field(...) makes it required — omission raises just like a False value.
    with pytest.raises(ValidationError):
        BetaRequestCreate(email="a@b.com", source="hero")  # type: ignore[call-arg]
