/**
 * ExpertAnalysisDetailPage — Anonymized analysis detail + annotation form.
 *
 * Requirements:
 * - FR-EXPV-01: Role check (expert_reviewer or admin only)
 * - FR-EXPV-03: Anonymized analysis detail view
 * - FR-EXPV-04: Annotation submission form
 * - FR-EXPV-07: Golden dataset labelling
 */

import { useState, useEffect, useCallback } from "react";
import { useParams, Link, Navigate } from "react-router";
import { supabase } from "@/lib/supabase";
import {
  getExpertAnalysis,
  submitAnnotation,
  getAnnotations,
  type ExpertAnalysisDetail,
  type AnnotationCreate,
  type AnnotationResponse,
} from "@/api/expert";
import UnvalidatedMetricsPanel from "@/components/UnvalidatedMetricsPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Confidence category — never shows raw decimal (NFR-USAB-03).
 * Thresholds per SRS: High ≥0.80, Moderate 0.65–0.79, Low 0.50–0.64, Very Low <0.50.
 */
function confidenceCategory(score: number | null): string {
  if (score === null) return "Unknown";
  if (score >= 0.8) return "High";
  if (score >= 0.65) return "Moderate";
  if (score >= 0.5) return "Low";
  return "Very Low";
}

const CONFIDENCE_BADGE_STYLES: Record<string, string> = {
  High: "bg-green-100 text-green-700",
  Moderate: "bg-blue-100 text-blue-700",
  Low: "bg-yellow-100 text-yellow-700",
  "Very Low": "bg-red-100 text-red-700",
  Unknown: "bg-gray-100 text-gray-500",
};

/**
 * Form score descriptor — Elite/Advanced/Intermediate/Needs Work/Needs Attention.
 * Per SRS FR-SCOR-07 thresholds.
 */
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

const EXERCISE_ISSUES: Record<string, Array<{ key: string; label: string }>> = {
  squat: [
    { key: "insufficient_depth", label: "Insufficient depth" },
    { key: "excessive_forward_lean", label: "Excessive forward lean" },
    { key: "knee_tracking", label: "Knee tracking issues at depth" },
    { key: "incomplete_lockout", label: "Incomplete lockout" },
    { key: "inconsistent_tempo", label: "Inconsistent rep tempo" },
  ],
  bench: [
    { key: "shoulder_angle_high", label: "Excessive shoulder angle at bottom" },
    { key: "incomplete_lockout", label: "Incomplete lockout" },
    { key: "inconsistent_tempo", label: "Inconsistent rep tempo" },
    { key: "bar_path_deviation", label: "Bar path deviation" },
  ],
  deadlift: [
    { key: "excessive_torso_lean", label: "Excessive torso lean at start" },
    { key: "incomplete_lockout", label: "Incomplete hip extension at lockout" },
    { key: "inconsistent_tempo", label: "Inconsistent rep tempo" },
    { key: "bar_path_deviation", label: "Bar path deviation" },
  ],
};

// ---------------------------------------------------------------------------
// Score card
// ---------------------------------------------------------------------------

interface ScoreCardProps {
  label: string;
  score: number | null | undefined;
}

