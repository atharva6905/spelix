/**
 * Session 4 — AutoFlowMetricsChips: shows depth_classification and
 * ecc_con_ratio as small chip badges on the regular user's ResultsPage.
 * Reads directly from analysis.rep_metrics[].metrics_json — no new
 * backend persistence required (values ride the existing JSONB column).
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import ResultsPage from "@/pages/ResultsPage";
import type { AnalysisDetail } from "@/api/analyses";


const mockUseAnalysisDetail = vi.fn();

vi.mock("@/hooks/useAnalysisDetail", () => ({
  useAnalysisDetail: (...args: unknown[]) => mockUseAnalysisDetail(...args),
}));

vi.mock("@/components/ChatPanel", () => ({
  default: () => <div data-testid="chat-panel" />,
}));

vi.mock("@xyflow/react", () => ({
  ReactFlow: () => <div data-testid="reactflow-canvas" />,
  Background: () => null,
  Controls: () => null,
}));
vi.mock("@xyflow/react/dist/style.css", () => ({}));

// ResultsPage imports supabase directly for the admin check (issue #192) —
// mock the client so the module doesn't construct against missing env in CI.
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: null },
      }),
    },
    channel: vi.fn().mockReturnValue({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
    }),
    removeChannel: vi.fn(),
  },
}));


function makeAnalysis(overrides: Partial<AnalysisDetail> = {}): AnalysisDetail {
  return {
    id: "auto-flow-test",
    status: "completed",
    exercise_type: "squat",
    exercise_variant: "standard",
    confidence_score: 0.85,
    form_score_safety: 8.0,
    form_score_technique: 6.5,
    form_score_path_balance: 7.0,
    form_score_control: 7.5,
    form_score_overall: 7.4,
    detection_result: null,
    video_path: null,
    annotated_video_path: null,
    plot_path: null,
    pdf_path: null,
    tags: null,
    quality_gate_result: null,
    summary_json: null,
    created_at: "2026-05-22T12:00:00Z",
    updated_at: "2026-05-22T12:00:00Z",
    coaching_result: null,
    rep_metrics: [
      {
        rep_index: 0,
        start_frame: 0,
        end_frame: 30,
        confidence_score: 0.9,
        metrics_json: {
          depth_classification: "above_parallel",
          ecc_con_ratio: 0.7,
          depth_angle: 95.0,
        },
      },
      {
        rep_index: 1,
        start_frame: 31,
        end_frame: 60,
        confidence_score: 0.9,
        metrics_json: {
          depth_classification: "at_parallel",
          ecc_con_ratio: 1.4,
          depth_angle: 90.0,
        },
      },
    ],
    ...overrides,
  };
}

function renderResultsPage(id = "auto-flow-test") {
  return render(
    <MemoryRouter initialEntries={[`/results/${id}`]}>
      <Routes>
        <Route path="/results/:id" element={<ResultsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ResultsPage AutoFlowMetricsChips (Session 4)", () => {
  it("renders depth_classification chip with modal label across reps", async () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });
    renderResultsPage();
    const chip = await screen.findByTestId("auto-flow-depth-chip");
    expect(chip).toBeInTheDocument();
    expect(chip.textContent).toMatch(/Depth: (above|at|below) parallel/i);
  });

  it("renders ecc_con_ratio chip with mean across reps to one decimal", async () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });
    renderResultsPage();
    const chip = await screen.findByTestId("auto-flow-ecc-con-chip");
    expect(chip).toBeInTheDocument();
    // Mean of 0.7 and 1.4 → 1.05 → displayed as "1.1" (toFixed(1)).
    expect(chip.textContent).toMatch(/Ecc\/Con: 1\.\d/);
  });

  it("does not render chips when keys are absent (analyses scored before Session 4)", async () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        rep_metrics: [
          {
            rep_index: 0,
            start_frame: 0,
            end_frame: 30,
            confidence_score: 0.9,
            metrics_json: { depth_angle: 95.0 },
          },
        ],
      }),
      isLoading: false,
      error: null,
    });
    renderResultsPage();
    // FormScoreCards is always rendered when overall is non-null; use it as
    // the "page mounted" sentinel.
    await screen.findByTestId("form-score-cards");
    expect(screen.queryByTestId("auto-flow-depth-chip")).not.toBeInTheDocument();
    expect(screen.queryByTestId("auto-flow-ecc-con-chip")).not.toBeInTheDocument();
  });
});
