/**
 * BarPathChart — unit tests
 *
 * TDD gate: renders the 2D bar-path trajectory for squat/deadlift data and
 * a graceful "not available" empty state when bar_path is null/absent
 * (bench has no real bar tracker yet, #180).
 *
 * Requirements: FR-RESL-05 (issue #206)
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import BarPathChart, { type BarPath } from "@/components/BarPathChart";

// Recharts uses ResizeObserver internally — stub it for jsdom
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverStub;

const SAMPLE_BAR_PATH: BarPath = {
  centroids: [
    [0.5, 0.2],
    [0.51, 0.55],
    [0.49, 0.9],
  ],
  ap_deviation_px: 0.02,
  path_consistency: 0.97,
};

describe("BarPathChart", () => {
  it("renders the trajectory chart when centroid data is present", () => {
    render(<BarPathChart barPath={SAMPLE_BAR_PATH} exerciseType="squat" />);
    expect(screen.getByTestId("bar-path-chart")).toBeInTheDocument();
  });

  it("renders the trajectory chart for deadlift data (R2c, #206)", () => {
    render(<BarPathChart barPath={SAMPLE_BAR_PATH} exerciseType="deadlift" />);
    expect(screen.getByTestId("bar-path-chart")).toBeInTheDocument();
    expect(screen.queryByTestId("bar-path-empty")).not.toBeInTheDocument();
  });

  it("renders the empty state when barPath is null (bench / no tracker)", () => {
    render(<BarPathChart barPath={null} exerciseType="bench" />);
    expect(screen.getByTestId("bar-path-empty")).toBeInTheDocument();
    // No chart should be rendered
    expect(screen.queryByTestId("bar-path-chart")).not.toBeInTheDocument();
  });

  it("renders the empty state when centroids are empty", () => {
    render(
      <BarPathChart
        barPath={{ centroids: [], path_consistency: 1 }}
        exerciseType="squat"
      />,
    );
    expect(screen.getByTestId("bar-path-empty")).toBeInTheDocument();
  });

  it("renders the empty state when barPath is undefined", () => {
    render(<BarPathChart barPath={undefined} exerciseType="deadlift" />);
    expect(screen.getByTestId("bar-path-empty")).toBeInTheDocument();
  });

  it("uses plain movement language, never medical framing", () => {
    const { container } = render(
      <BarPathChart barPath={SAMPLE_BAR_PATH} exerciseType="squat" />,
    );
    const text = container.textContent ?? "";
    expect(text.toLowerCase()).not.toContain("injury");
    expect(text).toContain("Bar Path");
  });
});
