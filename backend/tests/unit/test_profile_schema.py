"""ProfileUpdate.sex contract (FR-PROF-03 ext.)."""
import pytest
from pydantic import ValidationError

from app.schemas.profile import ProfileUpdate


def _update(**kw):
    base = dict(height_cm=180, weight_kg=80, age=30, experience_level="beginner")
    base.update(kw)
    return ProfileUpdate(**base)


def test_profile_update_sex_defaults_to_none():
    assert _update().sex is None


def test_profile_update_accepts_valid_sex():
    assert _update(sex="female").sex == "female"


def test_profile_update_rejects_invalid_sex():
    with pytest.raises(ValidationError):
        _update(sex="other")
