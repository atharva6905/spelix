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

interface Props {
  analysis: ExpertAnalysisDetail;
}

interface ApplicableEntry extends SagittalMetricRegistryEntry {
  perRep: Array<{ repIndex: number; value: number | string | null }>;
}

function _extractValue(
  rep: Record<string, unknown>,
  key: string,
): number | string | null {
  const raw = rep[key];
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
                {analysis.rep_metrics.map((_, i) => (
                  <th key={i} className="py-2 pr-3">
                    Rep {i + 1}
                  </th>
                ))}
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
                      {entry.computed_yet && rep.value !== null ? (
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
                        <span
                          className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500"
                          aria-label="Not yet computed"
                        >
                          Not yet computed
                        </span>
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
