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

# Resolve PDF template path — priority list mirrors ThresholdConfig (ADR-046a).
# 1. Relative to __file__ (works locally: backend/app/services/ → ../../.. → repo root)
# 2. Relative to CWD (works in Docker: CWD=/app, template at /app/reports/templates/)
_TEMPLATE_FILENAME = os.path.join("reports", "templates", "analysis_report.html")
_CANDIDATE_PATHS = [
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", _TEMPLATE_FILENAME)),
    os.path.normpath(os.path.join(os.getcwd(), _TEMPLATE_FILENAME)),
]
_DEFAULT_TEMPLATE_PATH = next(
    (p for p in _CANDIDATE_PATHS if os.path.isfile(p)),
    _CANDIDATE_PATHS[0],  # fallback — will raise FileNotFoundError in __init__
)

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
        return '<p class="sources-empty">No cited sources.</p>'
    items: list[str] = []
    for src in sources:
        if isinstance(src, dict):
            authors = ", ".join(src.get("authors", []))
            title = src.get("title", "")
            year = src.get("year", "")
            doi = src.get("doi")
            entry = f"{authors} ({year}). <em>{title}</em>"
            if doi:
                entry += f". DOI: {doi}"
            items.append(f"<p class='sources-list'>{entry}</p>")
        else:
            items.append(f"<p class='sources-list'>{src}</p>")
    return "".join(items)


def _score_descriptor(score: float) -> str:
    """Map a 1-10 form score to a descriptor label."""
    if score >= 9.0:
        return "Elite"
    if score >= 7.5:
        return "Advanced"
    if score >= 5.0:
        return "Intermediate"
    if score >= 3.0:
        return "Needs Work"
    return "Needs Attention"


def _score_color(score: float) -> str:
    """Map a 1-10 score to a pill color."""
    if score >= 7.5:
        return "#155724"  # green
    if score >= 5.0:
        return "#856404"  # amber
    return "#721c24"  # red


def _score_bg(score: float) -> str:
    """Map a 1-10 score to a pill background."""
    if score >= 7.5:
        return "#d4edda"
    if score >= 5.0:
        return "#fff3cd"
    return "#f8d7da"


def _build_score_pills(scores: dict | None) -> str:
    """Build the four dimension score pills + overall rating.

    scores: dict with keys form_score_safety, form_score_technique,
    form_score_path_balance, form_score_control, form_score_overall.
    """
    if not scores:
        return ""

    overall = scores.get("form_score_overall")
    if overall is None:
        return ""

    dimensions = [
        ("Movement Quality", scores.get("form_score_safety")),
        ("Technique", scores.get("form_score_technique")),
        ("Path & Balance", scores.get("form_score_path_balance")),
        ("Control", scores.get("form_score_control")),
    ]

    # Overall rating card
    overall_desc = _score_descriptor(overall)
    html = (
        '<div class="overall-score">'
        f'<span class="overall-value">{overall:.1f}</span>'
        f'<span class="overall-label">Overall Form Rating &mdash; {overall_desc}</span>'
        "</div>"
    )

    # Dimension pills
    html += '<div class="score-pills">'
    for name, val in dimensions:
        if val is None:
            continue
        bg = _score_bg(val)
        fg = _score_color(val)
        html += (
            f'<span class="score-pill" style="background:{bg};color:{fg};">'
            f"{name}: {val:.1f}"
            "</span>"
        )
    html += "</div>"
    return html


def _build_safety_warnings(warnings: list[str] | None) -> str:
    """Build a Movement Quality warning banner."""
    if not warnings:
        return ""
    items = "".join(f"<li>{w}</li>" for w in warnings)
    return (
        '<div class="safety-warning">'
        '<div class="warning-title">Movement Quality Alerts</div>'
        f"<ul>{items}</ul>"
        "</div>"
    )


