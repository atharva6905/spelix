import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, gen_uuid


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            "sex IN ('male','female','prefer_not_to_say')",
            name="ck_user_profiles_sex",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    height_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    experience_level: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    arm_span_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    femur_length_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Migration 9fffb59ba45f — optional lifter sex for coaching evidence matching (FR-PROF-03 ext.)
    sex: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
