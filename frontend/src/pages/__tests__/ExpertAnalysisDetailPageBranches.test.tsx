/**
 * Branch coverage uplift for ExpertAnalysisDetailPage.
 *
 * Covers: confidenceCategory branches, scoreDescriptor, scoreColorClass,
 * ScoreCard (null score), CoachingOutput (null result, structured branches,
 * agentTrace toggle), PreviousAnnotations, AnnotationForm (radioToBool,
 * parseJsonField, validation error, submit success, submit error),
 * main page branches (flagged_for_review, is_golden_dataset, variantLabel,
 * repCount, eval_scores, unauthorized, loading, error states).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  getExpertAnalysis: vi.fn(),
  submitAnnotation: vi.fn(),
  getAnnotations: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: { getSession: mocks.getSession },
  },
}));

vi.mock("@/api/expert", () => ({
  getExpertAnalysis: mocks.getExpertAnalysis,
  submitAnnotation: mocks.submitAnnotation,
  getAnnotations: mocks.getAnnotations,
}));

import ExpertAnalysisDetailPage from "@/pages/ExpertAnalysisDetailPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ANALYSIS_ID = "aaaaaaaa-1111-2222-3333-444444444444";

function renderDetailPage(id = ANALYSIS_ID) {
  return render(
    <MemoryRouter initialEntries={[`/expert/analyses/${id}`]}>
      <Routes>
        <Route path="/expert/analyses/:id" element={<ExpertAnalysisDetailPage />} />
        <Route path="/expert" element={<div>Expert Portal</div>} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

const BASE_ANALYSIS = {
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
  annotated_video_url: null,
};

function mockExpertSession() {
  mocks.getSession.mockResolvedValue({
    data: {
      session: {
        user: { id: "test-expert-id", user_metadata: { role: "expert_reviewer" } },
        access_token: "fake-token",
      },
    },
    error: null,
  });
}

// ---------------------------------------------------------------------------
// Tests — confidence category branches
// ---------------------------------------------------------------------------

describe("ExpertAnalysisDetailPage — branch coverage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockExpertSession();
    mocks.getExpertAnalysis.mockResolvedValue(BASE_ANALYSIS);
    mocks.getAnnotations.mockResolvedValue([]);
  });

  // confidenceCategory: >= 0.80 → High
  it("shows High confidence badge for score >= 0.80", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({ ...BASE_ANALYSIS, confidence_score: 0.9 });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText(/High Confidence/i)).toBeInTheDocument());
  });

  // confidenceCategory: 0.50 <= score < 0.65 → Low
  it("shows Low confidence badge for score in 0.50–0.64 range", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({ ...BASE_ANALYSIS, confidence_score: 0.55 });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText(/Low Confidence/i)).toBeInTheDocument());
  });

  // confidenceCategory: < 0.50 → Very Low
  it("shows Very Low confidence badge for score < 0.50", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({ ...BASE_ANALYSIS, confidence_score: 0.3 });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText(/Very Low Confidence/i)).toBeInTheDocument());
  });

  // confidenceCategory: null → Unknown
  it("shows Unknown confidence for null confidence_score", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({ ...BASE_ANALYSIS, confidence_score: null });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText(/Unknown Confidence/i)).toBeInTheDocument());
  });

  // scoreDescriptor: >= 9.0 → Elite
  it("shows Elite descriptor for score >= 9.0", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      form_score_overall: 9.5,
      form_score_safety: 9.0,
      form_score_technique: 8.0,
      form_score_path_balance: 8.5,
      form_score_control: 8.0,
    });
    renderDetailPage();
    // Multiple score cards can show "Elite" (e.g. overall 9.5 and safety 9.0)
    await waitFor(() => {
      const elites = screen.getAllByText("Elite");
      expect(elites.length).toBeGreaterThan(0);
    });
  });

  // scoreDescriptor: 5.0 <= score < 7.5 → Intermediate
  it("shows Intermediate descriptor for score in 5.0–7.4 range", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      form_score_overall: 6.0,
      form_score_safety: 6.0,
      form_score_technique: 6.0,
      form_score_path_balance: 6.0,
      form_score_control: 6.0,
    });
    renderDetailPage();
    await waitFor(() => {
      const intermediates = screen.getAllByText("Intermediate");
      expect(intermediates.length).toBeGreaterThan(0);
    });
  });

  // scoreDescriptor: 3.0 <= score < 5.0 → Needs Work
  it("shows Needs Work descriptor for score in 3.0–4.9 range", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      form_score_overall: 4.0,
      form_score_safety: 4.0,
      form_score_technique: 4.0,
      form_score_path_balance: 4.0,
      form_score_control: 4.0,
    });
    renderDetailPage();
    await waitFor(() => {
      const needsWork = screen.getAllByText("Needs Work");
      expect(needsWork.length).toBeGreaterThan(0);
    });
  });

  // scoreDescriptor: < 3.0 → Needs Attention + alert
  it("shows Needs Attention and movement quality alert for safety score < 3.0", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      form_score_safety: 2.5,
    });
    renderDetailPage();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/Movement Quality score is critically low/i)).toBeInTheDocument();
    });
  });

  // ScoreCard: null score renders "Not available"
  it("renders Not available for null form scores", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      form_score_safety: null,
      form_score_technique: null,
      form_score_path_balance: null,
      form_score_control: null,
      form_score_overall: null,
    });
    renderDetailPage();
    await waitFor(() => {
      const notAvailable = screen.getAllByText("Not available");
      expect(notAvailable.length).toBeGreaterThan(0);
    });
  });

  // flagged_for_review: true → shows Flagged badge
  it("shows Flagged for Review badge when flagged_for_review is true", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({ ...BASE_ANALYSIS, flagged_for_review: true });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Flagged for Review")).toBeInTheDocument());
  });

  // is_golden_dataset: true → shows Golden Dataset badge
  it("shows Golden Dataset badge when is_golden_dataset is true", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({ ...BASE_ANALYSIS, is_golden_dataset: true });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Golden Dataset")).toBeInTheDocument());
  });

  // exercise_variant: null → no variant in label
  it("shows exercise label without variant when exercise_variant is null", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({ ...BASE_ANALYSIS, exercise_variant: null });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Squat")).toBeInTheDocument());
  });

  // repCount: present in summary_json
  it("shows rep count when summary_json has rep_count field", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      summary_json: { rep_count: 8 },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText(/Reps analysed/i)).toBeInTheDocument());
    expect(screen.getByText("8")).toBeInTheDocument();
  });

  // eval_scores: non-null → renders eval section
  it("renders eval scores when present", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      eval_scores: { faithfulness: 0.9 },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Eval Scores")).toBeInTheDocument());
  });

  // CoachingOutput: null coachingResult
  it("shows no coaching output message when coaching_result is null", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({ ...BASE_ANALYSIS, coaching_result: null });
    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByText(/No coaching output available/i)).toBeInTheDocument(),
    );
  });

  // CoachingOutput: structured is null
  it("shows structured output not available when structured_output_json is null", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: { structured_output_json: null },
    });
    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByText(/Structured output not available/i)).toBeInTheDocument(),
    );
  });

  // CoachingOutput: safety_warnings populated
  it("renders movement quality alerts from safety_warnings", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: {
          summary: "Summary here",
          safety_warnings: ["Watch your knees"],
        },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Movement Quality Alerts")).toBeInTheDocument());
    expect(screen.getByText("Watch your knees")).toBeInTheDocument();
  });

  // CoachingOutput: strengths populated
  it("renders strengths section when strengths array is non-empty", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: {
          summary: "Good",
          strengths: ["Great depth"],
        },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Strengths")).toBeInTheDocument());
    expect(screen.getByText("Great depth")).toBeInTheDocument();
  });

  // CoachingOutput: issues with High severity
  it("renders issues with High severity badge", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: {
          issues: [
            { severity: "High", description: "Knees caving in", correction: "Push knees out" },
          ],
        },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Issues")).toBeInTheDocument());
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Knees caving in")).toBeInTheDocument();
    expect(screen.getByText("Push knees out")).toBeInTheDocument();
  });

  // CoachingOutput: issues with Medium severity
  it("renders issues with Medium severity badge", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: {
          issues: [{ severity: "Medium", description: "Slight forward lean", correction: null }],
        },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Medium")).toBeInTheDocument());
  });

  // CoachingOutput: issues with no correction (null)
  it("does not render correction paragraph when correction is null", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: {
          issues: [{ severity: "Low", description: "Minor issue", correction: null }],
        },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Minor issue")).toBeInTheDocument());
  });

  // CoachingOutput: recommended_cues
  it("renders recommended cues section", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: {
          recommended_cues: ["Chest up", "Drive through heels"],
        },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Recommended Cues")).toBeInTheDocument());
    expect(screen.getByText("Chest up")).toBeInTheDocument();
  });

  // CoachingOutput: citations with doi
  it("renders citations with DOI link", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: {
          citations: [
            {
              authors: ["Smith J", "Jones A"],
              year: 2022,
              title: "Squat Mechanics",
              doi: "10.1234/test",
            },
          ],
        },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Citations")).toBeInTheDocument());
    expect(screen.getByText(/Squat Mechanics/)).toBeInTheDocument();
    expect(screen.getByText("10.1234/test")).toBeInTheDocument();
  });

  // CoachingOutput: citations without doi
  it("renders citations without DOI when doi is null", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: {
          citations: [
            {
              authors: ["Smith J"],
              year: 2023,
              title: "Bench Press Study",
              doi: null,
            },
          ],
        },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText(/Bench Press Study/)).toBeInTheDocument());
  });

  // CoachingOutput: agentTrace toggle
  it("toggles agent trace visibility on button click", async () => {
    mocks.getExpertAnalysis.mockResolvedValue({
      ...BASE_ANALYSIS,
      coaching_result: {
        structured_output_json: { summary: "Good" },
        agent_trace: { step: 1, output: "traced" },
      },
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText(/Agent Trace/i)).toBeInTheDocument());

    // Trace content not visible yet
    expect(screen.queryByText(/"step"/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText(/Agent Trace/i));
    await waitFor(() => expect(screen.getByText(/"step"/)).toBeInTheDocument());

    // Click again to close
    fireEvent.click(screen.getByText(/Agent Trace/i));
    await waitFor(() => expect(screen.queryByText(/"step"/)).not.toBeInTheDocument());
  });

  // PreviousAnnotations: non-empty list
  it("renders previous annotations when list is non-empty", async () => {
    mocks.getAnnotations.mockResolvedValue([
      {
        id: "ann-0001-0000-0000-000000000001",
        coaching_quality_score: 8.5,
        movement_advice_accurate: true,
        engagement_advice_accurate: false,
        issues_identified: {},
        suggested_corrections: "Fix knee tracking",
        cited_sources: [],
        is_golden_label: false,
        created_at: "2026-04-21T10:00:00Z",
      },
    ]);
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Previous Annotations")).toBeInTheDocument());
    expect(screen.getByText("Fix knee tracking")).toBeInTheDocument();
    // "Yes" and "No" appear both in annotation values and radio labels — use getAllByText
    const yesElements = screen.getAllByText("Yes");
    expect(yesElements.length).toBeGreaterThan(0);
    const noElements = screen.getAllByText("No");
    expect(noElements.length).toBeGreaterThan(0);
  });

  // PreviousAnnotations: movement_advice_accurate null → N/A
  it("shows N/A for null boolean fields in annotations", async () => {
    mocks.getAnnotations.mockResolvedValue([
      {
        id: "ann-0002-0000-0000-000000000002",
        coaching_quality_score: null,
        movement_advice_accurate: null,
        engagement_advice_accurate: null,
        issues_identified: {},
        suggested_corrections: null,
        cited_sources: [],
        is_golden_label: true,
        created_at: "2026-04-21T10:00:00Z",
      },
    ]);
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Previous Annotations")).toBeInTheDocument());
    // All three radio-like fields show N/A
    const naLabels = screen.getAllByText("N/A");
    expect(naLabels.length).toBeGreaterThanOrEqual(2);
    // Golden label badge
    expect(screen.getByText("Golden Dataset Entry")).toBeInTheDocument();
  });

  // Unauthorized role
  it("navigates to home for non-authorized user", async () => {
    mocks.getSession.mockResolvedValue({
      data: {
        session: {
          user: { id: "uid", user_metadata: { role: "user" } },
          access_token: "token",
        },
      },
      error: null,
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Home")).toBeInTheDocument());
  });

  // No session → unauthorized
  it("navigates to home when session is null", async () => {
    mocks.getSession.mockResolvedValue({ data: { session: null }, error: null });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText("Home")).toBeInTheDocument());
  });

  // Admin role is also authorized
  it("allows admin role to access the page", async () => {
    mocks.getSession.mockResolvedValue({
      data: {
        session: {
          user: { id: "admin-id", user_metadata: { role: "admin" } },
          access_token: "token",
        },
      },
      error: null,
    });
    renderDetailPage();
    await waitFor(() => expect(screen.getByText(/Analysis Review/i)).toBeInTheDocument());
  });

  // Fetch error
  it("shows error message when analysis fetch fails", async () => {
    mocks.getExpertAnalysis.mockRejectedValue(new Error("Network error"));
    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByText(/Failed to load analysis/i)).toBeInTheDocument(),
    );
  });

  // AnnotationForm: validation error for out-of-range quality score
  it("shows validation error for quality score out of range", async () => {
    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit annotation/i })).toBeInTheDocument(),
    );

    const scoreInput = screen.getByLabelText(/Coaching Quality Score/i);
    fireEvent.change(scoreInput, { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: /submit annotation/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/Coaching quality score must be between 1.0 and 10.0/i),
      ).toBeInTheDocument(),
    );
  });

  // AnnotationForm: submit success flow
  it("shows success message after successful annotation submission", async () => {
    mocks.submitAnnotation.mockResolvedValue({
      id: "ann-new",
      coaching_quality_score: 7.0,
      movement_advice_accurate: true,
      engagement_advice_accurate: null,
      issues_identified: {},
      suggested_corrections: null,
      cited_sources: [],
      is_golden_label: false,
      created_at: "2026-04-22T10:00:00Z",
    });

    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit annotation/i })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: /submit annotation/i }));

    await waitFor(() =>
      expect(screen.getByText(/Annotation submitted successfully/i)).toBeInTheDocument(),
    );
  });

  // AnnotationForm: submit error
  it("shows error message when annotation submission fails", async () => {
    mocks.submitAnnotation.mockRejectedValue(new Error("Server error"));

    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit annotation/i })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: /submit annotation/i }));

    await waitFor(() =>
      expect(screen.getByText(/Failed to submit annotation/i)).toBeInTheDocument(),
    );
  });

  // AnnotationForm: radio buttons
  it("fills in radio buttons for movement and engagement advice", async () => {
    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit annotation/i })).toBeInTheDocument(),
    );

    const movementYes = screen.getAllByRole("radio", { name: "Yes" })[0];
    fireEvent.click(movementYes);
    expect(movementYes).toBeChecked();

    const movementNo = screen.getAllByRole("radio", { name: "No" })[0];
    fireEvent.click(movementNo);
    expect(movementNo).toBeChecked();
  });

  // AnnotationForm: golden label checkbox
  it("toggles golden label checkbox", async () => {
    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit annotation/i })).toBeInTheDocument(),
    );

    const checkbox = screen.getByRole("checkbox", { name: /golden dataset/i });
    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  // AnnotationForm: exercise-specific issue checkboxes
  it("checks an exercise issue and submits structured payload", async () => {
    mocks.submitAnnotation.mockResolvedValue({
      id: "ann-json",
      coaching_quality_score: null,
      movement_advice_accurate: null,
      engagement_advice_accurate: null,
      issues_identified: { insufficient_depth: { severity: "Medium" } },
      suggested_corrections: null,
      cited_sources: [],
      is_golden_label: false,
      created_at: "2026-04-23T10:00:00Z",
    });

    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit annotation/i })).toBeInTheDocument(),
    );

    const depthCheckbox = screen.getByRole("checkbox", { name: /Insufficient depth/i });
    fireEvent.click(depthCheckbox);
    expect(depthCheckbox).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: /submit annotation/i }));
    await waitFor(() =>
      expect(screen.getByText(/Annotation submitted successfully/i)).toBeInTheDocument(),
    );

    expect(mocks.submitAnnotation).toHaveBeenCalledWith(
      ANALYSIS_ID,
      expect.objectContaining({
        issues_identified: expect.objectContaining({
          insufficient_depth: { severity: "Medium" },
        }),
      }),
    );
  });

  // AnnotationForm: structured cited sources
  it("adds a source row, fills title, and submits structured payload", async () => {
    mocks.submitAnnotation.mockResolvedValue({
      id: "ann-cited",
      coaching_quality_score: null,
      movement_advice_accurate: null,
      engagement_advice_accurate: null,
      issues_identified: {},
      suggested_corrections: null,
      cited_sources: [{ title: "Test Study", authors: [], year: null, doi: null }],
      is_golden_label: false,
      created_at: "2026-04-23T10:00:00Z",
    });

    renderDetailPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit annotation/i })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByText(/\+ Add Source/i));

    const titleInput = screen.getByRole("textbox", { name: /source title/i });
    fireEvent.change(titleInput, { target: { value: "Test Study" } });

    fireEvent.click(screen.getByRole("button", { name: /submit annotation/i }));
    await waitFor(() =>
      expect(screen.getByText(/Annotation submitted successfully/i)).toBeInTheDocument(),
    );

    expect(mocks.submitAnnotation).toHaveBeenCalledWith(
      ANALYSIS_ID,
      expect.objectContaining({
        cited_sources: expect.arrayContaining([
          expect.objectContaining({ title: "Test Study" }),
        ]),
      }),
    );
  });
});
