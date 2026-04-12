"""Privacy-preserving trigger tag processing for Coach Brain entries.

Implements FR-BRAIN-10: body proportion attributes in trigger_tags use
categorical bins (3-5 categories), never raw measurements. Group size
threshold n>=20 is enforced before any pattern surfaces.

All methods are pure/static — no DB access, no async.
"""

from __future__ import annotations


class TriggerPrivacyService:
    """Privacy-preserving trigger tag processing for Coach Brain entries (FR-BRAIN-10).

    Body proportion attributes are categorized into bins rather than storing
    raw measurements. Group size thresholds prevent de-anonymization.

    Bin boundaries are calibrated for the barbell-athlete population, not the
    general population:

    Height bins (cm):
        short     < 165
        average   165 – 180  (inclusive on both edges)
        tall      > 180

    Weight bins (kg):
        light     < 70
        moderate  70 – 90   (inclusive on both edges)
        heavy     > 90

    Limb ratio bins (femur_length_cm / height_cm):
        short_limbed   < 0.26
        proportional   0.26 – 0.30  (inclusive on both edges)
        long_limbed    > 0.30

    Experience bins (passthrough for known values):
        beginner | intermediate | advanced | elite
        Unknown → intermediate (safe mid-bin fallback)
    """

    # Categorical bins for body proportions (3-5 categories each)
    HEIGHT_BINS = ["short", "average", "tall"]  # <165cm, 165-180cm, >180cm
    WEIGHT_BINS = ["light", "moderate", "heavy"]  # <70kg, 70-90kg, >90kg
    LIMB_RATIO_BINS = ["short_limbed", "proportional", "long_limbed"]
    EXPERIENCE_BINS = ["beginner", "intermediate", "advanced", "elite"]

    MIN_GROUP_SIZE = 20  # FR-BRAIN-10: minimum n before patterns surface

    @staticmethod
    def categorize_height(height_cm: float) -> str:
        """Bin height into categorical label.

        Args:
            height_cm: Athlete height in centimetres.

        Returns:
            "short" (<165), "average" (165-180 inclusive), or "tall" (>180).
        """
        if height_cm < 165.0:
            return "short"
        if height_cm <= 180.0:
            return "average"
        return "tall"

    @staticmethod
    def categorize_weight(weight_kg: float) -> str:
        """Bin weight into categorical label.

        Args:
            weight_kg: Athlete body weight in kilograms.

        Returns:
            "light" (<70), "moderate" (70-90 inclusive), or "heavy" (>90).
        """
        if weight_kg < 70.0:
            return "light"
        if weight_kg <= 90.0:
            return "moderate"
        return "heavy"

    @staticmethod
    def categorize_limb_ratio(femur_length_cm: float, height_cm: float) -> str:
        """Bin femur-to-height ratio into categorical label.

        The ratio captures relative limb length which affects squat and
        deadlift mechanics without storing the raw measurements.

        Args:
            femur_length_cm: Femur length in centimetres.
            height_cm: Athlete height in centimetres (must be > 0).

        Returns:
            "short_limbed" (ratio<0.26), "proportional" (0.26-0.30 inclusive),
            or "long_limbed" (ratio>0.30).
        """
        ratio = femur_length_cm / height_cm
        if ratio < 0.26:
            return "short_limbed"
        if ratio <= 0.30:
            return "proportional"
        return "long_limbed"

    @staticmethod
    def categorize_experience(experience_level: str) -> str:
        """Map experience level to bin (passthrough if already valid).

        Args:
            experience_level: Raw experience string from athlete profile.

        Returns:
            One of "beginner", "intermediate", "advanced", "elite".
            Unrecognised values fall back to "intermediate".
        """
        valid = {"beginner", "intermediate", "advanced", "elite"}
        if experience_level in valid:
            return experience_level
        return "intermediate"

    @staticmethod
    def build_trigger_tags(
        *,
        exercise: str,
        height_cm: float | None = None,
        weight_kg: float | None = None,
        femur_length_cm: float | None = None,
        experience_level: str | None = None,
        additional_tags: list[str] | None = None,
    ) -> list[str]:
        """Build privacy-safe trigger tags from athlete profile data.

        Always includes the exercise tag. Body proportion tags use categorical
        bins only — never raw measurements. Additional tags (like "knee_cave",
        "forward_lean") are passed through directly.

        Limb ratio tag is only added when BOTH femur_length_cm AND height_cm
        are provided — either alone is insufficient for the ratio calculation.

        Duplicate tags are deduplicated while preserving insertion order.

        Args:
            exercise: Barbell exercise type ("squat", "bench", "deadlift").
            height_cm: Optional athlete height in centimetres.
            weight_kg: Optional athlete weight in kilograms.
            femur_length_cm: Optional femur length in centimetres.
            experience_level: Optional experience string.
            additional_tags: Optional pass-through tags (movement fault labels,
                coaching cues, etc.). Never subjected to binning.

        Returns:
            Deduplicated list of categorical string tags. Raw numeric values
            are never present.
        """
        seen: set[str] = set()
        tags: list[str] = []

        def _add(tag: str) -> None:
            if tag not in seen:
                seen.add(tag)
                tags.append(tag)

        # Exercise tag is always first
        _add(exercise)

        # Height bin
        if height_cm is not None:
            _add(TriggerPrivacyService.categorize_height(height_cm))

        # Weight bin
        if weight_kg is not None:
            _add(TriggerPrivacyService.categorize_weight(weight_kg))

        # Limb ratio bin — requires both measurements
        if femur_length_cm is not None and height_cm is not None:
            _add(TriggerPrivacyService.categorize_limb_ratio(femur_length_cm, height_cm))

        # Experience bin
        if experience_level is not None:
            _add(TriggerPrivacyService.categorize_experience(experience_level))

        # Pass-through tags (movement faults, cue labels, etc.)
        for tag in additional_tags or []:
            _add(tag)

        return tags

    @staticmethod
    def check_group_size(group_count: int) -> bool:
        """Return True if group_count >= MIN_GROUP_SIZE.

        Coach Brain entries whose trigger pattern matches fewer than 20
        analyses must NOT surface in retrieval results (FR-BRAIN-10).

        Args:
            group_count: Number of analyses matching a given trigger pattern.

        Returns:
            True when the group is large enough to surface; False otherwise.
        """
        return group_count >= TriggerPrivacyService.MIN_GROUP_SIZE