def _build_recommended_cues(cues: list[str] | None) -> str:
    """Build recommended coaching cues section."""
    if not cues:
        return ""
    items = "".join(f"<li>{c}</li>" for c in cues)
    return (
        '<div class="coaching-block">'
        "<h3>Recommended Cues</h3>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def _build_bar_path_block(bar_path_plot_path: str | None) -> str:
    """Return an <img> tag with inline base64 bar path PNG, or empty."""
    if bar_path_plot_path is None or not os.path.isfile(bar_path_plot_path):
        return ""
    try:
        with open(bar_path_plot_path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        return (
            '<div class="section">'
            '<div class="section-title">Bar Path</div>'
            '<div class="plot-container">'
            f'<img src="data:image/png;base64,{b64}" alt="Bar path plot" '
            'style="max-width:300px;margin:0 auto;display:block;" />'
            "</div></div>"
        )
    except OSError:
        logger.warning("Could not read bar path plot at %s", bar_path_plot_path)
        return ""


def _build_keyframes_block(keyframes: list) -> str:
    """Render keyframe images for each rep (start, depth, end)."""
    if not keyframes:
        return ""
    html_parts = [
        '<div class="section">',
        '<div class="section-title">Rep Keyframes</div>',
    ]
    for kf in keyframes:
        rep_num = getattr(kf, "rep_index", 0) + 1
        html_parts.append('<div style="margin-bottom:12pt;">')
        html_parts.append(f'<div style="font-weight:600;margin-bottom:4pt;">Rep {rep_num}</div>')
        html_parts.append('<div style="display:flex;gap:6pt;">')
        for label, attr in [("Start", "start_image_b64"), ("Depth", "depth_image_b64"), ("End", "end_image_b64")]:
            b64 = getattr(kf, attr, None)
            if b64:
                html_parts.append(
                    f'<div style="text-align:center;flex:1;">'
                    f'<img src="data:image/jpeg;base64,{b64}" '
                    f'style="max-width:150px;border:1px solid #ddd;border-radius:4px;" '
                    f'alt="Rep {rep_num} {label}" />'
                    f'<div style="font-size:7pt;color:#666;margin-top:2pt;">{label}</div>'
                    f"</div>"
                )
        html_parts.append("</div></div>")
    html_parts.append("</div>")
    return "".join(html_parts)


def generate_bar_path_plot(bar_path: dict, output_path: str) -> str:
    """Generate a bar path scatter/line plot from centroid data.

    Parameters
    ----------
    bar_path:
        Dict with ``centroids`` key — list of (x, y) normalized tuples.
    output_path:
        Where to write the PNG file.

    Returns
    -------
    str
        The output_path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    centroids = bar_path.get("centroids", [])
    if not centroids:
        return output_path

    xs = [c[0] for c in centroids]
    ys = [c[1] for c in centroids]

    fig, ax = plt.subplots(figsize=(3, 5))
    # Plot path with gradient coloring (start=blue, end=red)
    n = len(xs)
    cmap = plt.get_cmap("coolwarm")
    colors = cmap([i / max(n - 1, 1) for i in range(n)])
    ax.scatter(xs, ys, c=colors, s=4, zorder=3)
    ax.plot(xs, ys, color="#cccccc", linewidth=0.8, alpha=0.6, zorder=2)

    # Invert Y axis (image coords: y increases downward)
    ax.invert_yaxis()
    ax.set_xlabel("Lateral Position", fontsize=8)
    ax.set_ylabel("Vertical Position", fontsize=8)
    ax.set_title("Bar Path", fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=7)

    # Add stats annotation
    lateral = bar_path.get("lateral_deviation_px") or bar_path.get("horizontal_drift")
    if lateral is not None:
        ax.annotate(
            f"Lateral dev: {float(lateral):.3f}",
            xy=(0.02, 0.98), xycoords="axes fraction",
            fontsize=7, va="top", color="#666",
        )

    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


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
            # Bar path chart (FR-XPRT-02)
            "bar_path_block": _build_bar_path_block(
                context.get("bar_path_plot_path")
            ),
            # Keyframe captures (FR-XPRT-02)
            "keyframes_block": _build_keyframes_block(
                context.get("keyframes") or []
            ),
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
            # Phase 1: Scoring pills, safety warnings, recommended cues
            "score_pills": _build_score_pills(context.get("scores")),
            "safety_warnings": _build_safety_warnings(
                coaching.get("safety_warnings") or []
            ),
            "recommended_cues": _build_recommended_cues(
                coaching.get("recommended_cues") or []
            ),
            # Sources — Phase 1 uses coaching citations
            "sources_block": _build_sources_block(
                coaching.get("citations") or context.get("sources") or []
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
