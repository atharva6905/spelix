/**
 * Tests for ResultsPage
 *
 * TDD gate: all 8 specified behaviours must pass.
 * Requirements: FR-RESL-01a–05, FR-RESL-08, FR-RESL-10–11,
 *               FR-SCOR-09–10, NFR-USAB-03
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import ResultsPage from "@/pages/ResultsPage";
import type { AnalysisDetail } from "@/api/analyses";

// ---------------------------------------------------------------------------
// Mock useAnalysisDetail so we can control data in each test
// ---------------------------------------------------------------------------

const mockUseAnalysisDetail = vi.fn();

vi.mock("@/hooks/useAnalysisDetail", () => ({
  useAnalysisDetail: (...args: unknown[]) => mockUseAnalysisDetail(...args),
}));

// ---------------------------------------------------------------------------
// Fixture factories
// ---------------------------------------------------------------------------

function makeAnalysis(overrides: Partial<AnalysisDetail> = {}): AnalysisDetail {
  return {
    id: "analysis-abc-123",
    status: "completed",
    exercise_type: "squat",
    exercise_variant: "high_bar",
    confidence_score: 0.85,
    video_path: "storage/videos/original.mp4",
    annotated_video_path: "https://cdn.example.com/annotated.mp4",
    plot_path: "https://cdn.example.com/plot.png",
    pdf_path: "https://cdn.example.com/report.pdf",
    tags: null,
    quality_gate_result: null,
    summary_json: null,
    created_at: "2026-04-08T10:00:00Z",
    updated_at: "2026-04-08T10:05:00Z",
    coaching_result: {
      structured_output_json: {
        summary: "Good overall form with minor hip hinge issues.",
        strengths: ["Solid bar path", "Good bracing"],
        issues: [
          {
            rep_number: 2,
            joint: "Hip",
            description: "Slight forward lean at the bottom.",
            severity: "Medium",
          },
          {
            rep_number: 3,
            joint: "Knee",
            description: "Knee cave on ascent.",
            severity: "High",
          },
          {
            rep_number: 1,
            joint: "Ankle",
            description: "Minor heel rise.",
            severity: "Low",
          },
        ],
        correction_plan: ["Focus on ankle mobility", "Use a heel wedge"],
        disclaimer:
          "This feedback is for educational purposes only and is not a substitute for in-person coaching or medical advice.",
      },
      created_at: "2026-04-08T10:05:00Z",
    },
    rep_metrics: [
      {
        rep_index: 0,
        start_frame: 0,
        end_frame: 60,
        confidence_score: 0.9,
        metrics_json: null,
      },
      {
        rep_index: 1,
        start_frame: 61,
        end_frame: 120,
        confidence_score: 0.75,
        metrics_json: null,
      },
    ],
    ...overrides,
  };
}

function renderResultsPage(id = "analysis-abc-123") {
  return render(
    <MemoryRouter initialEntries={[`/results/${id}`]}>
      <Routes>
        <Route path="/results/:id" element={<ResultsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ResultsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // TDD gate 7: Loading state renders
  it("renders loading state when isLoading is true", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: null,
      isLoading: true,
      error: null,
    });

    renderResultsPage();

    expect(
      screen.getByRole("status", { name: /loading analysis results/i }),
    ).toBeInTheDocument();
  });

  // TDD gate 8: Error state renders
  it("renders error message when fetch fails", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: null,
      isLoading: false,
      error: "Failed to load analysis",
    });

    renderResultsPage();

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Failed to load analysis")).toBeInTheDocument();
  });

  // TDD gate 1: Renders video player when annotated_video_path is present
  it("renders video player when annotated_video_path is present", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    const video = screen.getByTestId("annotated-video");
    expect(video).toBeInTheDocument();
    expect(video).toHaveAttribute(
      "src",
      "https://cdn.example.com/annotated.mp4",
    );
  });

  it("does not render video player when annotated_video_path is null", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ annotated_video_path: null }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.queryByTestId("annotated-video")).not.toBeInTheDocument();
  });

  // TDD gate 2: Renders coaching output sections
  it("renders coaching output sections: summary, strengths, issues, correction plan, disclaimer", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("coaching-summary")).toBeInTheDocument();
    expect(
      screen.getByText("Good overall form with minor hip hinge issues."),
    ).toBeInTheDocument();

    expect(screen.getByTestId("coaching-strengths")).toBeInTheDocument();
    expect(screen.getByText("Solid bar path")).toBeInTheDocument();
    expect(screen.getByText("Good bracing")).toBeInTheDocument();

    expect(screen.getByTestId("coaching-issues")).toBeInTheDocument();

    expect(screen.getByTestId("coaching-correction-plan")).toBeInTheDocument();
    expect(screen.getByText("Focus on ankle mobility")).toBeInTheDocument();

    expect(screen.getByTestId("coaching-disclaimer")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This feedback is for educational purposes only and is not a substitute for in-person coaching or medical advice.",
      ),
    ).toBeInTheDocument();
  });

  // TDD gate 3: Issues sorted by severity (High first)
  it("renders issues sorted High → Medium → Low", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    const issueItems = screen
      .getByTestId("coaching-issues")
      .querySelectorAll("li");

    // First issue must be severity High
    expect(issueItems[0]).toHaveTextContent("High");
    // Second issue must be severity Medium
    expect(issueItems[1]).toHaveTextContent("Medium");
    // Third issue must be severity Low
    expect(issueItems[2]).toHaveTextContent("Low");
  });

  // TDD gate 4: Rep metrics table renders
  it("renders rep metrics table with correct row count", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    // Header row + 2 data rows = 3 rows total
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(3);

    // Rep 1 and Rep 2 visible (rep_index + 1)
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  // TDD gate 5: Confidence badge shows categorical label, not decimal
  it("shows categorical confidence label — never the raw decimal", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.85 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    const badge = screen.getByTestId("confidence-badge");
    expect(badge).toHaveTextContent("High");
    // Raw decimal must not appear anywhere
    expect(screen.queryByText("0.85")).not.toBeInTheDocument();
    expect(screen.queryByText("85%")).not.toBeInTheDocument();
  });

  it("shows Moderate for confidence score 0.7", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.7 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("confidence-badge")).toHaveTextContent(
      "Moderate",
    );
    expect(screen.queryByText("0.7")).not.toBeInTheDocument();
  });

  // TDD gate 6: Low confidence shows caution banner (NFR-USAB-03)
  it("shows caution banner for Low confidence score", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.45 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("confidence-badge")).toHaveTextContent("Low");
    expect(screen.getByTestId("low-confidence-banner")).toBeInTheDocument();
  });

  it("shows caution banner for Very Low confidence score", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.2 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("confidence-badge")).toHaveTextContent(
      "Very Low",
    );
    expect(screen.getByTestId("low-confidence-banner")).toBeInTheDocument();
  });

  it("does not show caution banner for High confidence", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.9 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.queryByTestId("low-confidence-banner")).not.toBeInTheDocument();
  });

  // Exercise header
  it("renders exercise type and variant in header", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        exercise_type: "deadlift",
        exercise_variant: "conventional",
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByText("Deadlift")).toBeInTheDocument();
    expect(screen.getByText(/Conventional/)).toBeInTheDocument();
  });

  // 7-day artifact banner
  it("always shows the 7-day artifact banner", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByText(/available for 7 days/i)).toBeInTheDocument();
  });

  // Download links
  it("renders CSV download link", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("csv-download")).toBeInTheDocument();
  });

  it("renders PDF download link when pdf_path is present", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        pdf_path: "https://cdn.example.com/report.pdf",
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("pdf-download")).toBeInTheDocument();
  });

  it("does not render PDF download link when pdf_path is null", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ pdf_path: null }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.queryByTestId("pdf-download")).not.toBeInTheDocument();
  });

  // Angle plot
  it("renders angle plot image when plot_path is present", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("angle-plot")).toHaveAttribute(
      "src",
      "https://cdn.example.com/plot.png",
    );
  });

  // No coaching result
  it("does not render coaching section when coaching_result is null", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ coaching_result: null }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.queryByTestId("coaching-summary")).not.toBeInTheDocument();
  });
});
