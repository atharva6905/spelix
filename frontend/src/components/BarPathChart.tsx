/**
 * BarPathChart
 *
 * Renders the 2D barbell-path trajectory (FR-RESL-05) on the results page,
 * mirroring the bar-path plot that previously lived only in the PDF report.
 *
 * Data source: analysis.summary_json.bar_path — persisted by the worker so the
 * trajectory survives the 7-day artifact purge (issue #206). Bench has no real
 * bar tracker yet (#180), so bar_path is null there — the component degrades to
 * a plain "not available" state rather than rendering an empty axis box.
 *
 * Copy is movement-only: "Bar Path", "Lateral Position", "Vertical Position",
 * "Path Consistency" — never injury / medical framing.
 *
 * Requirements: FR-RESL-05 (issue #206)
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { BarPath } from "@/api/analyses";

export type { BarPath };

export interface BarPathChartProps {
  barPath: BarPath | null | undefined;
  exerciseType: string;
}

interface BarPathPoint {
  x: number;
  y: number;
}

const EMPTY_MESSAGE: Record<string, string> = {
  bench: "Bar path tracking is not available for the bench press yet.",
};

const DEFAULT_EMPTY_MESSAGE =
  "Bar path data is not available for this analysis.";

export default function BarPathChart({
  barPath,
  exerciseType,
}: BarPathChartProps) {
  const centroids = barPath?.centroids ?? [];

  if (centroids.length === 0) {
    return (
      <div
        className="flex h-40 items-center justify-center rounded-md bg-gray-50 px-4 text-center text-sm text-gray-400"
        data-testid="bar-path-empty"
      >
        {EMPTY_MESSAGE[exerciseType] ?? DEFAULT_EMPTY_MESSAGE}
      </div>
    );
  }

  // Image coordinates put the top of the lift at a small y and the bottom at a
  // large y. Reverse the Y axis so the chart reads bottom-up like the lifter.
  const data: BarPathPoint[] = centroids.map(([x, y]) => ({ x, y }));

  const rawConsistency = barPath?.path_consistency;
  const hasConsistency =
    typeof rawConsistency === "number" && Number.isFinite(rawConsistency);
  const consistencyLabel = hasConsistency
    ? `Bar Path · Path Consistency: ${Math.round(rawConsistency * 100)}%`
    : "Bar Path";

  return (
    <div data-testid="bar-path-chart">
      <p className="mb-1 text-xs font-medium text-gray-600">
        {consistencyLabel}
      </p>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, bottom: 24, left: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, 1]}
            tick={{ fontSize: 10 }}
            label={{
              value: "Lateral Position",
              position: "insideBottom",
              offset: -12,
              fontSize: 11,
            }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[0, 1]}
            reversed
            tick={{ fontSize: 10 }}
            label={{
              value: "Vertical Position",
              angle: -90,
              position: "insideLeft",
              fontSize: 11,
            }}
          />
          <Tooltip
            formatter={(value) =>
              typeof value === "number" ? value.toFixed(3) : String(value ?? "")
            }
          />
          <Line
            type="linear"
            dataKey="y"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 2 }}
            isAnimationActive={false}
            name="Bar Path"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
