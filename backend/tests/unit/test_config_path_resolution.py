"""Tests for ThresholdConfig path resolution in different filesystem layouts.

Regression coverage for the production worker crash where
``ThresholdConfig()`` raised ``FileNotFoundError: '/config/thresholds_v1.json'``
inside the Docker container. The cause: the path resolution in
``app/config.py`` was

    _REPO_ROOT = Path(__file__).parent.parent.parent
    _DEFAULT_THRESHOLD_PATH = _REPO_ROOT / "config" / "thresholds_v1.json"

For the local-dev layout ``<repo>/backend/app/config.py``, ``parent.parent.parent``
walks up to the repo root and finds ``<repo>/config/thresholds_v1.json``.
For the Docker container layout ``/app/app/config.py``, the same walk
walks up to the filesystem root ``/`` and looks for ``/config/...``
which doesn't exist (the Dockerfile didn't even copy ``config/`` into
the image).

These tests verify the fixed loader:

1. honours the ``THRESHOLD_CONFIG_PATH`` env var unconditionally (already
   supported, kept as the highest-priority override)
2. falls back to a list of candidate paths and picks the first one that
   exists, so it works in BOTH the local-dev layout AND the Docker
   layout (and is robust against future container restructures)
3. raises ``FileNotFoundError`` with an actionable message listing all
   candidates that were tried, so future deploy issues are diagnosable
   from the logs alone
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_threshold_file(tmp_path: Path) -> Path:
    """Create a minimal valid thresholds_v1.json in a tmp directory."""
    f = tmp_path / "thresholds_v1.json"
    f.write_text(
        json.dumps(
            {
                "version": "v1",
                "scoring_weights": {
                    "form_score_safety": 0.4,
                    "form_score_technique": 0.3,
                    "form_score_path_balance": 0.2,
                    "form_score_control": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )
    return f


class TestThresholdConfigPathResolution:
    def test_env_var_override_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch, fake_threshold_file: Path
    ) -> None:
        """THRESHOLD_CONFIG_PATH env var, when set, must be used directly."""
        monkeypatch.setenv("THRESHOLD_CONFIG_PATH", str(fake_threshold_file))

        from app.config import ThresholdConfig

        cfg = ThresholdConfig()
        assert cfg.version == "v1"

    def test_finds_config_in_docker_layout(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """When env var is unset, the loader must locate the file in the
        Docker container layout: ``/app/config/thresholds_v1.json``
        relative to the WORKDIR (which equals ``Path.cwd()`` in production
        because the container starts from /app).

        We simulate this by creating a fake ``<tmp>/config/`` directory
        and chdir-ing into ``<tmp>`` so ``Path.cwd()`` returns it. The
        loader should walk the candidate list and find the file.
        """
        monkeypatch.delenv("THRESHOLD_CONFIG_PATH", raising=False)

        # Create the config dir as a sibling of cwd, mimicking /app/config
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        cfg_file = cfg_dir / "thresholds_v1.json"
        cfg_file.write_text(json.dumps({"version": "v1"}), encoding="utf-8")

        monkeypatch.chdir(tmp_path)

        from app.config import ThresholdConfig

        cfg = ThresholdConfig()
        assert cfg.version == "v1"

    def test_finds_config_in_local_dev_layout(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When env var is unset and the file exists at the local-dev
        location (<repo>/config/thresholds_v1.json relative to
        backend/app/config.py via three .parent walks), it must still be
        found. This is the layout the existing test environment runs in.
        """
        monkeypatch.delenv("THRESHOLD_CONFIG_PATH", raising=False)

        from app.config import ThresholdConfig

        # Real <repo>/config/thresholds_v1.json should exist in the
        # checked-out repo. If this test fails the repo is broken.
        cfg = ThresholdConfig()
        assert cfg.version  # any non-empty version string

    def test_raises_actionable_error_when_no_candidate_exists(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """When neither the env var nor any candidate path resolves, the
        error MUST list every candidate path tried so the operator can
        diagnose from logs alone.
        """
        monkeypatch.delenv("THRESHOLD_CONFIG_PATH", raising=False)

        # chdir to a totally empty directory and patch out the local-dev
        # candidate so all candidates miss
        monkeypatch.chdir(tmp_path)

        from app.config import _resolve_threshold_path

        # Patch the local-dev candidate so it points at a definitely-
        # non-existent path. We do this by monkeypatching the helper
        # function rather than poking module globals.
        import app.config as config_mod

        original_default = config_mod._DEFAULT_THRESHOLD_PATH
        monkeypatch.setattr(
            config_mod, "_DEFAULT_THRESHOLD_PATH", tmp_path / "nope" / "thresholds_v1.json"
        )

        try:
            with pytest.raises(FileNotFoundError) as exc_info:
                _resolve_threshold_path()
            # Error must list every candidate that was tried
            msg = str(exc_info.value)
            assert "thresholds_v1.json" in msg
            # Multiple candidates should be mentioned
            assert msg.count("thresholds_v1.json") >= 2
        finally:
            monkeypatch.setattr(config_mod, "_DEFAULT_THRESHOLD_PATH", original_default)
