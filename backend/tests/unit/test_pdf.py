"""Unit tests for the PDF report generation service (B-035).

TDD gate: given analysis + coaching context → generates valid PDF bytes
          written to the correct output path.

Requirements: FR-XPRT-02, FR-XPRT-03, NFR-PERF-07

Tests
-----
1. test_render_html_contains_exercise_info     — exercise type, date, disclaimer present
2. test_generate_pdf_creates_file             — file exists and has >0 bytes
3. test_pdf_contains_disclaimer               — mandatory disclaimer in rendered HTML
4. test_pdf_with_no_plot                      — plot_path=None does not crash

Note on WeasyPrint mocking
--------------------------
WeasyPrint requires GTK system libraries (libgobject-2.0-0) which are not
present on Windows dev machines.  generate_pdf uses a lazy ``from weasyprint
import HTML`` inside the function body so that the module-level import does not
fail on import.  Tests that exercise generate_pdf inject a fake ``weasyprint``
module into ``sys.modules`` before calling the code under test so that the
lazy import resolves to our stub.  The real GTK path is exercised by the
Docker-based integration test suite.
"""

from __future__ import annotations

import os
import sys
import types
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.services.pdf import MANDATORY_DISCLAIMER, PDFService

# ---------------------------------------------------------------------------
# WeasyPrint stub
# ---------------------------------------------------------------------------


@contextmanager
def _weasyprint_stub(output_path_ref: list[str] | None = None):
    """Inject a fake ``weasyprint`` module so generate_pdf can run without GTK.

    The stub writes ``%PDF-1.4`` magic bytes to whatever path is passed to
    ``HTML(...).write_pdf(path)`` so file-existence assertions pass.
    """
    mock_html_instance = MagicMock()

    def fake_write_pdf(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"%PDF-1.4 fake-pdf-for-unit-tests\n")
        if output_path_ref is not None:
            output_path_ref.append(path)

    mock_html_instance.write_pdf.side_effect = fake_write_pdf

    mock_html_cls = MagicMock(return_value=mock_html_instance)

    # Build a minimal fake module
    fake_module = types.ModuleType("weasyprint")
    fake_module.HTML = mock_html_cls  # type: ignore[attr-defined]

    prev = sys.modules.get("weasyprint")
    sys.modules["weasyprint"] = fake_module
    try:
        yield mock_html_cls
    finally:
        if prev is None:
            sys.modules.pop("weasyprint", None)
        else:
            sys.modules["weasyprint"] = prev


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

DISCLAIMER = MANDATORY_DISCLAIMER

_COACHING = {
    "summary": "Good overall session with consistent depth.",
    "strengths": [
        "Consistent hip drive through the concentric phase.",
        "Neutral spine maintained across all reps.",
    ],
    "issues": [
        {
            "rep_number": 2,
            "joint": "Left knee",
            "description": "Knee caved inward at bottom position.",
            "severity": "High",
        },
        {
            "rep_number": 4,
            "joint": "Lumbar spine",
            "description": "Slight flexion detected during ascent.",
            "severity": "Medium",
        },
    ],
    "correction_plan": [
        "Cue 'knees out' during the descent to maintain knee tracking.",
        "Brace your core before unracking to protect the lumbar spine.",
        "Focus on driving hips through at lockout.",
    ],
    "disclaimer": DISCLAIMER,
    "raw_prompt_tokens": 512,
    "raw_completion_tokens": 256,
}

_REP_METRICS = [
    {"rep_index": 1, "hip_angle_min": 82.3, "knee_angle_min": 78.1, "confidence_score": 0.91},
    {"rep_index": 2, "hip_angle_min": 85.0, "knee_angle_min": 80.4, "confidence_score": 0.89},
    {"rep_index": 3, "hip_angle_min": 80.1, "knee_angle_min": 76.9, "confidence_score": 0.93},
]


