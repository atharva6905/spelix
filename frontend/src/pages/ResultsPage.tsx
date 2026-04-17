/**
 * ResultsPage
 *
 * Displays full analysis results: annotated video, coaching output,
 * rep metrics table, confidence badge, angle plot, and download links.
 *
 * Requirements: FR-RESL-01a–05, FR-RESL-08, FR-RESL-10–11,
 *               FR-SCOR-09–10, NFR-USAB-03
 */

import { useState } from "react";
import { useParams, Link } from "react-router";
import { useAnalysisDetail } from "@/hooks/useAnalysisDetail";
import type { CoachingIssue, Citation, RepMetricDetail } from "@/api/analyses";
import { parseWithCitations } from "@/components/CitationTooltip";
import ChatPanel from "@/components/ChatPanel";
import { AgentReasoningSidebar } from "@/components/AgentReasoningSidebar";
import {
  getConfidenceCategory,
  type ConfidenceCategory,
} from "@/lib/confidence";
import { API_BASE } from "@/api/config";

// ---------------------------------------------------------------------------
// Confidence helpers — never expose raw decimal (FR-SCOR-09–10, NFR-USAB-03)
// ---------------------------------------------------------------------------

const CONFIDENCE_STYLES: Record<ConfidenceCategory, string> = {
  High: "bg-green-100 text-green-800",
  Moderate: "bg-blue-100 text-blue-800",
  Low: "bg-yellow-100 text-yellow-800",
  "Very Low": "bg-red-100 text-red-800",
};

// Per-level guidance text — SRS FR-RESL-08
const CONFIDENCE_GUIDANCE: Record<ConfidenceCategory, string | null> = {
  High: "Results are reliable.",
  Moderate: "Partial occlusion detected — some metrics may be less precise.",
  Low: "Results may be unreliable — try better lighting or camera position.",
  "Very Low": "Unable to score reliably — please re-record.",
};

// ---------------------------------------------------------------------------
// Exercise display helpers
// ---------------------------------------------------------------------------

const EXERCISE_TYPE_LABELS: Record<string, string> = {
  squat: "Squat",
  bench: "Bench Press",
  deadlift: "Deadlift",
};

const EXERCISE_VARIANT_LABELS: Record<string, string> = {
  high_bar: "High Bar",
  low_bar: "Low Bar",
  flat: "Flat",
  incline: "Incline",
  decline: "Decline",
  conventional: "Conventional",
  sumo: "Sumo",
  romanian: "Romanian",
};

// ---------------------------------------------------------------------------
// Severity sort order (SRS Appendix D — High first)
// ---------------------------------------------------------------------------

const SEVERITY_ORDER: Record<CoachingIssue["severity"], number> = {
  High: 0,
  Medium: 1,
  Low: 2,
};

function sortIssuesBySeverity(issues: CoachingIssue[]): CoachingIssue[] {
  return [...issues].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  );
}

const SEVERITY_BADGE_STYLES: Record<CoachingIssue["severity"], string> = {
  High: "bg-red-100 text-red-800",
  Medium: "bg-yellow-100 text-yellow-800",
  Low: "bg-gray-100 text-gray-700",
};

// ---------------------------------------------------------------------------
// Form score descriptors (FR-SCOR-07)
// ---------------------------------------------------------------------------

function scoreDescriptor(score: number): string {
  if (score >= 9.0) return "Elite";
  if (score >= 7.5) return "Advanced";
  if (score >= 5.0) return "Intermediate";
  if (score >= 3.0) return "Needs Work";
  return "Needs Attention";
}

function scoreColorClass(score: number): string {
  if (score >= 7.5) return "bg-green-50 text-green-800 border-green-200";
  if (score >= 5.0) return "bg-amber-50 text-amber-800 border-amber-200";
  return "bg-red-50 text-red-800 border-red-200";
}

// ---------------------------------------------------------------------------
// Form score cards (FR-RESL-01, FR-SCOR-01 through FR-SCOR-08)
// ---------------------------------------------------------------------------

interface FormScoreCardsProps {
  safety: number | null | undefined;
  technique: number | null | undefined;
  pathBalance: number | null | undefined;
  control: number | null | undefined;
  overall: number | null | undefined;
}

