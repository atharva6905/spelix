/**
 * UnvalidatedMetricsPanel — Session 3 (L2-SAGITTAL-INFRA-04).
 *
 * Shows the 16 sagittal-view metrics that Sessions 4-7 will populate.
 * Expert reviewers only — mounted on ExpertAnalysisDetailPage below the
 * Coaching Output section.
 *
 * Language constraints (SaMD compliance — reviewed by spelix-security-reviewer):
 * - Header: "Unvalidated Metrics (computed, pending expert validation)"
 * - Subhead: "These metrics are computed but NOT YET scored. Validate against
 *   the video before flagging thresholds."
 * - NEVER uses "injury risk", "injury prevention", or "safety score".
 *
 * After Session 3, ALL 16 entries render "Not yet computed". Sessions 4-7
 * flip `computed_yet=true` per metric in the registry; this component then
 * renders the value + unit + Flag button.
 */
import { useCallback, useEffect, useState } from "react";

import {
  createThresholdFlag,
  getSagittalMetricsRegistry,
  type ExpertAnalysisDetail,
  type SagittalMetricRegistryEntry,
  type ThresholdFlagCreate,
  type ThresholdRow,
} from "@/api/expert";
import ThresholdFlagModal from "@/components/ThresholdFlagModal";
import { getConfidenceCategory } from "@/lib/confidence";

interface Props {
  analysis: ExpertAnalysisDetail;
}

interface ApplicableEntry extends SagittalMetricRegistryEntry {
  perRep: Array<{
    repIndex: number;
    value: number | string | null;
    confidenceScore: number | null;
    interpolationFraction: number | null;
  }>;
}

function _extractValue(
  rep: Record<string, unknown>,
  key: string,
): number | string | null {
  // Expert API nests rep_metrics values under `metrics_json` (matches the
  // JSONB column shape). Session-3 read the value off the top-level rep
  // object, which worked only while all 16 entries were stuck at
  // computed_yet=false. Session 4 flipped four flags and exposed the
  // shape mismatch — fall back to top-level for backwards-compatibility
  // with any test fixture that still uses the flat shape.
  const nested =
    rep.metrics_json && typeof rep.metrics_json === "object"
      ? (rep.metrics_json as Record<string, unknown>)[key]
      : undefined;
  const raw = nested !== undefined ? nested : rep[key];
  if (raw === undefined || raw === null) return null;
  if (typeof raw === "number" || typeof raw === "string") return raw;
  // Object / array values (e.g. bar_to_hip_distance dict) -- JSON-encode
  // for compact display until Sessions 6+ surface a structured view.
  try {
    return JSON.stringify(raw);
  } catch {
    return null;
  }
}

function _formatValue(value: number | string | null, unit: string): string {
  if (value === null) return "—";
  if (typeof value === "number") {
    const trimmed = unit.trim();
    return trimmed ? `${value.toFixed(1)} ${trimmed}` : value.toFixed(1);
  }
  return String(value);
}

function _confidenceChip(score: number | null) {
  if (score === null) return null;
  const cat = getConfidenceCategory(score);
  const tone =
    cat === "High"
      ? "bg-green-100 text-green-700"
      : cat === "Moderate"
        ? "bg-yellow-100 text-yellow-700"
        : cat === "Low"
          ? "bg-orange-100 text-orange-700"
          : "bg-red-100 text-red-700";
  return (
    <span
      className={`inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium ${tone}`}
    >
      {cat}
    </span>
  );
}

