/**
 * InsightsPanel
 *
 * Displays per-exercise and global insights for the HistoryPage.
 * Shows 7-session rolling average confidence, rep count trend,
 * most common quality gate warning, and personal best confidence.
 *
 * Requirements: FR-HIST-02, FR-HIST-03
 */

import type { ExerciseInsights, GlobalInsights } from "@/api/insights";
import TrendChart, { type TrendChartDataPoint } from "@/components/TrendChart";
import { getConfidenceCategory } from "@/lib/confidence";

/**
 * Build TrendChart data points from a plain array of values.
 * Dates are relative: session N = N days ago from today.
 */
function buildTrendData(values: number[]): TrendChartDataPoint[] {
  const today = new Date();
  return values.map((value, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (values.length - 1 - i));
    return { date: d.toISOString().slice(0, 10), value };
  });
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface InsightsPanelProps {
  exerciseInsights?: ExerciseInsights;
  globalInsights?: GlobalInsights;
  exerciseLabel?: string;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
      {children}
    </h3>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function InsightsPanel({
  exerciseInsights,
  globalInsights,
  exerciseLabel = "Exercise",
}: InsightsPanelProps) {
  const hasExerciseInsights = exerciseInsights !== undefined;
  const hasGlobalInsights = globalInsights !== undefined;

  return (
    <div
      className="space-y-6 rounded-lg bg-white p-6 shadow-sm"
      data-testid="insights-panel"
    >
      <h2 className="text-lg font-semibold text-gray-900">Insights</h2>

      {/* Per-exercise insights */}
      <div data-testid="exercise-insights">
        <SectionHeading>{exerciseLabel} — Last 7 Sessions</SectionHeading>

        {!hasExerciseInsights ? (
          <p className="text-sm text-gray-400" data-testid="exercise-insights-placeholder">
            Insights coming soon — complete more sessions to unlock.
          </p>
        ) : (
          <div className="space-y-4">
            {/* Rolling average confidence trend */}
            {exerciseInsights.rolling_avg_confidence.length > 0 && (
              <TrendChart
                data={buildTrendData(exerciseInsights.rolling_avg_confidence)}
                type="line"
                label="Avg Confidence"
              />
            )}

            {/* Rep count trend */}
            {exerciseInsights.rep_count_trend.length > 0 && (
              <TrendChart
                data={buildTrendData(exerciseInsights.rep_count_trend)}
                type="bar"
                label="Rep Count"
              />
            )}

            <div className="divide-y divide-gray-100">
              {/* Personal best confidence */}
              <StatRow
                label="Personal Best Confidence"
                value={
                  <span
                    className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800"
                    data-testid="personal-best-confidence"
                  >
                    {getConfidenceCategory(
                      exerciseInsights.personal_best_confidence,
                    )}
                  </span>
                }
              />

              {/* Most common warning */}
              <StatRow
                label="Most Common Warning"
                value={
                  exerciseInsights.most_common_warning !== null ? (
                    <span
                      className="text-amber-700"
                      data-testid="exercise-most-common-warning"
                    >
                      {exerciseInsights.most_common_warning}
                    </span>
                  ) : (
                    <span className="text-gray-400">None</span>
                  )
                }
              />
            </div>
          </div>
        )}
      </div>

      {/* Divider */}
      <hr className="border-gray-100" />

      {/* Global insights */}
      <div data-testid="global-insights">
        <SectionHeading>Global — Last 30 Days</SectionHeading>

        {!hasGlobalInsights ? (
          <p className="text-sm text-gray-400" data-testid="global-insights-placeholder">
            Insights coming soon — complete more sessions to unlock.
          </p>
        ) : (
          <div className="divide-y divide-gray-100">
            <StatRow
              label="Most Common Warning"
              value={
                globalInsights.most_common_warning !== null ? (
                  <span
                    className="text-amber-700"
                    data-testid="global-most-common-warning"
                  >
                    {globalInsights.most_common_warning}
                  </span>
                ) : (
                  <span className="text-gray-400">None</span>
                )
              }
            />

            <StatRow
              label="Highest Variance Exercise"
              value={
                globalInsights.highest_variance_exercise !== null ? (
                  <span data-testid="highest-variance-exercise">
                    {globalInsights.highest_variance_exercise}
                  </span>
                ) : (
                  <span className="text-gray-400">—</span>
                )
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