function FormScoreCards({
  safety,
  technique,
  pathBalance,
  control,
  overall,
}: FormScoreCardsProps) {
  // If no scores exist at all, don't render the section (Phase 0 fallback)
  if (
    overall == null &&
    safety == null &&
    technique == null &&
    pathBalance == null &&
    control == null
  ) {
    return null;
  }

  const dimensions: Array<{
    label: string;
    score: number | null | undefined;
    testId: string;
  }> = [
    { label: "Movement Quality", score: safety, testId: "score-safety" },
    { label: "Technique", score: technique, testId: "score-technique" },
    {
      label: "Path & Balance",
      score: pathBalance,
      testId: "score-path-balance",
    },
    { label: "Control", score: control, testId: "score-control" },
  ];

  // Highlight Movement Quality if below 3.0 (FR-RESL-01)
  const movementQualityWarning = typeof safety === "number" && safety < 3.0;

  return (
    <div
      className="rounded-lg bg-white p-6 shadow-sm"
      data-testid="form-score-cards"
    >
      <h2 className="mb-4 text-lg font-semibold text-gray-900">
        Form Assessment
      </h2>

      {/* Overall Form Rating */}
      {typeof overall === "number" && (
        <div
          className="mb-4 rounded-md border-2 border-blue-200 bg-blue-50 px-6 py-4 text-center"
          data-testid="score-overall"
        >
          <div className="text-4xl font-bold text-blue-900">
            {overall.toFixed(1)}
          </div>
          <div className="mt-1 text-sm font-medium uppercase tracking-wide text-blue-700">
            Overall Form Rating — {scoreDescriptor(overall)}
          </div>
        </div>
      )}

      {/* Movement Quality alert (FR-RESL-01 — Movement Quality < 3.0 highlight) */}
      {movementQualityWarning && (
        <div
          className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800"
          data-testid="movement-quality-alert"
        >
          <strong>Movement Quality Alert:</strong> Your Movement Quality score
          is below 3.0. Review the coaching feedback below before your next
          session.
        </div>
      )}

      {/* Four dimension cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {dimensions.map(({ label, score, testId }) => {
          if (typeof score !== "number") {
            return (
              <div
                key={testId}
                className="rounded-md border border-gray-200 bg-gray-50 px-4 py-3 text-center"
                data-testid={testId}
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  {label}
                </div>
                <div className="mt-1 text-sm text-gray-400">Not available</div>
              </div>
            );
          }
          return (
            <div
              key={testId}
              className={`rounded-md border px-4 py-3 text-center ${scoreColorClass(
                score,
              )}`}
              data-testid={testId}
            >
              <div className="text-xs font-semibold uppercase tracking-wide">
                {label}
              </div>
              <div className="mt-1 text-2xl font-bold">{score.toFixed(1)}</div>
              <div className="mt-0.5 text-xs">{scoreDescriptor(score)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function LoadingSpinner() {
  return (
    <div
      role="status"
      aria-label="Loading analysis results"
      className="flex flex-col items-center gap-4 py-16"
    >
      <svg
        className="h-10 w-10 animate-spin text-blue-600"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <p className="text-gray-600">Loading results…</p>
    </div>
  );
}

interface ConfidenceBadgeProps {
  score: number | null;
}

function ConfidenceBadge({ score }: ConfidenceBadgeProps) {
  if (score === null) return null;

  const category = getConfidenceCategory(score);
  const styleClass = CONFIDENCE_STYLES[category];
  const guidance = CONFIDENCE_GUIDANCE[category];

  return (
    <div className="space-y-2">
      <span
        className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${styleClass}`}
        data-testid="confidence-badge"
      >
        Confidence: {category}
      </span>
      {guidance !== null && (
        <div
          role={category === "Low" || category === "Very Low" ? "alert" : undefined}
          className={`rounded-md px-4 py-3 text-sm ${
            category === "Low" || category === "Very Low"
              ? "bg-yellow-50 text-yellow-800"
              : category === "Moderate"
                ? "bg-blue-50 text-blue-700"
                : "bg-green-50 text-green-700"
          }`}
          data-testid="confidence-guidance"
        >
          {guidance}
        </div>
      )}
    </div>
  );
}

interface RepMetricsTableProps {
  repMetrics: RepMetricDetail[];
}

function RepMetricsTable({ repMetrics }: RepMetricsTableProps) {
  const [sortAsc, setSortAsc] = useState(true);

  if (repMetrics.length === 0) {
    return (
      <p className="text-sm text-gray-500">No rep data available.</p>
    );
  }

  const sortedMetrics = [...repMetrics].sort((a, b) =>
    sortAsc ? a.rep_index - b.rep_index : b.rep_index - a.rep_index,
  );

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-500">
              <button
                onClick={() => setSortAsc(!sortAsc)}
                className="inline-flex items-center gap-1"
                aria-sort={sortAsc ? "ascending" : "descending"}
              >
                Rep {sortAsc ? "▲" : "▼"}
              </button>
            </th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">
              Start Frame
            </th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">
              End Frame
            </th>
            <th className="px-4 py-3 text-left font-medium text-gray-500">
              Confidence
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {sortedMetrics.map((rep) => {
            const repConfidence =
              rep.confidence_score !== null
                ? getConfidenceCategory(rep.confidence_score)
                : null;
            return (
              <tr key={rep.rep_index}>
                <td className="px-4 py-3 font-medium text-gray-900">
                  {rep.rep_index + 1}
                </td>
                <td className="px-4 py-3 text-gray-600">{rep.start_frame}</td>
                <td className="px-4 py-3 text-gray-600">{rep.end_frame}</td>
                <td className="px-4 py-3">
                  {repConfidence !== null ? (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${CONFIDENCE_STYLES[repConfidence]}`}
                    >
                      {repConfidence}
                    </span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface CoachingOutputProps {
  structured: {
    summary?: string;
    strengths?: string[];
    issues?: CoachingIssue[];
    correction_plan?: string[];
    disclaimer?: string;
    // Phase 1 fields (FR-AICP-03, FR-AICP-06)
    safety_warnings?: string[];
    recommended_cues?: string[];
    citations?: Citation[];
    // Phase 2 fields (P2-019)
    degraded_mode?: boolean;
  };
}

function CoachingOutputSection({ structured }: CoachingOutputProps) {
  const sortedIssues = structured.issues
    ? sortIssuesBySeverity(structured.issues)
    : [];

  const citations = structured.citations ?? [];

  return (
    <div className="space-y-6">
      {/* Phase 2: Degraded mode banner (P2-019, FR-AICP-15) */}
      {structured.degraded_mode && (
        <div
          data-testid="degraded-mode-banner"
          className="rounded-md border-l-4 border-yellow-400 bg-yellow-50 p-4"
        >
          <p className="text-sm font-medium text-yellow-800">
            Results generated without research backing. Source references are
            unavailable for this analysis.
          </p>
        </div>
      )}

      {/* Summary */}
      {structured.summary && (
        <div data-testid="coaching-summary">
          <h3 className="mb-2 text-base font-semibold text-gray-900">
            Summary
          </h3>
          <p className="text-gray-700">
            {parseWithCitations(structured.summary, citations)}
          </p>
        </div>
      )}

      {/* Strengths */}
      {structured.strengths && structured.strengths.length > 0 && (
        <div data-testid="coaching-strengths">
          <h3 className="mb-2 text-base font-semibold text-gray-900">
            Strengths
          </h3>
          <ul className="list-disc space-y-1 pl-5">
            {structured.strengths.map((s, i) => (
              <li key={i} className="text-gray-700">
                {parseWithCitations(s, citations)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Issues sorted by severity */}
      {sortedIssues.length > 0 && (
        <div data-testid="coaching-issues">
          <h3 className="mb-2 text-base font-semibold text-gray-900">
            Issues to Address
          </h3>
          <ul className="space-y-3">
            {sortedIssues.map((issue, i) => (
              <li
                key={i}
                className="flex items-start gap-3 rounded-md border border-gray-100 p-3"
              >
                <span
                  className={`mt-0.5 flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_BADGE_STYLES[issue.severity]}`}
                >
                  {issue.severity}
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-800">
                    Rep {issue.rep_number} — {issue.joint}
                  </p>
                  <p className="text-sm text-gray-600">
                    {parseWithCitations(issue.description, citations)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Correction plan */}
      {structured.correction_plan && structured.correction_plan.length > 0 && (
        <div data-testid="coaching-correction-plan">
          <h3 className="mb-2 text-base font-semibold text-gray-900">
            Correction Plan
          </h3>
          <ol className="list-decimal space-y-1 pl-5">
            {structured.correction_plan.map((step, i) => (
              <li key={i} className="text-gray-700">
                {parseWithCitations(step, citations)}
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Phase 1: Movement Quality warnings (FR-AICP-03) */}
      {structured.safety_warnings && structured.safety_warnings.length > 0 && (
        <div
          data-testid="coaching-safety-warnings"
          className="rounded-md border-l-4 border-red-400 bg-red-50 p-4"
        >
          <h3 className="mb-2 text-base font-semibold text-red-900">
            Movement Quality Alerts
          </h3>
          <ul className="list-disc space-y-1 pl-5">
            {structured.safety_warnings.map((w, i) => (
              <li key={i} className="text-red-800">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Phase 1: Recommended cues (FR-AICP-03) */}
      {structured.recommended_cues && structured.recommended_cues.length > 0 && (
        <div data-testid="coaching-recommended-cues">
          <h3 className="mb-2 text-base font-semibold text-gray-900">
            Recommended Cues
          </h3>
          <ul className="list-disc space-y-1 pl-5">
            {structured.recommended_cues.map((cue, i) => (
              <li key={i} className="text-gray-700">
                {cue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Phase 1: Citations (FR-AICP-06) */}
      {structured.citations && structured.citations.length > 0 && (
        <div data-testid="coaching-citations">
          <h3 className="mb-2 text-base font-semibold text-gray-900">
            Cited Sources
          </h3>
          <ul className="space-y-2">
            {structured.citations.map((c, i) => (
              <li key={i} className="text-sm text-gray-600">
                {c.authors.join(", ")} ({c.year}).{" "}
                <em>{c.title}</em>
                {c.doi && <span> — DOI: {c.doi}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Disclaimer — verbatim per SRS */}
      <div
        data-testid="coaching-disclaimer"
        className="rounded-md bg-gray-50 px-4 py-3 text-xs text-gray-500"
      >
        {structured.disclaimer ??
          "This feedback is for educational purposes only and is not a substitute for in-person coaching or medical advice."}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const { analysis, isLoading, error } = useAnalysisDetail(id ?? "");
  const [isReasoningOpen, setIsReasoningOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-6">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-6">
        <div className="w-full max-w-md rounded-lg bg-white p-8 shadow-md">
          <div
            role="alert"
            className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            {error}
          </div>
          <Link
            to="/"
            className="mt-4 inline-block text-sm text-blue-600 hover:underline"
          >
            Back to home
          </Link>
        </div>
      </div>
    );
  }

  if (!analysis) return null;

  const exerciseTypeLabel =
    EXERCISE_TYPE_LABELS[analysis.exercise_type] ?? analysis.exercise_type;
  const exerciseVariantLabel =
    EXERCISE_VARIANT_LABELS[analysis.exercise_variant] ??
    analysis.exercise_variant;

  const coachingData = analysis.coaching_result?.structured_output_json;

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="mx-auto max-w-4xl space-y-8">

        {/* 7-day artifact banner */}
        <div className="rounded-md bg-blue-50 px-4 py-3 text-sm text-blue-700">
          Artifacts (video, plot, PDF) are available for 7 days from the date
          of analysis.
        </div>

        {/* Header — exercise type + variant + rep count + timestamp (FR-RESL-01a) */}
        <div className="rounded-lg bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-bold text-gray-900">
            {exerciseTypeLabel}{" "}
            <span className="font-normal text-gray-500">
              — {exerciseVariantLabel}
            </span>
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            Analysis ID: {analysis.id}
          </p>
          <p className="mt-1 text-sm text-gray-400">
            {analysis.rep_metrics?.length ?? 0} reps ·{" "}
            {new Date(analysis.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>

          {/* Confidence badge + per-level guidance (FR-SCOR-09–10, NFR-USAB-03, FR-RESL-08) */}
          <div className="mt-4">
            <ConfidenceBadge score={analysis.confidence_score} />
          </div>
        </div>

        {/* Phase 1: Form Score Cards (FR-RESL-01, FR-SCOR-01–08) */}
        <FormScoreCards
          safety={analysis.form_score_safety}
          technique={analysis.form_score_technique}
          pathBalance={analysis.form_score_path_balance}
          control={analysis.form_score_control}
          overall={analysis.form_score_overall}
        />

        {/* Annotated video player (FR-RESL-02) */}
        {analysis.annotated_video_path && (
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Annotated Video
            </h2>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video
              controls
              className="w-full rounded-md"
              src={analysis.annotated_video_path}
              data-testid="annotated-video"
            >
              Your browser does not support the video element.
            </video>
            <a
              href={analysis.annotated_video_path}
              download
              className="mt-2 inline-flex items-center text-sm text-blue-600 hover:underline"
              data-testid="annotated-video-download"
            >
              Download annotated video
            </a>
          </div>
        )}

        {/* Coaching output (FR-RESL-03) */}
        {coachingData && (
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Coaching Feedback
              </h2>
              {(analysis.coaching_result?.agent_trace_json?.nodes_executed?.length ?? 0) > 0 && (
                <button
                  type="button"
                  onClick={() => setIsReasoningOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
                  data-testid="open-reasoning-sidebar"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.8}
                    stroke="currentColor"
                    className="h-3.5 w-3.5"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.847.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z"
                    />
                  </svg>
                  How AI Reasoned
                </button>
              )}
            </div>
            <CoachingOutputSection
              structured={
                coachingData as Parameters<typeof CoachingOutputSection>[0]["structured"]
              }
            />
          </div>
        )}

        <AgentReasoningSidebar
          isOpen={isReasoningOpen}
          trace={analysis.coaching_result?.agent_trace_json ?? null}
          onClose={() => setIsReasoningOpen(false)}
        />

        {/* Follow-up chat (FR-RESL-09, FR-AICP-17) */}
        {coachingData && <ChatPanel analysisId={analysis.id} />}

        {/* Rep metrics table (FR-RESL-04) */}
        <div className="rounded-lg bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Rep Metrics
          </h2>
          <RepMetricsTable repMetrics={analysis.rep_metrics} />
        </div>

        {/* Angle plot (FR-RESL-05) */}
        {analysis.plot_path && (
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Angle Plot
            </h2>
            <img
              src={analysis.plot_path}
              alt="Joint angle time-series plot"
              className="w-full rounded-md"
              data-testid="angle-plot"
            />
          </div>
        )}

        {/* Download links (FR-RESL-08, FR-RESL-10–11) */}
        <div className="rounded-lg bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Downloads
          </h2>
          <div className="flex flex-wrap gap-3">
            {/* CSV export — constructed from analysis id */}
            <a
              href={`${API_BASE}/api/v1/analyses/${analysis.id}/export/csv`}
              className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
              data-testid="csv-download"
            >
              Download CSV
            </a>

            {/* PDF report (if available) */}
            {analysis.pdf_path && (
              <a
                href={analysis.pdf_path}
                className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
                data-testid="pdf-download"
              >
                Download PDF Report
              </a>
            )}
          </div>
        </div>

        {/* Three-tier disclaimer — SRS FR-RESL-11 */}
        <div data-testid="three-tier-disclaimer" className="rounded-lg bg-white p-6 shadow-sm space-y-3">
          <h2 className="text-sm font-semibold text-gray-600">Important Information</h2>
          <p className="text-xs text-gray-500">
            This analysis is for fitness and performance purposes only and is not medical advice. Consult a qualified healthcare professional before beginning or modifying any exercise program.
          </p>
          <p className="text-xs text-gray-500">
            Generated by automated systems with inherent limitations. Results are probabilistic estimates, not clinical evaluations.
          </p>
          <p className="text-xs text-gray-500">
            Physical exercise carries inherent risk. You assume responsibility for your exercise choices.
          </p>
        </div>

        {/* Back link */}
        <div className="pb-8">
          <Link
            to="/"
            className="text-sm text-blue-600 hover:underline"
          >
            Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