def _make_context(
    *,
    exercise_type: str = "squat",
    exercise_variant: str = "low_bar",
    date: str = "2025-04-08",
    confidence_score: float = 0.91,
    confidence_label: str = "High",
    rep_count: int = 3,
    rep_metrics: list | None = None,
    coaching: dict | None = None,
    plot_path: str | None = None,
    disclaimer: str = DISCLAIMER,
) -> dict:
    return {
        "date": date,
        "exercise_type": exercise_type,
        "exercise_variant": exercise_variant,
        "confidence_score": confidence_score,
        "confidence_label": confidence_label,
        "rep_count": rep_count,
        "rep_metrics": rep_metrics if rep_metrics is not None else _REP_METRICS,
        "coaching": coaching if coaching is not None else _COACHING,
        "plot_path": plot_path,
        "disclaimer": disclaimer,
    }


@pytest.fixture()
def pdf_service() -> PDFService:
    """PDFService using the real template via default path resolution."""
    return PDFService()


# ---------------------------------------------------------------------------
# 1. render_html — content checks (no WeasyPrint needed)
# ---------------------------------------------------------------------------


class TestRenderHtml:
    def test_render_html_contains_exercise_info(self, pdf_service: PDFService):
        """Rendered HTML includes exercise type, variant, and date."""
        ctx = _make_context(
            exercise_type="deadlift",
            exercise_variant="conventional",
            date="2025-04-08",
        )
        html = pdf_service.render_html(ctx)

        assert "deadlift" in html
        assert "conventional" in html
        assert "2025-04-08" in html

    def test_render_html_contains_rep_count(self, pdf_service: PDFService):
        ctx = _make_context(rep_count=5)
        html = pdf_service.render_html(ctx)
        assert "5" in html

    def test_render_html_contains_confidence_score(self, pdf_service: PDFService):
        ctx = _make_context(confidence_score=0.87, confidence_label="Moderate")
        html = pdf_service.render_html(ctx)
        assert "87" in html
        assert "Moderate" in html

    def test_render_html_contains_coaching_summary(self, pdf_service: PDFService):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "Good overall session" in html

    def test_render_html_contains_strengths(self, pdf_service: PDFService):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "Consistent hip drive" in html
        assert "Neutral spine maintained" in html

    def test_render_html_contains_issues(self, pdf_service: PDFService):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "Left knee" in html
        assert "Knee caved inward" in html

    def test_render_html_contains_correction_plan(self, pdf_service: PDFService):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "knees out" in html

    def test_render_html_contains_rep_metrics_data(self, pdf_service: PDFService):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "Rep #" in html

    def test_render_html_bench_press(self, pdf_service: PDFService):
        """Works for bench press exercise type."""
        ctx = _make_context(
            exercise_type="bench",
            exercise_variant="competition_grip",
            rep_metrics=[
                {"rep_index": 1, "elbow_angle_min": 82.0, "wrist_angle": 178.0},
            ],
        )
        html = pdf_service.render_html(ctx)
        assert "bench" in html
        assert "competition_grip" in html


# ---------------------------------------------------------------------------
# 2. Mandatory disclaimer
# ---------------------------------------------------------------------------


class TestDisclaimer:
    def test_pdf_contains_disclaimer(self, pdf_service: PDFService):
        """Mandatory disclaimer text appears in rendered HTML."""
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert MANDATORY_DISCLAIMER in html

    def test_pdf_disclaimer_uses_custom_value_from_context(self, pdf_service: PDFService):
        """If context overrides disclaimer, that value is rendered."""
        custom_disclaimer = (
            "This feedback is for educational purposes only and is not a substitute "
            "for in-person coaching or medical advice."
        )
        ctx = _make_context(disclaimer=custom_disclaimer)
        html = pdf_service.render_html(ctx)
        assert custom_disclaimer in html


# ---------------------------------------------------------------------------
# 3. generate_pdf — file creation (WeasyPrint stubbed)
# ---------------------------------------------------------------------------


