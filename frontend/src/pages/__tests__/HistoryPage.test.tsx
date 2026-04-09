/**
 * Tests for HistoryPage, InsightsPanel, and TrendChart.
 *
 * TDD gate:
 *   1. test_list_renders — mock GET /analyses → list items appear
 *   2. test_insights_panel_renders — InsightsPanel with mock data renders stats
 *   3. test_charts_render_with_data — TrendChart with mock data renders SVG
 *
 * Requirements: FR-HIST-01, FR-HIST-02, FR-HIST-03, FR-HIST-06
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";

// ---------------------------------------------------------------------------
// Mocks — must be declared before imports that use them
// ---------------------------------------------------------------------------

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

vi.mock("@/api/analyses", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/analyses")>();
  return {
    ...actual,
    listAnalyses: vi.fn(),
  };
});

vi.mock("@/api/insights", () => ({
  getExerciseInsights: vi.fn(),
  getGlobalInsights: vi.fn(),
}));

// Import after mocks
import HistoryPage from "@/pages/HistoryPage";
import InsightsPanel from "@/components/InsightsPanel";
import TrendChart from "@/components/TrendChart";
import { listAnalyses } from "@/api/analyses";
import { getExerciseInsights, getGlobalInsights } from "@/api/insights";
import type { ExerciseInsights, GlobalInsights } from "@/api/insights";
import type { AnalysisListItem } from "@/api/analyses";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeListItem(overrides: Partial<AnalysisListItem> = {}): AnalysisListItem {
  return {
    id: "analysis-001",
    status: "completed",
    exercise_type: "squat",
    exercise_variant: "high_bar",
    confidence_score: 0.85,
    created_at: "2026-04-08T10:00:00Z",
    ...overrides,
  };
}

const mockExerciseInsights: ExerciseInsights = {
  rolling_avg_confidence: [0.72, 0.78, 0.81, 0.79, 0.83, 0.85, 0.87],
  rep_count_trend: [4, 5, 5, 6, 5, 6, 7],
  most_common_warning: "Low body visibility",
  personal_best_confidence: 0.87,
};

const mockGlobalInsights: GlobalInsights = {
  most_common_warning: "Partial body out of frame",
  highest_variance_exercise: "Squat — High Bar",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderHistoryPage() {
  return render(
    <MemoryRouter initialEntries={["/history"]}>
      <Routes>
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/analysis/:id" element={<div>Analysis Page</div>} />
        <Route path="/upload" element={<div>Upload Page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HistoryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: insights endpoints not available (404)
    vi.mocked(getExerciseInsights).mockRejectedValue(
      Object.assign(new Error("Not found"), { status: 404 }),
    );
    vi.mocked(getGlobalInsights).mockRejectedValue(
      Object.assign(new Error("Not found"), { status: 404 }),
    );
  });

  // TDD gate 1: list items appear
  it("test_list_renders — renders analysis list items", async () => {
    vi.mocked(listAnalyses).mockResolvedValue([
      makeListItem({ id: "a1", exercise_type: "squat", exercise_variant: "high_bar" }),
      makeListItem({ id: "a2", exercise_type: "bench", exercise_variant: "flat", status: "processing", confidence_score: null }),
      makeListItem({ id: "a3", exercise_type: "deadlift", exercise_variant: "conventional", confidence_score: 0.62 }),
    ]);

    renderHistoryPage();

    await waitFor(() => {
      expect(screen.getByTestId("analysis-list")).toBeInTheDocument();
    });

    const rows = screen.getAllByTestId("analysis-row");
    expect(rows).toHaveLength(3);

    // Exercise labels — use getAllByText since InsightsPanel heading also contains exercise name
    expect(screen.getAllByText(/Squat/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Bench Press/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Deadlift/).length).toBeGreaterThanOrEqual(1);

    // Status badges
    const statusBadges = screen.getAllByTestId("status-badge");
    const statusTexts = statusBadges.map((b) => b.textContent);
    expect(statusTexts).toContain("Completed");
    expect(statusTexts).toContain("Processing");

    // Confidence labels (only for items with scores)
    const confidenceLabels = screen.getAllByTestId("confidence-label");
    expect(confidenceLabels.length).toBeGreaterThanOrEqual(1);
    // High confidence (0.85) → "High"
    expect(confidenceLabels.some((el) => el.textContent === "High")).toBe(true);
  });

  it("renders empty state when no analyses", async () => {
    vi.mocked(listAnalyses).mockResolvedValue([]);

    renderHistoryPage();

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText(/No analyses yet/i)).toBeInTheDocument();
  });

  it("renders loading state initially", () => {
    // listAnalyses never resolves
    vi.mocked(listAnalyses).mockReturnValue(new Promise(() => {}));

    renderHistoryPage();

    expect(screen.getByRole("status", { name: /loading history/i })).toBeInTheDocument();
  });

  it("renders error when fetch fails", async () => {
    vi.mocked(listAnalyses).mockRejectedValue(new Error("Network error"));

    renderHistoryPage();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("shows insights placeholder when insights endpoints return 404", async () => {
    vi.mocked(listAnalyses).mockResolvedValue([makeListItem()]);

    renderHistoryPage();

    await waitFor(() => {
      expect(screen.getByTestId("analysis-list")).toBeInTheDocument();
    });

    // InsightsPanel should be present with placeholders
    await waitFor(() => {
      expect(screen.getByTestId("insights-panel")).toBeInTheDocument();
    });
    expect(screen.getByTestId("exercise-insights-placeholder")).toBeInTheDocument();
    expect(screen.getByTestId("global-insights-placeholder")).toBeInTheDocument();
  });

  it("shows insights when endpoints succeed", async () => {
    vi.mocked(listAnalyses).mockResolvedValue([makeListItem()]);
    vi.mocked(getExerciseInsights).mockResolvedValue(mockExerciseInsights);
    vi.mocked(getGlobalInsights).mockResolvedValue(mockGlobalInsights);

    renderHistoryPage();

    await waitFor(() => {
      expect(screen.getByTestId("exercise-most-common-warning")).toBeInTheDocument();
    });
    expect(screen.getByText("Low body visibility")).toBeInTheDocument();
    expect(screen.getByTestId("global-most-common-warning")).toBeInTheDocument();
    expect(screen.getByText("Partial body out of frame")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// InsightsPanel tests
// ---------------------------------------------------------------------------

describe("InsightsPanel — test_insights_panel_renders", () => {
  it("renders per-exercise stats with mock data", () => {
    render(
      <MemoryRouter>
        <InsightsPanel
          exerciseInsights={mockExerciseInsights}
          globalInsights={mockGlobalInsights}
          exerciseLabel="Squat — High Bar"
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("insights-panel")).toBeInTheDocument();

    // Personal best confidence displayed as category
    expect(screen.getByTestId("personal-best-confidence")).toHaveTextContent("High");

    // Most common warning
    expect(screen.getByTestId("exercise-most-common-warning")).toHaveTextContent(
      "Low body visibility",
    );

    // Global stats
    expect(screen.getByTestId("global-most-common-warning")).toHaveTextContent(
      "Partial body out of frame",
    );
    expect(screen.getByTestId("highest-variance-exercise")).toHaveTextContent(
      "Squat — High Bar",
    );
  });

  it("shows placeholder text when exerciseInsights is undefined", () => {
    render(
      <MemoryRouter>
        <InsightsPanel globalInsights={mockGlobalInsights} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("exercise-insights-placeholder")).toBeInTheDocument();
    expect(screen.getByText(/Insights coming soon/i)).toBeInTheDocument();
  });

  it("shows placeholder text when globalInsights is undefined", () => {
    render(
      <MemoryRouter>
        <InsightsPanel exerciseInsights={mockExerciseInsights} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("global-insights-placeholder")).toBeInTheDocument();
  });

  it("shows null warnings as None", () => {
    render(
      <MemoryRouter>
        <InsightsPanel
          exerciseInsights={{ ...mockExerciseInsights, most_common_warning: null }}
          globalInsights={{ most_common_warning: null, highest_variance_exercise: null }}
        />
      </MemoryRouter>,
    );

    // "None" for exercise and global most common warning
    const noneElements = screen.getAllByText("None");
    expect(noneElements.length).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// TrendChart tests
// ---------------------------------------------------------------------------

describe("TrendChart — test_charts_render_with_data", () => {
  const trendData = [
    { date: "2026-04-01", value: 0.72 },
    { date: "2026-04-02", value: 0.78 },
    { date: "2026-04-03", value: 0.81 },
    { date: "2026-04-04", value: 0.85 },
    { date: "2026-04-05", value: 0.87 },
  ];

  it("renders SVG for line chart with data", () => {
    // Mock getBoundingClientRect so ResponsiveContainer reports non-zero size
    // and Recharts renders the SVG in jsdom.
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({
      width: 400,
      height: 120,
      top: 0,
      left: 0,
      bottom: 120,
      right: 400,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    const { container } = render(
      <TrendChart data={trendData} type="line" label="Avg Confidence" />,
    );

    expect(screen.getByTestId("trend-chart")).toBeInTheDocument();
    expect(screen.getByText("Avg Confidence")).toBeInTheDocument();
    // ResponsiveContainer renders the recharts wrapper div even in jsdom
    expect(container.querySelector(".recharts-responsive-container")).toBeInTheDocument();

    vi.restoreAllMocks();
  });

  it("renders SVG for bar chart with data", () => {
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({
      width: 400,
      height: 120,
      top: 0,
      left: 0,
      bottom: 120,
      right: 400,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    const barData = [
      { date: "2026-04-01", value: 4 },
      { date: "2026-04-02", value: 5 },
      { date: "2026-04-03", value: 6 },
    ];

    const { container } = render(
      <TrendChart data={barData} type="bar" label="Rep Count" />,
    );

    expect(screen.getByTestId("trend-chart")).toBeInTheDocument();
    expect(screen.getByText("Rep Count")).toBeInTheDocument();
    expect(container.querySelector(".recharts-responsive-container")).toBeInTheDocument();

    vi.restoreAllMocks();
  });

  it("renders empty state when data is empty", () => {
    render(<TrendChart data={[]} type="line" label="Avg Confidence" />);

    expect(screen.getByTestId("trend-chart-empty")).toBeInTheDocument();
    expect(screen.getByText("No data yet")).toBeInTheDocument();
  });
});
