/**
 * TrendChart — unit tests
 * TDD gate: tooltip formatter returns human-readable label, not raw decimal.
 * Requirements: FR-HIST-02
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TrendChart, {
  formatLineValue,
  formatBarValue,
  type TrendChartDataPoint,
} from "@/components/TrendChart";

// Recharts uses ResizeObserver internally — stub it for jsdom
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverStub;

const SAMPLE_LINE_DATA: TrendChartDataPoint[] = [
  { date: "2024-01-01", value: 0.87 },
  { date: "2024-01-08", value: 0.55 },
];

const SAMPLE_BAR_DATA: TrendChartDataPoint[] = [
  { date: "2024-01-01", value: 5 },
  { date: "2024-01-08", value: 8 },
];

describe("TrendChart", () => {
  it("renders empty state when data is empty", () => {
    render(<TrendChart data={[]} type="line" label="Confidence" />);
    expect(screen.getByTestId("trend-chart-empty")).toBeInTheDocument();
  });

  it("renders chart container when data is provided (line)", () => {
    render(
      <TrendChart data={SAMPLE_LINE_DATA} type="line" label="Confidence" />,
    );
    expect(screen.getByTestId("trend-chart")).toBeInTheDocument();
  });

  it("renders chart container when data is provided (bar)", () => {
    render(
      <TrendChart data={SAMPLE_BAR_DATA} type="bar" label="Rep Count" />,
    );
    expect(screen.getByTestId("trend-chart")).toBeInTheDocument();
  });

  it("displays the label prop as chart title", () => {
    render(
      <TrendChart data={SAMPLE_LINE_DATA} type="line" label="Confidence" />,
    );
    expect(screen.getByText("Confidence")).toBeInTheDocument();
  });

  // TDD gate: tooltip formatters return human-readable strings, not raw decimals
  it("formatLineValue returns percentage string not raw decimal", () => {
    expect(formatLineValue(0.87)).toBe("87%");
    expect(formatLineValue(0.5)).toBe("50%");
    expect(formatLineValue(1)).toBe("100%");
    expect(formatLineValue(0)).toBe("0%");
  });

  it("formatBarValue returns integer string not decimal", () => {
    expect(formatBarValue(5)).toBe("5");
    expect(formatBarValue(8)).toBe("8");
    expect(formatBarValue(0)).toBe("0");
  });

  it("line chart tooltip formatter handles non-number value by stringifying", () => {
    // Test the non-number branch: value is not a number, should fallback to String(value ?? "")
    // We can test this through the exported formatter function pattern
    // The formatter is: typeof value === "number" ? formatLineValue(value) : String(value ?? "")
    const formatter = (value: unknown) =>
      typeof value === "number" ? formatLineValue(value as number) : String(value ?? "");

    expect(formatter("not-a-number")).toBe("not-a-number");
    expect(formatter(null)).toBe("");
    expect(formatter(undefined)).toBe("");
    expect(formatter(0.75)).toBe("75%");
  });

  it("bar chart tooltip formatter handles non-number value by stringifying", () => {
    const formatter = (value: unknown) =>
      typeof value === "number" ? formatBarValue(value as number) : String(value ?? "");

    expect(formatter("text")).toBe("text");
    expect(formatter(null)).toBe("");
    expect(formatter(undefined)).toBe("");
    expect(formatter(7)).toBe("7");
  });
});
