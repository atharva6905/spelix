/**
 * Tests for ResultsPage
 *
 * TDD gate: all 8 specified behaviours must pass.
 * Requirements: FR-RESL-01a–05, FR-RESL-08, FR-RESL-10–11,
 *               FR-SCOR-09–10, NFR-USAB-03
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

// Mock ChatPanel to avoid useChat API setup in page-level tests
vi.mock("@/components/ChatPanel", () => ({
  default: ({ analysisId }: { analysisId: string }) => (
    <div data-testid="chat-panel" data-analysis-id={analysisId} />
  ),
}));

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({
    nodes,
  }: {
    nodes: Array<{ id: string; data: { label: string } }>;
  }) => (
    <div data-testid="reactflow-canvas">
      {nodes.map((n) => (
        <div key={n.id}>{n.data.label}</div>
      ))}
    </div>
  ),
  Background: () => null,
  Controls: () => null,
}));
vi.mock("@xyflow/react/dist/style.css", () => ({}));

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
      agent_trace_json: null,
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

  // TDD gate 6 / B-058: Per-level confidence guidance (FR-RESL-08)
  it("shows 'Results are reliable.' guidance for High confidence", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.9 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("confidence-badge")).toHaveTextContent("High");
    expect(screen.getByTestId("confidence-guidance")).toHaveTextContent(
      "Results are reliable.",
    );
  });

  it("shows Moderate guidance for confidence score 0.70", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.70 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("confidence-badge")).toHaveTextContent("Moderate");
    expect(screen.getByTestId("confidence-guidance")).toHaveTextContent(
      "Partial occlusion detected",
    );
  });

  it("shows Low guidance for confidence score 0.55", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.55 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("confidence-badge")).toHaveTextContent("Low");
    expect(screen.getByTestId("confidence-guidance")).toHaveTextContent(
      "Results may be unreliable",
    );
  });

  it("shows Very Low guidance for confidence score 0.2", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ confidence_score: 0.2 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("confidence-badge")).toHaveTextContent("Very Low");
    expect(screen.getByTestId("confidence-guidance")).toHaveTextContent(
      "Unable to score reliably",
    );
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

  // B-047: Three-tier disclaimer (FR-RESL-11)
  it("renders three-tier disclaimer with all three required paragraphs", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    const disclaimer = screen.getByTestId("three-tier-disclaimer");
    expect(disclaimer).toBeInTheDocument();
    expect(disclaimer).toHaveTextContent(
      "This analysis is for fitness and performance purposes only and is not medical advice.",
    );
    expect(disclaimer).toHaveTextContent(
      "Generated by automated systems with inherent limitations.",
    );
    expect(disclaimer).toHaveTextContent(
      "Physical exercise carries inherent risk.",
    );
  });

  // B-048: Rep count and timestamp in summary card (FR-RESL-01a)
  it("renders rep count and formatted timestamp in header card", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        rep_metrics: [
          { rep_index: 0, start_frame: 0, end_frame: 60, confidence_score: 0.9, metrics_json: null },
          { rep_index: 1, start_frame: 61, end_frame: 120, confidence_score: 0.8, metrics_json: null },
          { rep_index: 2, start_frame: 121, end_frame: 180, confidence_score: 0.85, metrics_json: null },
        ],
        created_at: "2026-04-08T10:00:00Z",
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    // Rep count
    expect(screen.getByText(/3 reps/)).toBeInTheDocument();
    // Formatted date — year must appear
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it("shows 0 reps when rep_metrics is empty", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ rep_metrics: [] }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByText(/0 reps/)).toBeInTheDocument();
  });

  // B-057: Rep metrics table sortable by rep column
  it("clicking Rep column header reverses row order", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        rep_metrics: [
          { rep_index: 0, start_frame: 0, end_frame: 60, confidence_score: 0.9, metrics_json: null },
          { rep_index: 1, start_frame: 61, end_frame: 120, confidence_score: 0.8, metrics_json: null },
        ],
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    const sortBtn = screen.getByRole("button", { name: /rep/i });

    // Default order: ascending (rep_index 0 first → displayed as "1")
    let rows = screen.getAllByRole("row");
    // rows[0] = header, rows[1] = first data row
    expect(rows[1]).toHaveTextContent("1");

    fireEvent.click(sortBtn);

    // After click: descending — rep_index 1 first → displayed as "2"
    rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("2");
  });

  // B-059: Annotated video download link
  it("renders annotated video download link with correct href", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        annotated_video_path: "https://cdn.example.com/annotated.mp4",
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    const downloadLink = screen.getByTestId("annotated-video-download");
    expect(downloadLink).toBeInTheDocument();
    expect(downloadLink).toHaveAttribute(
      "href",
      "https://cdn.example.com/annotated.mp4",
    );
  });

  it("does not render annotated video download link when path is null", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ annotated_video_path: null }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(
      screen.queryByTestId("annotated-video-download"),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Phase 1: Form Score Cards (FR-RESL-01, FR-SCOR-01 through FR-SCOR-08)
// ---------------------------------------------------------------------------

describe("ResultsPage — Phase 1 Form Score Cards", () => {
  beforeEach(() => {
    mockUseAnalysisDetail.mockReset();
  });

  it("renders all four dimension score cards when scores are present", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        form_score_safety: 8.2,
        form_score_technique: 7.0,
        form_score_path_balance: 6.5,
        form_score_control: 5.8,
        form_score_overall: 7.1,
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("form-score-cards")).toBeInTheDocument();
    expect(screen.getByTestId("score-overall")).toBeInTheDocument();
    expect(screen.getByTestId("score-safety")).toBeInTheDocument();
    expect(screen.getByTestId("score-technique")).toBeInTheDocument();
    expect(screen.getByTestId("score-path-balance")).toBeInTheDocument();
    expect(screen.getByTestId("score-control")).toBeInTheDocument();

    // Score values rendered
    expect(screen.getByTestId("score-overall")).toHaveTextContent("7.1");
    expect(screen.getByTestId("score-safety")).toHaveTextContent("8.2");
  });

  it("displays Movement Quality label (not 'Safety Score')", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ form_score_safety: 6.0, form_score_overall: 6.0 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("score-safety")).toHaveTextContent(
      /Movement Quality/i,
    );
    expect(screen.queryByText(/Safety Score/i)).not.toBeInTheDocument();
  });

  it("shows Movement Quality alert when safety score < 3.0", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        form_score_safety: 2.5,
        form_score_overall: 4.0,
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("movement-quality-alert")).toBeInTheDocument();
  });

  it("does not show Movement Quality alert when safety score >= 3.0", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        form_score_safety: 7.5,
        form_score_overall: 7.5,
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.queryByTestId("movement-quality-alert")).not.toBeInTheDocument();
  });

  it("hides the form score section entirely when no scores present (Phase 0 fallback)", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        form_score_safety: null,
        form_score_technique: null,
        form_score_path_balance: null,
        form_score_control: null,
        form_score_overall: null,
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.queryByTestId("form-score-cards")).not.toBeInTheDocument();
  });

  it("renders score descriptor text for overall rating", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ form_score_overall: 9.2 }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    expect(screen.getByTestId("score-overall")).toHaveTextContent(/Elite/i);
  });
});

// ---------------------------------------------------------------------------
// Phase 1: Extended coaching sections (FR-AICP-03)
// ---------------------------------------------------------------------------

describe("ResultsPage — Phase 1 coaching extensions", () => {
  beforeEach(() => {
    mockUseAnalysisDetail.mockReset();
  });

  it("renders safety_warnings when present", () => {
    const analysis = makeAnalysis();
    (
      analysis.coaching_result!.structured_output_json! as unknown as Record<
        string,
        unknown
      >
    ).safety_warnings = ["Significant knee cave detected on rep 3"];

    mockUseAnalysisDetail.mockReturnValue({
      analysis,
      isLoading: false,
      error: null,
    });

    renderResultsPage();
    expect(screen.getByTestId("coaching-safety-warnings")).toBeInTheDocument();
    expect(
      screen.getByText(/Significant knee cave detected on rep 3/i),
    ).toBeInTheDocument();
  });

  it("renders recommended_cues when present", () => {
    const analysis = makeAnalysis();
    (
      analysis.coaching_result!.structured_output_json! as unknown as Record<
        string,
        unknown
      >
    ).recommended_cues = ["Push knees out", "Drive through heels"];

    mockUseAnalysisDetail.mockReturnValue({
      analysis,
      isLoading: false,
      error: null,
    });

    renderResultsPage();
    expect(screen.getByTestId("coaching-recommended-cues")).toBeInTheDocument();
    expect(screen.getByText(/Push knees out/i)).toBeInTheDocument();
  });

  it("renders citations with authors, year, title, and DOI", () => {
    const analysis = makeAnalysis();
    (
      analysis.coaching_result!.structured_output_json! as unknown as Record<
        string,
        unknown
      >
    ).citations = [
      {
        title: "Squat biomechanics review",
        authors: ["Schoenfeld, B.", "Grgic, J."],
        year: 2020,
        doi: "10.1234/example",
      },
    ];

    mockUseAnalysisDetail.mockReturnValue({
      analysis,
      isLoading: false,
      error: null,
    });

    renderResultsPage();
    expect(screen.getByTestId("coaching-citations")).toBeInTheDocument();
    expect(screen.getByText(/Schoenfeld/i)).toBeInTheDocument();
    expect(screen.getByText(/Squat biomechanics review/i)).toBeInTheDocument();
    expect(screen.getByText(/10\.1234\/example/i)).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Phase 2: Citation tooltips (P2-021, FR-RESL-06)
  // -------------------------------------------------------------------------

  it("renders inline citation markers in summary text", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        coaching_result: {
          structured_output_json: {
            summary: "Good form overall [1].",
            strengths: ["Strong bracing [1]"],
            issues: [
              {
                rep_number: 1,
                joint: "Knee",
                description: "Knee cave on ascent [1]",
                severity: "High",
                citation_indices: [1],
              },
            ],
            correction_plan: ["Cue knees out [1]"],
            disclaimer: "Educational purposes only.",
            citations: [
              {
                title: "Squat Mechanics",
                authors: ["Smith J"],
                year: 2022,
                doi: "10.1234/squat",
              },
            ],
          },
          agent_trace_json: null,
          created_at: "2026-04-08T10:05:00Z",
        },
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();

    // Citation markers should appear in multiple sections
    const markers = screen.getAllByTestId("citation-marker-1");
    expect(markers.length).toBeGreaterThanOrEqual(1);
    // Each marker is a button
    expect(markers[0].tagName).toBe("BUTTON");
  });

  it("renders citation markers in correction plan", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        coaching_result: {
          structured_output_json: {
            summary: "Some summary.",
            strengths: [],
            issues: [],
            correction_plan: ["Focus on ankle mobility [1]"],
            disclaimer: "Educational purposes only.",
            citations: [
              {
                title: "Ankle Mobility Study",
                authors: ["Jones A"],
                year: 2021,
                doi: null,
              },
            ],
          },
          agent_trace_json: null,
          created_at: "2026-04-08T10:05:00Z",
        },
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();
    expect(screen.getByTestId("citation-marker-1")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Phase 2: Degraded mode banner (P2-019, FR-AICP-15)
  // -------------------------------------------------------------------------

  it("renders degraded mode banner when degraded_mode is true", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({
        coaching_result: {
          structured_output_json: {
            summary: "Form analysis without research context.",
            strengths: [],
            issues: [],
            correction_plan: [],
            disclaimer: "Educational purposes only.",
            degraded_mode: true,
          },
          agent_trace_json: null,
          created_at: "2026-04-08T10:05:00Z",
        },
      }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();
    expect(screen.getByTestId("degraded-mode-banner")).toBeInTheDocument();
    expect(
      screen.getByText(/without research backing/i),
    ).toBeInTheDocument();
  });

  it("does not render degraded mode banner when degraded_mode is false", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();
    expect(
      screen.queryByTestId("degraded-mode-banner"),
    ).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Phase 2: Follow-up chat panel (P2-022, FR-RESL-09)
  // -------------------------------------------------------------------------

  it("renders chat panel when coaching result is present", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis(),
      isLoading: false,
      error: null,
    });

    renderResultsPage();
    expect(screen.getByTestId("chat-panel")).toBeInTheDocument();
  });

  it("does not render chat panel when coaching result is null", () => {
    mockUseAnalysisDetail.mockReturnValue({
      analysis: makeAnalysis({ coaching_result: null }),
      isLoading: false,
      error: null,
    });

    renderResultsPage();
    expect(screen.queryByTestId("chat-panel")).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Phase 3: agent_trace_json type round-trip (P3-007, FR-RESL-07)
  // -------------------------------------------------------------------------

  it("exposes agent_trace_json on the analysis detail shape (types round-trip)", () => {
    const analysis = makeAnalysis({
      coaching_result: {
        structured_output_json: {
          summary: "ok",
          strengths: [],
          issues: [],
          correction_plan: [],
          disclaimer: "",
        },
        created_at: "2026-04-17T10:00:00Z",
        agent_trace_json: {
          mode: "deterministic",
          nodes_executed: [
            {
              node: "get_rep_metrics",
              started_at: "2026-04-17T10:00:00Z",
              duration_ms: 12.3,
              output_keys: ["rep_metrics"],
              error: null,
            },
          ],
          eval_scores: { faithfulness: 0.92 },
          cove_iterations: [],
          converged: true,
          retrieval_source: "coach_brain_primary",
          degraded_mode: false,
        },
      },
    });
    expect(analysis.coaching_result?.agent_trace_json?.mode).toBe("deterministic");
    expect(analysis.coaching_result?.agent_trace_json?.nodes_executed?.[0]?.node).toBe(
      "get_rep_metrics",
    );
  });

  describe("How AI Reasoned sidebar integration (P3-007)", () => {
    it("does not render the button when agent_trace_json is null", () => {
      mockUseAnalysisDetail.mockReturnValue({
        analysis: makeAnalysis(),
        isLoading: false,
        error: null,
      });
      renderResultsPage();
      expect(
        screen.queryByRole("button", { name: /how ai reasoned/i }),
      ).not.toBeInTheDocument();
    });

    it("does not render the button when agent_trace_json has empty nodes_executed", () => {
      const analysis = makeAnalysis();
      analysis.coaching_result = {
        ...analysis.coaching_result!,
        agent_trace_json: {
          mode: "deterministic",
          nodes_executed: [],
          eval_scores: {},
          cove_iterations: [],
          converged: false,
          retrieval_source: null,
          degraded_mode: false,
        },
      };
      mockUseAnalysisDetail.mockReturnValue({
        analysis,
        isLoading: false,
        error: null,
      });
      renderResultsPage();
      expect(
        screen.queryByRole("button", { name: /how ai reasoned/i }),
      ).not.toBeInTheDocument();
    });

    it("renders the button when agent_trace_json has at least one executed node", () => {
      const analysis = makeAnalysis();
      analysis.coaching_result = {
        ...analysis.coaching_result!,
        agent_trace_json: {
          mode: "deterministic",
          nodes_executed: [
            {
              node: "get_rep_metrics",
              started_at: "2026-04-17T10:00:00Z",
              duration_ms: 10,
              output_keys: ["rep_metrics"],
              error: null,
            },
          ],
          eval_scores: {},
          cove_iterations: [],
          converged: true,
          retrieval_source: "coach_brain_primary",
          degraded_mode: false,
        },
      };
      mockUseAnalysisDetail.mockReturnValue({
        analysis,
        isLoading: false,
        error: null,
      });
      renderResultsPage();
      expect(
        screen.getByRole("button", { name: /how ai reasoned/i }),
      ).toBeInTheDocument();
    });

    it("clicking the button opens the sidebar; clicking close hides it", () => {
      const analysis = makeAnalysis();
      analysis.coaching_result = {
        ...analysis.coaching_result!,
        agent_trace_json: {
          mode: "deterministic",
          nodes_executed: [
            {
              node: "get_rep_metrics",
              started_at: "2026-04-17T10:00:00Z",
              duration_ms: 10,
              output_keys: ["rep_metrics"],
              error: null,
            },
          ],
          eval_scores: {},
          cove_iterations: [],
          converged: true,
          retrieval_source: "coach_brain_primary",
          degraded_mode: false,
        },
      };
      mockUseAnalysisDetail.mockReturnValue({
        analysis,
        isLoading: false,
        error: null,
      });
      renderResultsPage();

      expect(
        screen.queryByTestId("agent-reasoning-sidebar"),
      ).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /how ai reasoned/i }));
      expect(screen.getByTestId("agent-reasoning-sidebar")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /^close$/i }));
      expect(
        screen.queryByTestId("agent-reasoning-sidebar"),
      ).not.toBeInTheDocument();
    });
  });
});