class TestGeneratePdf:
    def test_generate_pdf_creates_file(self, pdf_service: PDFService, tmp_path):
        """generate_pdf writes a non-empty PDF file to the specified path."""
        output = str(tmp_path / "report.pdf")
        ctx = _make_context()

        with _weasyprint_stub():
            returned_path = pdf_service.generate_pdf(ctx, output)

        assert returned_path == output
        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

    def test_generate_pdf_returns_output_path(self, pdf_service: PDFService, tmp_path):
        """generate_pdf returns the exact path passed in."""
        output = str(tmp_path / "sub" / "report.pdf")
        ctx = _make_context()

        with _weasyprint_stub():
            returned = pdf_service.generate_pdf(ctx, output)

        assert returned == output

    def test_generate_pdf_creates_parent_dirs(self, pdf_service: PDFService, tmp_path):
        """generate_pdf creates missing parent directories."""
        output = str(tmp_path / "nested" / "deep" / "report.pdf")
        assert not os.path.exists(str(tmp_path / "nested"))

        with _weasyprint_stub():
            pdf_service.generate_pdf(_make_context(), output)

        assert os.path.isfile(output)

    def test_generate_pdf_produces_valid_pdf_bytes(self, pdf_service: PDFService, tmp_path):
        """Output file starts with the PDF magic bytes %PDF."""
        output = str(tmp_path / "report.pdf")

        with _weasyprint_stub():
            pdf_service.generate_pdf(_make_context(), output)

        with open(output, "rb") as fh:
            magic = fh.read(4)
        assert magic == b"%PDF"

    def test_generate_pdf_passes_rendered_html_to_weasyprint(
        self, pdf_service: PDFService, tmp_path
    ):
        """WeasyPrint HTML class is called with the rendered HTML string."""
        output = str(tmp_path / "report.pdf")
        ctx = _make_context(exercise_type="bench")

        with _weasyprint_stub() as mock_html_cls:
            pdf_service.generate_pdf(ctx, output)

        call_kwargs = mock_html_cls.call_args
        assert call_kwargs is not None
        # HTML is called with string=<rendered html>
        html_arg = call_kwargs.kwargs.get("string") or (
            call_kwargs.args[0] if call_kwargs.args else ""
        )
        assert "bench" in html_arg


# ---------------------------------------------------------------------------
# 4. plot_path=None — no crash
# ---------------------------------------------------------------------------


class TestPdfWithNoPlot:
    def test_pdf_with_no_plot_renders_html(self, pdf_service: PDFService):
        """plot_path=None renders a placeholder without raising."""
        ctx = _make_context(plot_path=None)
        html = pdf_service.render_html(ctx)
        assert "not available" in html or "plot-placeholder" in html

    def test_pdf_with_no_plot_generates_file(self, pdf_service: PDFService, tmp_path):
        """generate_pdf with plot_path=None produces a valid PDF."""
        output = str(tmp_path / "no_plot_report.pdf")
        ctx = _make_context(plot_path=None)

        with _weasyprint_stub():
            pdf_service.generate_pdf(ctx, output)

        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

    def test_pdf_with_nonexistent_plot_path(self, pdf_service: PDFService, tmp_path):
        """generate_pdf with a nonexistent plot_path does not crash."""
        output = str(tmp_path / "report.pdf")
        ctx = _make_context(plot_path="/nonexistent/path/plot.png")

        with _weasyprint_stub():
            pdf_service.generate_pdf(ctx, output)

        assert os.path.isfile(output)

    def test_pdf_with_empty_rep_metrics(self, pdf_service: PDFService):
        """Empty rep_metrics list renders 'No reps detected' placeholder."""
        ctx = _make_context(rep_metrics=[], rep_count=0)
        html = pdf_service.render_html(ctx)
        assert "No reps detected" in html

    def test_pdf_with_empty_coaching_issues(self, pdf_service: PDFService):
        """Empty issues list renders 'No form issues identified' placeholder."""
        coaching = dict(_COACHING)
        coaching["issues"] = []
        ctx = _make_context(coaching=coaching)
        html = pdf_service.render_html(ctx)
        assert "No form issues identified" in html


