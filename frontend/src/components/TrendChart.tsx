/**
 * TrendChart
 *
 * Recharts-based chart for displaying confidence trends (line) and
 * rep count trends (bar). Used in InsightsPanel.
 *
 * Requirements: FR-HIST-02
 */

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export interface TrendChartDataPoint {
  date: string;
  value: number;
}

export interface TrendChartProps {
  data: TrendChartDataPoint[];
  type: "line" | "bar";
  label: string;
}

export default function TrendChart({ data, type, label }: TrendChartProps) {
  if (data.length === 0) {
    return (
      <div
        className="flex h-32 items-center justify-center rounded-md bg-gray-50 text-sm text-gray-400"
        data-testid="trend-chart-empty"
      >
        No data yet
      </div>
    );
  }

  const commonProps = {
    data,
    margin: { top: 4, right: 8, bottom: 4, left: -16 },
  };

  return (
    <div data-testid="trend-chart">
      <p className="mb-1 text-xs font-medium text-gray-500">{label}</p>
      <ResponsiveContainer width="100%" height={120}>
        {type === "line" ? (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              tickFormatter={(v: string) => {
                const d = new Date(v);
                return `${d.getMonth() + 1}/${d.getDate()}`;
              }}
            />
            <YAxis tick={{ fontSize: 10 }} domain={[0, 1]} />
            <Tooltip
              formatter={(value) => [typeof value === "number" ? value.toFixed(2) : String(value ?? ""), label]}
              labelFormatter={(l) => new Date(String(l)).toLocaleDateString()}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        ) : (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              tickFormatter={(v: string) => {
                const d = new Date(v);
                return `${d.getMonth() + 1}/${d.getDate()}`;
              }}
            />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
            <Tooltip
              formatter={(value) => [String(value ?? ""), label]}
              labelFormatter={(l) => new Date(String(l)).toLocaleDateString()}
            />
            <Bar dataKey="value" fill="#10b981" radius={[2, 2, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
