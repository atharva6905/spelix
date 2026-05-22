"""Static test for the lateral_deviation_px -> ap_deviation_px JSONB
migration (revision 2371965f8072).

Verifies:
- The upgrade() SQL targets ``rep_metrics.metrics``, removes the old key,
  builds the new key from the old value, and guards with ``WHERE metrics ?
  'lateral_deviation_px'`` (idempotent).
- The downgrade() SQL is the symmetric inverse.
- The semantic rename, when applied to a representative JSONB payload
  via Python dict munging, preserves the numeric value and removes the
  old key.

This is a unit test against the migration's text + a Python-side
equivalent of the JSONB transformation. A live-DB integration test is
unnecessary here because (1) the SQL is small and (2) the migration is
applied locally and on prod as part of the deploy CI step.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2371965f8072_rename_lateral_deviation_px_jsonb_key_.py"
)


def _load_migration() -> types.ModuleType:
    """Load the migration file as a module with a stubbed alembic.op."""
    spec = importlib.util.spec_from_file_location("migration_ap_rename", _MIGRATION_PATH)
    assert spec is not None, f"Cannot load migration from {_MIGRATION_PATH}"
    mod = importlib.util.module_from_spec(spec)
    alembic_stub = types.ModuleType("alembic")
    op_stub = MagicMock()
    alembic_stub.op = op_stub  # type: ignore[attr-defined]
    sys.modules["alembic"] = alembic_stub
    sys.modules["alembic.op"] = op_stub
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_migration_revises_current_head() -> None:
    mod = _load_migration()
    assert mod.revision == "2371965f8072"
    assert mod.down_revision == "0906139da711"


def test_upgrade_sql_renames_lateral_to_ap() -> None:
    mod = _load_migration()
    op_stub = sys.modules["alembic"].op  # type: ignore[attr-defined]
    op_stub.reset_mock()
    mod.upgrade()
    op_stub.execute.assert_called_once()
    sql = op_stub.execute.call_args.args[0]
    assert "UPDATE rep_metrics" in sql
    assert "metrics_json - 'lateral_deviation_px'" in sql
    assert "jsonb_build_object('ap_deviation_px'" in sql
    # Idempotency guard
    assert "WHERE metrics_json ? 'lateral_deviation_px'" in sql


def test_downgrade_sql_reverses_the_rename() -> None:
    mod = _load_migration()
    op_stub = sys.modules["alembic"].op  # type: ignore[attr-defined]
    op_stub.reset_mock()
    mod.downgrade()
    op_stub.execute.assert_called_once()
    sql = op_stub.execute.call_args.args[0]
    assert "metrics_json - 'ap_deviation_px'" in sql
    assert "jsonb_build_object('lateral_deviation_px'" in sql
    assert "WHERE metrics_json ? 'ap_deviation_px'" in sql


def _apply_python_equivalent(row_metrics: dict) -> dict:
    """Mirror the JSONB transformation in pure Python."""
    if "lateral_deviation_px" not in row_metrics:
        return row_metrics
    new = {k: v for k, v in row_metrics.items() if k != "lateral_deviation_px"}
    new["ap_deviation_px"] = row_metrics["lateral_deviation_px"]
    return new


def test_python_equivalent_preserves_value() -> None:
    before = {"lateral_deviation_px": 0.123, "depth_angle": 92.0}
    after = _apply_python_equivalent(before)
    assert after["ap_deviation_px"] == pytest.approx(0.123)
    assert "lateral_deviation_px" not in after
    assert after["depth_angle"] == 92.0


def test_python_equivalent_is_idempotent() -> None:
    """Applying the transformation twice is a no-op the second time."""
    before = {"lateral_deviation_px": 0.05}
    once = _apply_python_equivalent(before)
    twice = _apply_python_equivalent(once)
    assert once == twice
    assert "lateral_deviation_px" not in twice
    assert twice["ap_deviation_px"] == pytest.approx(0.05)


def test_python_equivalent_noop_on_already_renamed_row() -> None:
    """A row that already has the new key is untouched."""
    row = {"ap_deviation_px": 0.07, "torso_lean": 30.0}
    after = _apply_python_equivalent(row)
    assert after == row
