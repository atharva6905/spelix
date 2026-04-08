"""PDF report generation service using WeasyPrint.

Requirements: FR-XPRT-02, FR-XPRT-03, NFR-PERF-07
Phase 0: static render written to output_path after coaching completes.
Template: reports/templates/analysis_report.html (self-contained; no external URLs).

Usage
-----
service = PDFService()
path = service.generate_pdf(context, "/tmp/spelix/abc123/report.pdf")
"""

from __future__ import annotations

import base64
import logging
import os
from string import Template

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

# Relative to the repo root (two levels up from backend/app/services/)
_DEFAULT_TEMPLATE_SUBPATH = os.path.join(
    os.path.dirname(__file__),          # backend/app/services/
    "..", "..", "..",                    # → repo root
    "reports", "templates",
    "analysis_report.html",
)
_DEFAULT_TEMPLATE_PATH = os.path.normpath(_DEFAULT_TEMPLATE_SUBPATH)

MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a substitute "
    "for in-person coaching or medical advice."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _confidence_badge_class(label: str) -> str:
    """Map confidence label to CSS badge class."""
    mapping = {
        "High": "badge-high",
        "Moderate": "badge-moderate",
        "Low": "badge-low",
        "Very Low": "badge-very-low",
    }
    return mapping.get(label, "badge-low")


