"""
Tests for analysis status transition guard (SRS Section 5.2a).

TDD gate: all tests must pass after implementation.
"""
import pytest

from app.services.status import InvalidTransition, transition

# ---------------------------------------------------------------------------
# 1. Every valid transition succeeds
# ---------------------------------------------------------------------------


class TestValidTransitions:
    def test_new_row_to_queued(self):
        """(new row) → queued is the only legal first transition."""
        assert transition(None, "queued") == "queued"

    def test_queued_to_quality_gate_pending(self):
        assert transition("queued", "quality_gate_pending") == "quality_gate_pending"

    def test_quality_gate_pending_to_quality_gate_rejected(self):
        assert (
            transition("quality_gate_pending", "quality_gate_rejected")
            == "quality_gate_rejected"
        )

    def test_quality_gate_pending_to_processing(self):
        assert transition("quality_gate_pending", "processing") == "processing"

    def test_processing_to_coaching(self):
        assert transition("processing", "coaching") == "coaching"

    def test_processing_to_failed(self):
        assert transition("processing", "failed") == "failed"

    def test_coaching_to_completed(self):
        assert transition("coaching", "completed") == "completed"

    def test_coaching_to_failed(self):
        assert transition("coaching", "failed") == "failed"

    def test_failed_to_queued_when_retry_count_zero(self):
        assert transition("failed", "queued", retry_count=0) == "queued"

    def test_failed_to_queued_when_retry_count_one(self):
        assert transition("failed", "queued", retry_count=1) == "queued"

    def test_failed_to_queued_when_retry_count_two(self):
        assert transition("failed", "queued", retry_count=2) == "queued"


# ---------------------------------------------------------------------------
# 2. Every invalid transition raises InvalidTransition
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    def test_queued_cannot_go_to_processing(self):
        with pytest.raises(InvalidTransition):
            transition("queued", "processing")

    def test_queued_cannot_go_to_completed(self):
        with pytest.raises(InvalidTransition):
            transition("queued", "completed")

    def test_queued_cannot_go_to_failed(self):
        with pytest.raises(InvalidTransition):
            transition("queued", "failed")

    def test_quality_gate_pending_cannot_go_to_completed(self):
        with pytest.raises(InvalidTransition):
            transition("quality_gate_pending", "completed")

    def test_quality_gate_pending_cannot_go_to_coaching(self):
        with pytest.raises(InvalidTransition):
            transition("quality_gate_pending", "coaching")

    def test_processing_cannot_go_to_queued(self):
        with pytest.raises(InvalidTransition):
            transition("processing", "queued")

    def test_processing_cannot_go_to_completed(self):
        with pytest.raises(InvalidTransition):
            transition("processing", "completed")

    def test_coaching_cannot_go_to_processing(self):
        with pytest.raises(InvalidTransition):
            transition("coaching", "processing")

    def test_coaching_cannot_go_to_queued(self):
        with pytest.raises(InvalidTransition):
            transition("coaching", "queued")

    def test_none_cannot_go_to_processing(self):
        with pytest.raises(InvalidTransition):
            transition(None, "processing")

    def test_none_cannot_go_to_completed(self):
        with pytest.raises(InvalidTransition):
            transition(None, "completed")

    def test_unknown_current_status_raises(self):
        with pytest.raises(InvalidTransition):
            transition("not_a_real_status", "queued")

    def test_unknown_target_status_raises(self):
        with pytest.raises(InvalidTransition):
            transition("queued", "not_a_real_status")


# ---------------------------------------------------------------------------
# 3. Terminal states reject all transitions
# ---------------------------------------------------------------------------


class TestTerminalStates:
    VALID_TARGETS = [
        "queued",
        "quality_gate_pending",
        "quality_gate_rejected",
        "processing",
        "coaching",
        "completed",
        "failed",
    ]

    def test_completed_rejects_all_targets(self):
        for target in self.VALID_TARGETS:
            with pytest.raises(InvalidTransition):
                transition("completed", target)

    def test_quality_gate_rejected_rejects_all_targets(self):
        for target in self.VALID_TARGETS:
            with pytest.raises(InvalidTransition):
                transition("quality_gate_rejected", target)

    def test_failed_at_max_retries_rejects_all_targets(self):
        """failed with retry_count>=3 is terminal — no transitions allowed."""
        for target in self.VALID_TARGETS:
            with pytest.raises(InvalidTransition):
                transition("failed", target, retry_count=3)

    def test_failed_at_retry_count_four_rejects_all_targets(self):
        for target in self.VALID_TARGETS:
            with pytest.raises(InvalidTransition):
                transition("failed", target, retry_count=4)


# ---------------------------------------------------------------------------
# 4. failed→queued blocked when retry_count >= 3
# ---------------------------------------------------------------------------


class TestFailedRetryGate:
    def test_failed_to_queued_blocked_at_exactly_three(self):
        with pytest.raises(InvalidTransition):
            transition("failed", "queued", retry_count=3)

    def test_failed_to_queued_blocked_above_three(self):
        with pytest.raises(InvalidTransition):
            transition("failed", "queued", retry_count=10)

    def test_failed_to_non_queued_always_blocked(self):
        """failed can only retry to queued (when count < 3); all other targets invalid."""
        for target in ["quality_gate_pending", "processing", "coaching", "completed"]:
            with pytest.raises(InvalidTransition):
                transition("failed", target, retry_count=0)


# ---------------------------------------------------------------------------
# 5. failed→queued allowed when retry_count < 3
# ---------------------------------------------------------------------------


class TestFailedRetryAllowed:
    def test_allowed_at_zero(self):
        assert transition("failed", "queued", retry_count=0) == "queued"

    def test_allowed_at_one(self):
        assert transition("failed", "queued", retry_count=1) == "queued"

    def test_allowed_at_two(self):
        assert transition("failed", "queued", retry_count=2) == "queued"

    def test_default_retry_count_is_zero(self):
        """Default retry_count=0 means failed→queued is valid by default."""
        assert transition("failed", "queued") == "queued"


# ---------------------------------------------------------------------------
# 6. InvalidTransition message is informative
# ---------------------------------------------------------------------------


class TestExceptionMessage:
    def test_exception_message_contains_current_and_target(self):
        with pytest.raises(InvalidTransition) as exc_info:
            transition("completed", "queued")
        msg = str(exc_info.value)
        assert "completed" in msg
        assert "queued" in msg
