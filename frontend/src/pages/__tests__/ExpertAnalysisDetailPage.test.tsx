/**
 * Tests for ExpertAnalysisDetailPage.
 *
 * Requirements:
 * - FR-EXPV-01: Role check (expert_reviewer or admin only)
 * - FR-EXPV-03: Anonymized analysis detail — user_id must never appear
 * - FR-EXPV-04: Annotation submission form
 * - FR-EXPV-07: Golden dataset labelling
 *
 * TDD gates:
 *   1. Renders exercise type from loaded analysis
 *   2. Does NOT display "user_id" anywhere (FR-EXPV-03 anonymization)
 *   3. Shows form scores
 *   4. Renders annotation submit button
 *   5. Shows confidence as categorical label, never decimal (NFR-USAB-03)
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
        data: {
          session: {
            user: {
              id: "test-expert-id",
              user_metadata: { role: "expert_reviewer" },
            },
            access_token: "fake-token",
          },
        },
        error: null,
      }),
    },
  },
}));

vi.mock("@/api/expert", () => ({
  getExpertAnalysis: vi.fn().mockResolvedValue({
    id: "aaaaaaaa-1111-2222-3333-444444444444",
    exercise_type: "squat",
    exercise_variant: "high_bar",
    confidence_score: 0.72,
    form_score_safety: 8.0,
    form_score_technique: 7.0,
    form_score_path_balance: 7.5,
    form_score_control: 6.5,
    form_score_overall: 7.2,
    summary_json: { total_reps: 5 },
    quality_gate_result: null,
    coaching_result: { structured_output_json: { summary: "Good depth." } },
    rep_metrics: [],
    retrieval_context: null,
    eval_scores: null,
    flagged_for_review: false,
    is_golden_dataset: false,
    created_at: "2026-04-20T10:00:00Z",
  }),
  submitAnnotation: vi.fn().mockResolvedValue({ id: "annotation-1" }),
  getAnnotations: vi.fn().mockResolvedValue([]),
}));

// Import after mocks
import ExpertAnalysisDetailPage from "@/pages/ExpertAnalysisDetailPage";
import { supabase } from "@/lib/supabase";
import { getExpertAnalysis, getAnnotations } from "@/api/expert";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ANALYSIS_ID = "aaaaaaaa-1111-2222-3333-444444444444";

function renderDetailPage(analysisId = ANALYSIS_ID) {
  return render(
    <MemoryRouter initialEntries={[`/expert/analyses/${analysisId}`]}>
      <Routes>
        <Route
          path="/expert/analyses/:id"
          element={<ExpertAnalysisDetailPage />}
        />
        <Route path="/expert" element={<div>Expert Portal</div>} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExpertAnalysisDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default: authorized expert_reviewer
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: {
        session: {
          user: {
            id: "test-expert-id",
            user_metadata: { role: "expert_reviewer" },
          },
          access_token: "fake-token",
        },
      },
      error: null,
    } as ReturnType<typeof supabase.auth.getSession> extends Promise<infer R> ? R : never);

    vi.mocked(getExpertAnalysis).mockResolvedValue({
      id: ANALYSIS_ID,
      exercise_type: "squat",
      exercise_variant: "high_bar",
      confidence_score: 0.72,
      form_score_safety: 8.0,
      form_score_technique: 7.0,
      form_score_path_balance: 7.5,
      form_score_control: 6.5,
      form_score_overall: 7.2,
      summary_json: { total_reps: 5 },
      quality_gate_result: null,
      coaching_result: { structured_output_json: { summary: "Good depth." } },
      rep_metrics: [],
      retrieval_context: null,
      eval_scores: null,
      flagged_for_review: false,
      is_golden_dataset: false,
      created_at: "2026-04-20T10:00:00Z",
    });

    vi.mocked(getAnnotations).mockResolvedValue([]);
  });

  it("renders exercise type from loaded analysis", async () => {
    renderDetailPage();

    await waitFor(() => {
      // ExpertAnalysisDetailPage maps "squat" → "Squat" via EXERCISE_TYPE_LABELS
      expect(screen.getByText(/Squat/)).toBeInTheDocument();
    });
  });

  it("does NOT display user_id anywhere (FR-EXPV-03 anonymization)", async () => {
    renderDetailPage();

    await waitFor(() => {
      // Wait for page to fully render (exercise type visible)
      expect(screen.getByText(/Squat/)).toBeInTheDocument();
    });

    // user_id must never appear in the rendered output
    const pageText = document.body.textContent ?? "";
    expect(pageText).not.toContain("user_id");
    expect(pageText).not.toContain("test-expert-id");
  });

  it("shows form scores in the analysis metrics section", async () => {
    renderDetailPage();

    await waitFor(() => {
      // Score labels rendered by ScoreCard components
      expect(screen.getByText("Overall")).toBeInTheDocument();
      // form_score_safety is displayed as "Movement Quality" (never "safety")
      expect(screen.getByText("Movement Quality")).toBeInTheDocument();
      expect(screen.getByText("Technique")).toBeInTheDocument();
    });

    // Verify numeric score values are rendered (e.g. form_score_overall = 7.2)
    expect(screen.getByText("7.2")).toBeInTheDocument();
  });

  it("renders the Submit Annotation button (FR-EXPV-04)", async () => {
    renderDetailPage();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /submit annotation/i }),
      ).toBeInTheDocument();
    });
  });

  it("shows confidence as categorical label, never decimal (NFR-USAB-03)", async () => {
    renderDetailPage();

    await waitFor(() => {
      // confidence_score 0.72 → "Moderate" (0.65–0.79 range)
      expect(screen.getByText(/Moderate Confidence/i)).toBeInTheDocument();
    });

    // Raw decimal "0.72" must not appear
    expect(screen.queryByText("0.72")).not.toBeInTheDocument();
  });
});