def _build_rep_metrics_table(rep_metrics: list[dict]) -> str:
    """Render a per-rep metrics HTML table from the list of rep metric dicts.

    The column set is the union of all keys found across all reps, minus
    internal keys (rep_index is always col 0).  Unknown values render as '—'.
    """
    if not rep_metrics:
        return "<p style='color:#999;font-style:italic;font-size:9pt;'>No reps detected.</p>"

    # Collect all metric keys (excluding rep_index which we pin first)
    metric_keys: list[str] = []
    seen: set[str] = set()
    for rep in rep_metrics:
        for k in rep:
            if k != "rep_index" and k not in seen:
                metric_keys.append(k)
                seen.add(k)

    # Header row
    headers = ["Rep #"] + [k.replace("_", " ").title() for k in metric_keys]
    th_cells = "".join(f"<th>{h}</th>" for h in headers)
    header_row = f"<tr>{th_cells}</tr>"

    # Data rows
    rows_html: list[str] = []
    for rep in rep_metrics:
        rep_idx = rep.get("rep_index", "—")
        tds = f"<td>{rep_idx}</td>"
        for k in metric_keys:
            val = rep.get(k)
            if val is None:
                tds += "<td>—</td>"
            elif isinstance(val, float):
                tds += f"<td>{val:.1f}</td>"
            else:
                tds += f"<td>{val}</td>"
        rows_html.append(f"<tr>{tds}</tr>")

    return (
        "<table>"
        f"<thead>{header_row}</thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )


def _build_plot_block(plot_path: str | None) -> str:
    """Return an <img> tag with inline base64 PNG, or a placeholder."""
    if plot_path is None or not os.path.isfile(plot_path):
        return (
            '<div class="plot-placeholder">'
            "Angle time-series plot not available."
            "</div>"
        )
    try:
        with open(plot_path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        return (
            '<div class="plot-container">'
            f'<img src="data:image/png;base64,{b64}" alt="Angle time-series plot" />'
            "</div>"
        )
    except OSError:
        logger.warning("Could not read plot file at %s — skipping.", plot_path)
        return (
            '<div class="plot-placeholder">'
            "Angle time-series plot could not be loaded."
            "</div>"
        )


def _build_coaching_strengths(strengths: list[str]) -> str:
    if not strengths:
        return "<li>No strengths recorded.</li>"
    return "".join(f"<li>{s}</li>" for s in strengths)


def _build_coaching_issues_table(issues: list[dict]) -> str:
    if not issues:
        return "<p style='color:#999;font-style:italic;font-size:9pt;'>No form issues identified.</p>"

    rows_html: list[str] = []
    for issue in issues:
        severity = issue.get("severity", "Low")
        row_class = f"issue-row-{severity.lower()}"
        rep = issue.get("rep_number", "—")
        joint = issue.get("joint", "—")
        desc = issue.get("description", "—")
        rows_html.append(
            f'<tr class="{row_class}">'
            f"<td>{severity}</td>"
            f"<td>Rep {rep}</td>"
            f"<td>{joint}</td>"
            f"<td>{desc}</td>"
            "</tr>"
        )

    return (
        "<table>"
        "<thead><tr>"
        "<th>Severity</th><th>Rep</th><th>Joint</th><th>Description</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )


def _build_coaching_corrections(correction_plan: list[str]) -> str:
    if not correction_plan:
        return "<li>No corrections specified.</li>"
    return "".join(f"<li>{cue}</li>" for cue in correction_plan)


def _build_sources_block(sources: list | None) -> str:
    if not sources:
        return '<p class="sources-empty">No cited sources (Phase 0).</p>'
    items = "".join(f"<p class='sources-list'>{s}</p>" for s in sources)
    return items


# ---------------------------------------------------------------------------
# PDFService
# ---------------------------------------------------------------------------


class PDFService:
    """Generates PDF summary reports using WeasyPrint.

    Parameters
    ----------
    template_dir:
        Directory containing ``analysis_report.html``.  Defaults to
        ``<repo_root>/reports/templates/``.
    """

    def __init__(self, template_dir: str | None = None) -> None:
        if template_dir is None:
            self._template_path = _DEFAULT_TEMPLATE_PATH
        else:
            self._template_path = os.path.join(template_dir, "analysis_report.html")

        if not os.path.isfile(self._template_path):
            raise FileNotFoundError(
                f"PDF template not found at: {self._template_path}"
            )

        with open(self._template_path, encoding="utf-8") as fh:
            self._template_src = fh.read()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_html(self, context: dict) -> str:
        """Render the HTML template with values from *context*.

        Uses :class:`string.Template` substitution (``${key}`` placeholders).
        All derived/formatted values are computed here before substitution.

        Parameters
        ----------
        context:
            Dict with keys:
            - ``date`` (str) — ISO date string
            - ``exercise_type`` (str)
            - ``exercise_variant`` (str)
            - ``confidence_score`` (float, 0–1)
            - ``confidence_label`` (str)
            - ``rep_count`` (int)
            - ``rep_metrics`` (list[dict])
            - ``coaching`` (dict — CoachingOutput as dict)
            - ``plot_path`` (str | None)
            - ``disclaimer`` (str)

        Returns
        -------
        str
            Fully rendered HTML string ready for WeasyPrint.
        """
        coaching: dict = context.get("coaching") or {}
        confidence_score: float = float(context.get("confidence_score") or 0.0)
        confidence_label: str = context.get("confidence_label") or "Low"

        quality_gate_result = context.get("quality_gate_result")
        if quality_gate_result is None:
            qg_passed = True  # default if not provided
        elif isinstance(quality_gate_result, dict):
            qg_passed = bool(quality_gate_result.get("passed", True))
        else:
            qg_passed = bool(quality_gate_result)

        substitutions = {
            # Header
            "date": context.get("date", ""),
            "exercise_type": context.get("exercise_type", ""),
            "exercise_variant": context.get("exercise_variant", ""),
            "user_info": context.get("user_info", ""),
            # Summary card
            "rep_count": str(context.get("rep_count", 0)),
            "confidence_pct": f"{confidence_score * 100:.0f}",
            "confidence_label": confidence_label,
            "confidence_badge_class": _confidence_badge_class(confidence_label),
            "quality_gate_class": "qg-passed" if qg_passed else "qg-failed",
            "quality_gate_status": "Passed" if qg_passed else "Failed",
            # Rep metrics table
            "rep_metrics_table": _build_rep_metrics_table(
                context.get("rep_metrics") or []
            ),
            # Plot
            "plot_block": _build_plot_block(context.get("plot_path")),
            # Coaching
            "coaching_summary": coaching.get("summary", ""),
            "coaching_strengths": _build_coaching_strengths(
                coaching.get("strengths") or []
            ),
            "coaching_issues_table": _build_coaching_issues_table(
                coaching.get("issues") or []
            ),
            "coaching_corrections": _build_coaching_corrections(
                coaching.get("correction_plan") or []
            ),
            # Sources
            "sources_block": _build_sources_block(
                context.get("sources") or []
            ),
            # Footer disclaimer (also used in @page running footer)
            "disclaimer": context.get("disclaimer", MANDATORY_DISCLAIMER),
        }

        tmpl = Template(self._template_src)
        return tmpl.safe_substitute(substitutions)

    def generate_pdf(self, context: dict, output_path: str) -> str:
        """Render HTML → PDF → write to *output_path*.

        Parameters
        ----------
        context:
            Same structure as :meth:`render_html`.
        output_path:
            Absolute path where the PDF file will be written.

        Returns
        -------
        str
            The resolved *output_path* (same value passed in).
        """
        html_string = self.render_html(context)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        logger.info(
            "Generating PDF report for %s → %s",
            context.get("exercise_type", "unknown"),
            output_path,
        )

        from weasyprint import HTML  # lazy import — requires GTK system libs

        HTML(string=html_string).write_pdf(output_path)

        logger.info("PDF report written: %s", output_path)
        return output_path