# ---------------------------------------------------------------------------
# 5. PDFService construction
# ---------------------------------------------------------------------------


class TestPdfServiceConstruction:
    def test_raises_on_missing_template(self, tmp_path):
        """FileNotFoundError if the template is not found in template_dir."""
        with pytest.raises(FileNotFoundError, match="PDF template not found"):
            PDFService(template_dir=str(tmp_path))

    def test_accepts_custom_template_dir(self, tmp_path):
        """PDFService accepts a custom template_dir pointing to the real template."""
        import shutil

        from app.services.pdf import _DEFAULT_TEMPLATE_PATH

        shutil.copy(_DEFAULT_TEMPLATE_PATH, tmp_path / "analysis_report.html")

        service = PDFService(template_dir=str(tmp_path))
        assert service is not None


# ---------------------------------------------------------------------------
# Phase 1 PDF extension tests (FR-XPRT-02)
# ---------------------------------------------------------------------------


class TestPhase1ScorePills:
    def test_score_pills_rendered_when_scores_present(self, pdf_service):
        ctx = _make_context()
        ctx["scores"] = {
            "form_score_safety": 7.8,
            "form_score_technique": 6.5,
            "form_score_path_balance": 8.1,
            "form_score_control": 5.2,
            "form_score_overall": 7.2,
        }
        html = pdf_service.render_html(ctx)
        assert "Overall Form Rating" in html
        assert "7.2" in html
        assert "Movement Quality" in html
        assert "Technique" in html
        assert "Path &amp; Balance" in html or "Path & Balance" in html
        assert "Control" in html

    def test_score_pills_empty_when_no_scores(self, pdf_service):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "Overall Form Rating" not in html

    def test_score_pills_empty_when_overall_none(self, pdf_service):
        ctx = _make_context()
        ctx["scores"] = {
            "form_score_safety": 7.8,
            "form_score_overall": None,
        }
        html = pdf_service.render_html(ctx)
        assert "Overall Form Rating" not in html


class TestPhase1SafetyWarnings:
    def test_safety_warnings_rendered(self, pdf_service):
        ctx = _make_context()
        coaching_with_warnings = dict(_COACHING)
        coaching_with_warnings["safety_warnings"] = [
            "Excessive forward lean detected at bottom position.",
            "Knee valgus observed in reps 2 and 4.",
        ]
        ctx["coaching"] = coaching_with_warnings
        html = pdf_service.render_html(ctx)
        assert "Movement Quality Alerts" in html
        assert "Excessive forward lean" in html
        assert "Knee valgus" in html

    def test_no_safety_warnings_when_empty(self, pdf_service):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "Movement Quality Alerts" not in html


class TestPhase1RecommendedCues:
    def test_recommended_cues_rendered(self, pdf_service):
        ctx = _make_context()
        coaching_with_cues = dict(_COACHING)
        coaching_with_cues["recommended_cues"] = [
            "Push knees out over toes.",
            "Brace core before descent.",
        ]
        ctx["coaching"] = coaching_with_cues
        html = pdf_service.render_html(ctx)
        assert "Recommended Cues" in html
        assert "Push knees out" in html

    def test_no_cues_when_empty(self, pdf_service):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "<h3>Recommended Cues</h3>" not in html


class TestPhase1Citations:
    def test_citations_from_coaching(self, pdf_service):
        ctx = _make_context()
        coaching_with_citations = dict(_COACHING)
        coaching_with_citations["citations"] = [
            {
                "title": "Squat Depth and Muscle Activation",
                "authors": ["Schoenfeld, B.", "Grgic, J."],
                "year": 2020,
                "doi": "10.1234/example",
            },
        ]
        ctx["coaching"] = coaching_with_citations
        html = pdf_service.render_html(ctx)
        assert "Schoenfeld" in html
        assert "2020" in html
        assert "Squat Depth and Muscle Activation" in html

    def test_no_citations_shows_empty(self, pdf_service):
        ctx = _make_context()
        html = pdf_service.render_html(ctx)
        assert "No cited sources" in html