function ScoreCard({ label, score }: ScoreCardProps) {
  if (score == null) {
    return (
      <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
        <p className="text-xs font-medium text-gray-500">{label}</p>
        <p className="mt-1 text-sm text-gray-400">Not available</p>
      </div>
    );
  }

  return (
    <div className={`rounded-md border p-3 ${scoreColorClass(score)}`}>
      <p className="text-xs font-medium opacity-70">{label}</p>
      <p className="mt-1 text-lg font-bold">{score.toFixed(1)}</p>
      <p className="text-xs">{scoreDescriptor(score)}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Eval scores card (structured replacement for raw JSON)
// ---------------------------------------------------------------------------

function EvalScoresCard({ scores }: { scores: Record<string, unknown> }) {
  const faithfulness =
    typeof scores.faithfulness === "number" ? scores.faithfulness : null;
  const passed = scores.faithfulness_passed === true;
  const coveVerified = scores.cove_verified === true;
  const coveIterations =
    typeof scores.cove_iterations === "number" ? scores.cove_iterations : null;
  const unsupported = Array.isArray(scores.unsupported_claims)
    ? (scores.unsupported_claims as string[])
    : [];

  return (
    <div className="mt-4 space-y-3">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        Eval Scores
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {faithfulness !== null && (
          <div
            className={`rounded-md border p-3 ${passed ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}`}
          >
            <p className="text-xs text-gray-500">Faithfulness</p>
            <p
              className={`text-lg font-semibold ${passed ? "text-green-700" : "text-red-700"}`}
            >
              {Math.round(faithfulness * 100)}%
            </p>
            <span
              className={`text-xs ${passed ? "text-green-600" : "text-red-600"}`}
            >
              {passed ? "Passed" : "Below threshold"}
            </span>
          </div>
        )}
        <div
          className={`rounded-md border p-3 ${coveVerified ? "border-green-200 bg-green-50" : "border-yellow-200 bg-yellow-50"}`}
        >
          <p className="text-xs text-gray-500">Fact-Check (CoVe)</p>
          <p
            className={`text-lg font-semibold ${coveVerified ? "text-green-700" : "text-yellow-700"}`}
          >
            {coveVerified ? "Verified" : "Not verified"}
          </p>
          {coveIterations !== null && (
            <span className="text-xs text-gray-500">
              {coveIterations} iteration{coveIterations !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>
      {unsupported.length > 0 && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3">
          <p className="mb-1 text-xs font-medium text-red-700">
            Unsupported Claims
          </p>
          <ul className="list-inside list-disc space-y-1 text-sm text-red-600">
            {unsupported.map((claim, i) => (
              <li key={i}>{claim}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Coaching output renderer
// ---------------------------------------------------------------------------

interface CoachingOutputProps {
  coachingResult: Record<string, unknown> | null;
}

function CoachingOutput({ coachingResult }: CoachingOutputProps) {
  const [agentTraceOpen, setAgentTraceOpen] = useState(false);

  if (!coachingResult) {
    return (
      <p className="text-sm text-gray-400">No coaching output available for this analysis.</p>
    );
  }

  const structured = coachingResult.structured_output_json as Record<string, unknown> | null;
  const agentTrace = coachingResult.agent_trace as Record<string, unknown> | null;

  return (
    <div className="space-y-4">
      {structured ? (
        <>
          {/* Summary */}
          {typeof structured.summary === "string" && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-gray-700">Summary</h3>
              <p className="text-sm text-gray-600">{structured.summary}</p>
            </div>
          )}

          {/* Safety warnings — never label as "safety"; keep as Movement Quality alerts */}
          {Array.isArray(structured.safety_warnings) && structured.safety_warnings.length > 0 && (
            <div className="rounded-md bg-red-50 p-3">
              <h3 className="mb-1 text-sm font-semibold text-red-700">Movement Quality Alerts</h3>
              <ul className="list-inside list-disc space-y-1">
                {(structured.safety_warnings as string[]).map((w, i) => (
                  <li key={i} className="text-sm text-red-600">{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Strengths */}
          {Array.isArray(structured.strengths) && structured.strengths.length > 0 && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-gray-700">Strengths</h3>
              <ul className="list-inside list-disc space-y-1">
                {(structured.strengths as string[]).map((s, i) => (
                  <li key={i} className="text-sm text-gray-600">{s}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Issues */}
          {Array.isArray(structured.issues) && structured.issues.length > 0 && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-gray-700">Issues</h3>
              <ul className="space-y-2">
                {(structured.issues as Array<Record<string, unknown>>).map((issue, i) => (
                  <li key={i} className="rounded-md border border-gray-200 bg-gray-50 p-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          issue.severity === "High"
                            ? "bg-red-100 text-red-700"
                            : issue.severity === "Medium"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {String(issue.severity ?? "Unknown")}
                      </span>
                      <span className="text-sm font-medium text-gray-800">
                        {String(issue.description ?? "")}
                      </span>
                    </div>
                    {issue.correction != null && (
                      <p className="mt-1 text-xs text-gray-500">{String(issue.correction)}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommended cues */}
          {Array.isArray(structured.recommended_cues) && structured.recommended_cues.length > 0 && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-gray-700">Recommended Cues</h3>
              <ul className="list-inside list-disc space-y-1">
                {(structured.recommended_cues as string[]).map((cue, i) => (
                  <li key={i} className="text-sm text-gray-600">{cue}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Citations */}
          {Array.isArray(structured.citations) && structured.citations.length > 0 && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-gray-700">Citations</h3>
              <ol className="list-decimal pl-4 space-y-1">
                {(structured.citations as Array<Record<string, unknown>>).map((c, i) => (
                  <li key={i} className="text-xs text-gray-500">
                    {Array.isArray(c.authors) ? (c.authors as string[]).join(", ") : ""}
                    {c.year ? ` (${c.year})` : ""}
                    {c.title ? ` — ${c.title}` : ""}
                    {c.doi ? (
                      <span className="ml-1 font-mono text-indigo-500">{String(c.doi)}</span>
                    ) : null}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </>
      ) : (
        <p className="text-sm text-gray-400">Structured output not available.</p>
      )}

      {/* Agent trace — collapsible */}
      {agentTrace && (
        <div>
          <button
            type="button"
            onClick={() => setAgentTraceOpen((v) => !v)}
            className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-700"
          >
            <span>{agentTraceOpen ? "\u25BC" : "\u25B6"}</span>
            Agent Trace
          </button>
          {agentTraceOpen && (
            <pre className="mt-2 overflow-x-auto rounded-md bg-gray-900 p-4 text-xs text-gray-300">
              {JSON.stringify(agentTrace, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Previous annotations (read-only)
// ---------------------------------------------------------------------------

interface PreviousAnnotationsProps {
  annotations: AnnotationResponse[];
}

function PreviousAnnotations({ annotations }: PreviousAnnotationsProps) {
  if (annotations.length === 0) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-900">Previous Annotations</h2>
      {annotations.map((ann) => (
        <div
          key={ann.id}
          className="rounded-md border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-xs text-gray-400">{ann.id.slice(0, 8)}&hellip;</span>
            <span className="text-xs text-gray-400">{formatDate(ann.created_at)}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <div>
              <span className="text-xs font-medium text-gray-500">Quality Score</span>
              <p>{ann.coaching_quality_score ?? "—"}</p>
            </div>
            <div>
              <span className="text-xs font-medium text-gray-500">Movement Advice Accurate</span>
              <p>
                {ann.movement_advice_accurate === true
                  ? "Yes"
                  : ann.movement_advice_accurate === false
                  ? "No"
                  : "N/A"}
              </p>
            </div>
            <div>
              <span className="text-xs font-medium text-gray-500">Engagement Advice Accurate</span>
              <p>
                {ann.engagement_advice_accurate === true
                  ? "Yes"
                  : ann.engagement_advice_accurate === false
                  ? "No"
                  : "N/A"}
              </p>
            </div>
          </div>
          {ann.suggested_corrections && (
            <div className="mt-2">
              <span className="text-xs font-medium text-gray-500">Suggested Corrections</span>
              <p className="mt-0.5 text-sm">{ann.suggested_corrections}</p>
            </div>
          )}
          {ann.is_golden_label && (
            <span className="mt-2 inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              Golden Dataset Entry
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Annotation form — FR-EXPV-04 + FR-EXPV-07
// ---------------------------------------------------------------------------

type RadioValue = "yes" | "no" | "na";
type Severity = "High" | "Medium" | "Low";

interface IssueEntry {
  checked: boolean;
  severity: Severity;
  notes: string;
}

interface SourceEntry {
  id: string;
  title: string;
  authors: string;
  year: string;
  doi: string;
}

interface AnnotationFormState {
  coaching_quality_score: string;
  movement_advice_accurate: RadioValue | "";
  engagement_advice_accurate: RadioValue | "";
  issues: Record<string, IssueEntry>;
  ai_missed_issue: string;
  ai_false_positive: string;
  suggested_corrections: string;
  sources: SourceEntry[];
  is_golden_label: boolean;
}

interface AnnotationFormProps {
  analysisId: string;
  exerciseType: string;
  onSuccess: (ann: AnnotationResponse) => void;
}

let sourceIdCounter = 0;

function AnnotationForm({ analysisId, exerciseType, onSuccess }: AnnotationFormProps) {
  const [form, setForm] = useState<AnnotationFormState>({
    coaching_quality_score: "",
    movement_advice_accurate: "",
    engagement_advice_accurate: "",
    issues: {},
    ai_missed_issue: "",
    ai_false_positive: "",
    suggested_corrections: "",
    sources: [],
    is_golden_label: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  function radioToBool(val: RadioValue | ""): boolean | null {
    if (val === "yes") return true;
    if (val === "no") return false;
    return null;
  }

  function updateIssue(key: string, patch: Partial<IssueEntry>) {
    setForm((f) => ({
      ...f,
      issues: {
        ...f.issues,
        [key]: {
          checked: f.issues[key]?.checked ?? false,
          severity: f.issues[key]?.severity ?? "Medium",
          notes: f.issues[key]?.notes ?? "",
          ...patch,
        },
      },
    }));
  }

  function addSource() {
    sourceIdCounter += 1;
    setForm((f) => ({
      ...f,
      sources: [...f.sources, { id: `src-${sourceIdCounter}`, title: "", authors: "", year: "", doi: "" }],
    }));
  }

  function removeSource(id: string) {
    setForm((f) => ({ ...f, sources: f.sources.filter((s) => s.id !== id) }));
  }

  function updateSource(id: string, patch: Partial<Omit<SourceEntry, "id">>) {
    setForm((f) => ({
      ...f,
      sources: f.sources.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    }));
  }

  async function handleSubmit() {
    setSubmitError(null);

    const qualityNum = form.coaching_quality_score
      ? parseFloat(form.coaching_quality_score)
      : null;

    if (qualityNum !== null && (qualityNum < 1.0 || qualityNum > 10.0)) {
      setSubmitError("Coaching quality score must be between 1.0 and 10.0.");
      return;
    }

    const issuesPayload: Record<string, unknown> = {};
    for (const { key } of EXERCISE_ISSUES[exerciseType] ?? []) {
      const entry = form.issues[key];
      if (entry?.checked) {
        issuesPayload[key] = { severity: entry.severity, notes: entry.notes || undefined };
      }
    }
    if (form.ai_missed_issue.trim())
      issuesPayload.ai_missed_issue = { text: form.ai_missed_issue.trim() };
    if (form.ai_false_positive.trim())
      issuesPayload.ai_false_positive = { text: form.ai_false_positive.trim() };

    const citedPayload = form.sources
      .filter((s) => s.title.trim())
      .map((s) => ({
        title: s.title.trim(),
        authors: s.authors.split(",").map((a) => a.trim()).filter(Boolean),
        year: parseInt(s.year, 10) || null,
        doi: s.doi.trim() || null,
      }));

    const payload: AnnotationCreate = {
      coaching_quality_score: qualityNum,
      movement_advice_accurate: radioToBool(form.movement_advice_accurate),
      engagement_advice_accurate: radioToBool(form.engagement_advice_accurate),
      issues_identified: issuesPayload,
      suggested_corrections: form.suggested_corrections.trim() || null,
      cited_sources: citedPayload,
      is_golden_label: form.is_golden_label,
    };

    setSubmitting(true);
    try {
      const result = await submitAnnotation(analysisId, payload);
      setSubmitSuccess(true);
      onSuccess(result);
    } catch (err) {
      console.error("Failed to submit annotation", err);
      setSubmitError("Failed to submit annotation. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitSuccess) {
    return (
      <div className="rounded-md bg-green-50 p-4 text-sm text-green-700">
        Annotation submitted successfully.
      </div>
    );
  }

  const exerciseIssues = EXERCISE_ISSUES[exerciseType] ?? [];

  return (
    <div className="space-y-5">
      {submitError && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-600">{submitError}</div>
      )}

      {/* Coaching quality score */}
      <div>
        <label htmlFor="coaching_quality_score" className="mb-1 block text-sm font-medium text-gray-700">
          Coaching Quality Score (1.0–10.0)
        </label>
        <input
          id="coaching_quality_score"
          type="number"
          min={1.0}
          max={10.0}
          step={0.1}
          value={form.coaching_quality_score}
          onChange={(e) => setForm((f) => ({ ...f, coaching_quality_score: e.target.value }))}
          className="w-32 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          placeholder="e.g. 7.5"
        />
      </div>

      {/* Movement advice accurate (D-029) */}
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-gray-700">
          Movement Quality Advice Accurate?
        </legend>
        <div className="flex gap-4">
          {(["yes", "no", "na"] as RadioValue[]).map((val) => (
            <label key={val} className="flex items-center gap-1.5 text-sm text-gray-600">
              <input
                type="radio"
                name="movement_advice_accurate"
                value={val}
                checked={form.movement_advice_accurate === val}
                onChange={() => setForm((f) => ({ ...f, movement_advice_accurate: val }))}
                className="text-indigo-600"
              />
              {val === "yes" ? "Yes" : val === "no" ? "No" : "N/A"}
            </label>
          ))}
        </div>
      </fieldset>

      {/* Engagement advice accurate */}
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-gray-700">
          Engagement Advice Accurate?
        </legend>
        <div className="flex gap-4">
          {(["yes", "no", "na"] as RadioValue[]).map((val) => (
            <label key={val} className="flex items-center gap-1.5 text-sm text-gray-600">
              <input
                type="radio"
                name="engagement_advice_accurate"
                value={val}
                checked={form.engagement_advice_accurate === val}
                onChange={() => setForm((f) => ({ ...f, engagement_advice_accurate: val }))}
                className="text-indigo-600"
              />
              {val === "yes" ? "Yes" : val === "no" ? "No" : "N/A"}
            </label>
          ))}
        </div>
      </fieldset>

      {/* Issues identified — exercise-specific checkboxes */}
      <fieldset>
        <legend className="mb-2 text-sm font-medium text-gray-700">Issues Identified</legend>
        <div className="space-y-2">
          {exerciseIssues.map(({ key, label }) => {
            const entry = form.issues[key];
            const checked = entry?.checked ?? false;
            return (
              <div key={key} className="rounded-md border border-gray-200 p-3">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => updateIssue(key, { checked: e.target.checked })}
                    className="rounded text-indigo-600"
                  />
                  {label}
                </label>
                {checked && (
                  <div className="mt-2 flex flex-wrap items-center gap-3 pl-6">
                    <select
                      aria-label={`${label} severity`}
                      value={entry?.severity ?? "Medium"}
                      onChange={(e) => updateIssue(key, { severity: e.target.value as Severity })}
                      className="rounded-md border border-gray-300 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none"
                    >
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                      <option value="Low">Low</option>
                    </select>
                    <input
                      type="text"
                      aria-label={`${label} notes`}
                      placeholder="Notes (optional)"
                      value={entry?.notes ?? ""}
                      onChange={(e) => updateIssue(key, { notes: e.target.value })}
                      className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none"
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-3 space-y-2">
          <div>
            <label htmlFor="ai_missed_issue" className="mb-1 block text-xs font-medium text-gray-600">
              AI missed an issue
            </label>
            <input
              id="ai_missed_issue"
              type="text"
              value={form.ai_missed_issue}
              onChange={(e) => setForm((f) => ({ ...f, ai_missed_issue: e.target.value }))}
              placeholder="Describe any issue the AI failed to identify..."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="ai_false_positive" className="mb-1 block text-xs font-medium text-gray-600">
              AI identified a non-issue
            </label>
            <input
              id="ai_false_positive"
              type="text"
              value={form.ai_false_positive}
              onChange={(e) => setForm((f) => ({ ...f, ai_false_positive: e.target.value }))}
              placeholder="Describe any false positive from the AI..."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none"
            />
          </div>
        </div>
      </fieldset>

      {/* Suggested corrections */}
      <div>
        <label htmlFor="suggested_corrections" className="mb-1 block text-sm font-medium text-gray-700">
          Suggested Corrections
        </label>
        <textarea
          id="suggested_corrections"
          rows={3}
          value={form.suggested_corrections}
          onChange={(e) => setForm((f) => ({ ...f, suggested_corrections: e.target.value }))}
          placeholder="Describe specific corrections the coaching output should have included..."
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
        />
      </div>

      {/* Cited sources — structured rows */}
      <fieldset>
        <legend className="mb-2 text-sm font-medium text-gray-700">Cited Sources</legend>
        <div className="space-y-3">
          {form.sources.map((src) => (
            <div key={src.id} className="rounded-md border border-gray-200 p-3">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <input
                  type="text"
                  aria-label="Source title"
                  placeholder="Title"
                  value={src.title}
                  onChange={(e) => updateSource(src.id, { title: e.target.value })}
                  className="col-span-2 rounded-md border border-gray-300 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none"
                />
                <input
                  type="text"
                  aria-label="Source authors"
                  placeholder="Authors (comma-separated)"
                  value={src.authors}
                  onChange={(e) => updateSource(src.id, { authors: e.target.value })}
                  className="col-span-2 rounded-md border border-gray-300 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none"
                />
                <input
                  type="text"
                  aria-label="Source year"
                  placeholder="Year"
                  value={src.year}
                  onChange={(e) => updateSource(src.id, { year: e.target.value })}
                  className="rounded-md border border-gray-300 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none"
                />
                <input
                  type="text"
                  aria-label="Source DOI"
                  placeholder="DOI (optional)"
                  value={src.doi}
                  onChange={(e) => updateSource(src.id, { doi: e.target.value })}
                  className="rounded-md border border-gray-300 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none"
                />
                <div className="col-span-2 flex justify-end sm:col-span-2">
                  <button
                    type="button"
                    onClick={() => removeSource(src.id)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addSource}
          className="mt-2 text-sm font-medium text-indigo-600 hover:text-indigo-800"
        >
          + Add Source
        </button>
      </fieldset>

      {/* Golden label — FR-EXPV-07 */}
      <div>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={form.is_golden_label}
            onChange={(e) => setForm((f) => ({ ...f, is_golden_label: e.target.checked }))}
            className="rounded text-indigo-600"
          />
          Mark as golden dataset entry
        </label>
        <p className="mt-0.5 pl-6 text-xs text-gray-400">
          Golden entries are used for fine-tuning and evaluation benchmarks.
        </p>
      </div>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={submitting}
        className="rounded-md bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {submitting ? "Submitting..." : "Submit Annotation"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ExpertAnalysisDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [analysis, setAnalysis] = useState<ExpertAnalysisDetail | null>(null);
  const [annotations, setAnnotations] = useState<AnnotationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Role check — FR-EXPV-01
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const session = data.session;
      if (!session) {
        setIsAuthorized(false);
        return;
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload = session.user as any;
      const role =
        payload?.app_metadata?.role ?? payload?.user_metadata?.role ?? null;
      setIsAuthorized(role === "expert_reviewer" || role === "admin");
    });
  }, []);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [detail, anns] = await Promise.all([
        getExpertAnalysis(id),
        getAnnotations(id),
      ]);
      setAnalysis(detail);
      setAnnotations(anns);
    } catch (err) {
      console.error("Failed to load analysis detail", err);
      setError("Failed to load analysis. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (isAuthorized) {
      fetchData();
    }
  }, [isAuthorized, fetchData]);

  function handleAnnotationSuccess(ann: AnnotationResponse) {
    setAnnotations((prev) => [...prev, ann]);
  }

  if (isAuthorized === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Checking permissions...</p>
      </div>
    );
  }

  if (!isAuthorized) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <h1 className="mb-2 text-2xl font-bold text-gray-900">Access Denied</h1>
          <p className="mb-4 text-sm text-gray-500">
            You do not have permission to view this page.
          </p>
          <Navigate to="/" replace />
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Loading analysis...</p>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="mb-4 text-sm text-red-600">{error ?? "Analysis not found."}</p>
          <Link to="/expert" className="text-sm text-indigo-600 underline">
            Back to portal
          </Link>
        </div>
      </div>
    );
  }

  const confidenceCat = confidenceCategory(analysis.confidence_score);
  const exerciseLabel =
    EXERCISE_TYPE_LABELS[analysis.exercise_type] ?? analysis.exercise_type;
  const variantLabel = analysis.exercise_variant
    ? (EXERCISE_VARIANT_LABELS[analysis.exercise_variant] ?? analysis.exercise_variant)
    : null;

  const repCount =
    analysis.summary_json != null && "rep_count" in analysis.summary_json
      ? (analysis.summary_json.rep_count as number)
      : null;

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        {/* Back link */}
        <div className="mb-6">
          <Link to="/expert" className="text-sm text-indigo-600 hover:underline">
            &larr; Back to Expert Portal
          </Link>
        </div>

        <h1 className="mb-8 text-3xl font-bold text-gray-900">Analysis Review</h1>

        {/* ------------------------------------------------------------------ */}
        {/* Left / top: anonymized metrics                                      */}
        {/* ------------------------------------------------------------------ */}
        <section
          aria-labelledby="metrics-heading"
          className="mb-6 rounded-lg bg-white p-6 shadow-sm"
        >
          <h2 id="metrics-heading" className="mb-4 text-lg font-semibold text-gray-900">
            Analysis Metrics
          </h2>

          {/* Header row */}
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <span className="text-base font-semibold text-gray-800">
              {exerciseLabel}
              {variantLabel ? ` — ${variantLabel}` : ""}
            </span>

            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${CONFIDENCE_BADGE_STYLES[confidenceCat]}`}
            >
              {confidenceCat} Confidence
            </span>

            {analysis.flagged_for_review && (
              <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
                Flagged for Review
              </span>
            )}

            {analysis.is_golden_dataset && (
              <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                Golden Dataset
              </span>
            )}
          </div>

          {/* Rep count */}
          {repCount !== null && (
            <p className="mb-4 text-sm text-gray-600">
              <span className="font-medium">Reps analysed:</span> {repCount}
            </p>
          )}

          {/* Score cards */}
          {/* form_score_safety is displayed as "Movement Quality" — never "safety score" */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
            <ScoreCard label="Overall" score={analysis.form_score_overall} />
            <ScoreCard label="Movement Quality" score={analysis.form_score_safety} />
            <ScoreCard label="Technique" score={analysis.form_score_technique} />
            <ScoreCard label="Path & Balance" score={analysis.form_score_path_balance} />
            <ScoreCard label="Control" score={analysis.form_score_control} />
          </div>

          {/* Movement Quality alert when score < 3.0 */}
          {analysis.form_score_safety != null && analysis.form_score_safety < 3.0 && (
            <div
              role="alert"
              className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
            >
              Movement Quality score is critically low ({analysis.form_score_safety.toFixed(1)}).
              Coaching output should address form corrections urgently.
            </div>
          )}

          {/* Annotated video — skeleton overlay with angle labels */}
          {analysis.annotated_video_url && (
            <div className="mt-4">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
                Annotated Video
              </p>
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <video
                controls
                className="w-full rounded-md"
                src={analysis.annotated_video_url}
                data-testid="expert-annotated-video"
              >
                Your browser does not support the video element.
              </video>
            </div>
          )}

          {/* Eval scores — structured cards for expert reviewers */}
          {analysis.eval_scores && (
            <EvalScoresCard scores={analysis.eval_scores} />
          )}
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Center: coaching output                                             */}
        {/* ------------------------------------------------------------------ */}
        <section
          aria-labelledby="coaching-heading"
          className="mb-6 rounded-lg bg-white p-6 shadow-sm"
        >
          <h2 id="coaching-heading" className="mb-4 text-lg font-semibold text-gray-900">
            Coaching Output
          </h2>
          <CoachingOutput coachingResult={analysis.coaching_result} />
        </section>

        {/* ------------------------------------------------------------------ */}
        {/* Unvalidated Metrics — Session 3 sagittal-view scaffold              */}
        {/* (ADR-SAGITTAL-METRICS-REGISTRY)                                     */}
        {/* ------------------------------------------------------------------ */}
        <UnvalidatedMetricsPanel analysis={analysis} />

        {/* ------------------------------------------------------------------ */}
        {/* Bottom: previous annotations + annotation form                     */}
        {/* ------------------------------------------------------------------ */}
        <section className="rounded-lg bg-white p-6 shadow-sm">
          <PreviousAnnotations annotations={annotations} />

          {annotations.length > 0 && (
            <hr className="my-6 border-gray-200" />
          )}

          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Submit Annotation
          </h2>
          <AnnotationForm analysisId={analysis.id} exerciseType={analysis.exercise_type} onSuccess={handleAnnotationSuccess} />
        </section>
      </div>
    </div>
  );
}
