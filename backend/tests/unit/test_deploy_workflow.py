"""Regression guards for the prod deploy pipeline (issue #311).

The prod migrate step (`alembic upgrade head`) never ran successfully because
(1) bare `uv run` tried to sync DEV deps into the read-only `--no-dev` venv
(Permission denied), and (2) `alembic.ini` + `alembic/` were never COPYd into
the image (alembic could not find `script_location`). These string-level checks
lock the fix so a future edit can't silently regress either half — and assert
the #303 retry-then-gate (reverted in #310) is present so a real migrate
failure rolls back red instead of being swallowed by the errexit-off script.
"""

import re
from pathlib import Path

# repo root: backend/tests/unit/test_deploy_workflow.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_DOCKERFILE = _REPO_ROOT / "backend" / "Dockerfile"


def _ci_text() -> str:
    return _CI_YML.read_text(encoding="utf-8")


def _dockerfile_text() -> str:
    return _DOCKERFILE.read_text(encoding="utf-8")


def test_dockerfile_copies_alembic_config_and_migrations() -> None:
    """The image must carry alembic.ini + the alembic/ migrations dir, else
    `alembic upgrade head` fails with 'No script_location key found'."""
    text = _dockerfile_text()
    assert re.search(r"^\s*COPY\s+alembic\.ini\b", text, re.MULTILINE), (
        "Dockerfile must `COPY alembic.ini` into the image"
    )
    assert re.search(r"^\s*COPY\s+alembic/\s", text, re.MULTILINE), (
        "Dockerfile must `COPY alembic/` (migrations dir) into the image"
    )


def test_migrate_invocation_uses_no_dev_and_explicit_config() -> None:
    """The migrate line must use `uv run --no-dev` (not bare `uv run`, which
    syncs dev deps into the read-only venv) and pass `-c /app/alembic.ini`."""
    text = _ci_text()
    migrate_lines = [
        ln for ln in text.splitlines() if "alembic" in ln and "upgrade head" in ln
    ]
    assert migrate_lines, "no `alembic ... upgrade head` line found in ci.yml"
    for ln in migrate_lines:
        assert "uv run --no-dev" in ln, (
            f"migrate line must use `uv run --no-dev`, got: {ln.strip()!r}"
        )
        assert "-c /app/alembic.ini" in ln, (
            f"migrate line must pass `-c /app/alembic.ini`, got: {ln.strip()!r}"
        )
        # guard against a bare `uv run alembic` slipping back in
        assert not re.search(r"uv run\s+alembic", ln), (
            f"migrate line must not use bare `uv run alembic`, got: {ln.strip()!r}"
        )


def test_deploy_has_migrate_retry_then_gate() -> None:
    """A persistent migrate failure must gate rollback (the #303/#309 logic):
    a bounded retry loop + a MIGRATED flag that controls the rollback path."""
    text = _ci_text()
    assert "MIGRATED=0" in text, "deploy script must initialise MIGRATED=0"
    assert "MIGRATED=1" in text, "deploy script must set MIGRATED=1 on success"
    assert re.search(r'\[\s*"\$MIGRATED"\s*=\s*1\s*\]', text), (
        "rollback must be gated on the MIGRATED flag"
    )
    assert re.search(r"for m in 1 2 3 4 5", text), (
        "migrate must retry (5 attempts) to absorb post-`up -d` readiness blips"
    )
    assert "ROLLING BACK" in text and 'git checkout "$PREVIOUS_SHA"' in text, (
        "deploy must roll back to the previous SHA on failure"
    )