export default function UnvalidatedMetricsPanel({ analysis }: Props) {
  const [entries, setEntries] = useState<SagittalMetricRegistryEntry[] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [flagRow, setFlagRow] = useState<ThresholdRow | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSagittalMetricsRegistry()
      .then((resp) => {
        if (!cancelled) setEntries(resp.entries);
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to load sagittal metrics registry", err);
          setError("Unable to load sagittal metrics registry.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const applicable: ApplicableEntry[] = (entries ?? [])
    .filter((e) =>
      e.exercise_applicability.includes(
        analysis.exercise_type as "squat" | "bench" | "deadlift",
      ),
    )
    .map((e) => ({
      ...e,
      perRep: analysis.rep_metrics.map((rep, i) => ({
        repIndex:
          typeof rep.rep_index === "number" ? (rep.rep_index as number) : i + 1,
        value: _extractValue(rep, e.key_name),
        confidenceScore:
          typeof rep.confidence_score === "number"
            ? (rep.confidence_score as number)
            : null,
        interpolationFraction:
          typeof rep.interpolation_fraction === "number"
            ? (rep.interpolation_fraction as number)
            : null,
      })),
    }));

  const handleFlagSubmit = useCallback(
    async (payload: ThresholdFlagCreate) => {
      await createThresholdFlag(payload);
    },
    [],
  );

  if (error) {
    return (
      <section
        aria-labelledby="unvalidated-metrics-heading"
        className="mb-6 rounded-lg bg-white p-6 shadow-sm"
      >
        <h2
          id="unvalidated-metrics-heading"
          className="mb-2 text-lg font-semibold text-gray-900"
        >
          Unvalidated Metrics (computed, pending expert validation)
        </h2>
        <p className="text-sm text-red-600">{error}</p>
      </section>
    );
  }

  if (entries === null) {
    return (
      <section
        aria-labelledby="unvalidated-metrics-heading"
        className="mb-6 rounded-lg bg-white p-6 shadow-sm"
      >
        <h2
          id="unvalidated-metrics-heading"
          className="mb-2 text-lg font-semibold text-gray-900"
        >
          Unvalidated Metrics (computed, pending expert validation)
        </h2>
        <p className="text-sm text-gray-400">Loading sagittal metrics…</p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="unvalidated-metrics-heading"
      className="mb-6 rounded-lg bg-white p-6 shadow-sm"
    >
      <h2
        id="unvalidated-metrics-heading"
        className="mb-1 text-lg font-semibold text-gray-900"
      >
        Unvalidated Metrics (computed, pending expert validation)
      </h2>
      <p className="mb-4 text-sm text-gray-600">
        These metrics are computed but NOT YET scored. Validate against the
        video before flagging thresholds.
      </p>

      {applicable.length === 0 ? (
        <p className="text-sm text-gray-400">
          No sagittal metrics apply to this exercise.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2 pr-3">Metric</th>
                {analysis.rep_metrics.map((rep, i) => {
                  const score =
                    typeof rep.confidence_score === "number"
                      ? (rep.confidence_score as number)
                      : null;
                  return (
                    <th key={i} className="py-2 pr-3">
                      <div className="flex flex-col gap-0.5">
                        <span>Rep {i + 1}</span>
                        {_confidenceChip(score)}
                      </div>
                    </th>
                  );
                })}
                <th className="py-2 pr-3">Description</th>
              </tr>
            </thead>
            <tbody>
              {applicable.map((entry) => (
                <tr key={entry.key_name} className="border-b align-top">
                  <td className="py-2 pr-3 font-medium text-gray-700">
                    {entry.display_label}
                  </td>
                  {entry.perRep.map((rep, i) => (
                    <td key={i} className="py-2 pr-3 text-gray-700">
                      {!entry.computed_yet ? (
                        <span
                          className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500"
                          aria-label="Not yet computed"
                        >
                          Not yet computed
                        </span>
                      ) : rep.value !== null ? (
                        <div className="flex items-center gap-2">
                          <span>{_formatValue(rep.value, entry.unit)}</span>
                          <button
                            type="button"
                            onClick={() =>
                              setFlagRow({
                                section: "unvalidated_metrics",
                                key: entry.key_name,
                                value:
                                  typeof rep.value === "number"
                                    ? rep.value
                                    : 0,
                                unit: entry.unit,
                                provenance_citation: null,
                                last_modified_by: null,
                              })
                            }
                            className="rounded border border-indigo-200 px-2 py-0.5 text-xs text-indigo-600 hover:bg-indigo-50"
                          >
                            Flag
                          </button>
                        </div>
                      ) : (
                        <div
                          className="flex flex-col gap-0.5"
                          title="Landmark dropout this rep — R2 reconstructed the affected frames; metrics that depend on the occluded joint can't be computed."
                        >
                          <span className="inline-flex w-fit items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                            Cannot compute
                          </span>
                          {rep.confidenceScore !== null && (
                            <span className="text-[11px] text-gray-500">
                              {getConfidenceCategory(rep.confidenceScore)} confidence
                            </span>
                          )}
                          {rep.interpolationFraction !== null &&
                            rep.interpolationFraction > 0 && (
                              <span className="text-[11px] text-gray-500">
                                {Math.round(rep.interpolationFraction * 100)}% interpolated
                              </span>
                            )}
                        </div>
                      )}
                    </td>
                  ))}
                  <td className="py-2 pr-3 text-xs text-gray-500">
                    {entry.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ThresholdFlagModal
        row={flagRow}
        onClose={() => setFlagRow(null)}
        onSubmit={handleFlagSubmit}
      />
    </section>
  );
}
