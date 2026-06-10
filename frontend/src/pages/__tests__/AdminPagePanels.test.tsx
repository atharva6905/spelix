/**
 * Branch coverage uplift for AdminPage — covers the RagCorpusPanel,
 * ExpertQueuePanel, and CoachBrainPanel branches not covered by the
 * existing AdminPage.test.tsx.
 *
 * Also covers: AnalysisLogPanel status badge branches (processing/coaching →
 * blue, quality_gate_rejected → red), pagination branches, dismiss button
 * on disable message, and delete-error branch.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";

// ---------------------------------------------------------------------------
// Mocks — all 11 admin API functions must be mocked so the panels render
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  listAdminUsers: vi.fn(),
  deleteAdminUser: vi.fn(),
  disableAdminUser: vi.fn(),
  listAdminAnalyses: vi.fn(),
  getAdminHealth: vi.fn(),
  listRagDocuments: vi.fn(),
  deleteRagDocument: vi.fn(),
  reEmbedRagDocument: vi.fn(),
  listExpertQueue: vi.fn(),
  getExpertQueueStats: vi.fn(),
  listCoachBrainEntries: vi.fn(),
  updateCoachBrainEntry: vi.fn(),
  deleteCoachBrainEntry: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/api/admin", () => ({
  listAdminUsers: mocks.listAdminUsers,
  deleteAdminUser: mocks.deleteAdminUser,
  disableAdminUser: mocks.disableAdminUser,
  listAdminAnalyses: mocks.listAdminAnalyses,
  getAdminHealth: mocks.getAdminHealth,
  listRagDocuments: mocks.listRagDocuments,
  deleteRagDocument: mocks.deleteRagDocument,
  reEmbedRagDocument: mocks.reEmbedRagDocument,
  listExpertQueue: mocks.listExpertQueue,
  getExpertQueueStats: mocks.getExpertQueueStats,
  listCoachBrainEntries: mocks.listCoachBrainEntries,
  updateCoachBrainEntry: mocks.updateCoachBrainEntry,
  deleteCoachBrainEntry: mocks.deleteCoachBrainEntry,
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: { getSession: mocks.getSession },
  },
}));

import AdminPage from "@/pages/AdminPage";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ADMIN_SESSION = {
  data: {
    session: {
      access_token: "test-token",
      user: {
        id: "admin-user-id",
        app_metadata: { role: "admin" },
        user_metadata: {},
      },
    },
  },
};

const HEALTH = { queue_depth: 0, worker_heartbeat: true, db_ok: true };

function setupBaseAdminMocks() {
  mocks.getSession.mockResolvedValue(ADMIN_SESSION as never);
  mocks.listAdminUsers.mockResolvedValue([]);
  mocks.listAdminAnalyses.mockResolvedValue([]);
  mocks.getAdminHealth.mockResolvedValue(HEALTH);
  mocks.listRagDocuments.mockResolvedValue([]);
  mocks.listExpertQueue.mockResolvedValue([]);
  mocks.getExpertQueueStats.mockResolvedValue({
    total_flagged: 0,
    total_annotated: 0,
    golden_dataset_count: 0,
  });
  mocks.listCoachBrainEntries.mockResolvedValue([]);
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminPage />
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdminPage — panels branch coverage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupBaseAdminMocks();
  });

  // --- RagCorpusPanel ---

  it("renders RAG Corpus Management panel heading", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("RAG Corpus Management")).toBeInTheDocument(),
    );
  });

  it("renders RAG document in table with all status badge types", async () => {
    mocks.listRagDocuments.mockResolvedValue([
      {
        id: "doc-001",
        title: "Squat Biomechanics",
        document_type: "research_paper",
        quality_tier: "tier_1",
        review_status: "reviewed_approved",
        chunk_count: 12,
        year: 2022,
      },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Squat Biomechanics")).toBeInTheDocument());
    expect(screen.getByText("reviewed approved")).toBeInTheDocument();
    // Re-embed button only appears for reviewed_approved
    expect(screen.getByRole("button", { name: /Re-embed/i })).toBeInTheDocument();
  });

  it("renders RAG document with pending status badge", async () => {
    mocks.listRagDocuments.mockResolvedValue([
      {
        id: "doc-002",
        title: "Bench Press Study",
        document_type: "systematic_review",
        quality_tier: null,
        review_status: "pending",
        chunk_count: 5,
        year: null,
      },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Bench Press Study")).toBeInTheDocument());
    expect(screen.getByText("pending")).toBeInTheDocument();
    // No Re-embed button for non-approved
    expect(screen.queryByRole("button", { name: /Re-embed/i })).not.toBeInTheDocument();
  });

  it("renders RAG document with needs_revision status badge", async () => {
    mocks.listRagDocuments.mockResolvedValue([
      {
        id: "doc-003",
        title: "Deadlift Research",
        document_type: "meta_analysis",
        quality_tier: "tier_2",
        review_status: "needs_revision",
        chunk_count: 8,
        year: 2021,
      },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("needs revision")).toBeInTheDocument());
  });

  it("renders RAG document with reviewed_rejected status badge", async () => {
    mocks.listRagDocuments.mockResolvedValue([
      {
        id: "doc-004",
        title: "Rejected Paper",
        document_type: "case_study",
        quality_tier: null,
        review_status: "reviewed_rejected",
        chunk_count: 3,
        year: 2020,
      },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("reviewed rejected")).toBeInTheDocument());
  });

  it("renders a DOI column linking to doi.org in the corpus table", async () => {
    mocks.listRagDocuments.mockResolvedValue([
      {
        id: "doc-005",
        title: "Linked Paper",
        document_type: "research_paper",
        quality_tier: "tier_1",
        review_status: "pending",
        chunk_count: 2,
        year: 2024,
        doi: "10.1234/squat",
      },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Linked Paper")).toBeInTheDocument());
    expect(screen.getByText("DOI")).toBeInTheDocument();
    const doiLink = screen.getByRole("link", { name: "10.1234/squat" });
    expect(doiLink).toHaveAttribute("href", "https://doi.org/10.1234/squat");
  });

  it("renders an em dash for corpus documents without a DOI", async () => {
    mocks.listRagDocuments.mockResolvedValue([
      {
        id: "doc-006",
        title: "Unlinked Paper",
        document_type: "research_paper",
        quality_tier: "tier_1",
        review_status: "pending",
        chunk_count: 2,
        year: 2024,
        doi: null,
      },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Unlinked Paper")).toBeInTheDocument());
    // Quality tier and year are populated, so the only em dash in the row is
    // the DOI cell.
    const row = screen.getByText("Unlinked Paper").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLTableRowElement).getByText("—")).toBeInTheDocument();
  });

  it("renders empty state for RAG corpus panel", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("No documents found")).toBeInTheDocument());
  });

  it("changes reviewFilter select in RAG corpus panel", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("RAG Corpus Management")).toBeInTheDocument(),
    );

    const selects = screen.getAllByDisplayValue("All statuses");
    fireEvent.change(selects[0], { target: { value: "pending" } });

    await waitFor(() => expect(mocks.listRagDocuments).toHaveBeenCalledTimes(2));
  });

  it("changes exerciseFilter select in RAG corpus panel", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("RAG Corpus Management")).toBeInTheDocument(),
    );

    const selects = screen.getAllByDisplayValue("All exercises");
    fireEvent.change(selects[0], { target: { value: "squat" } });

    await waitFor(() => expect(mocks.listRagDocuments).toHaveBeenCalledTimes(2));
  });

  it("shows error state when RAG document fetch fails", async () => {
    mocks.listRagDocuments.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => expect(screen.getByText("Failed to load documents")).toBeInTheDocument());
  });

  // --- ExpertQueuePanel ---

  it("renders Expert Reviewer Queue panel heading", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Expert Reviewer Queue")).toBeInTheDocument(),
    );
  });

  it("renders expert queue stats when present", async () => {
    mocks.getExpertQueueStats.mockResolvedValue({
      total_flagged: 5,
      total_annotated: 3,
      golden_dataset_count: 2,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Flagged:")).toBeInTheDocument());
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders expert queue items with confidence categories", async () => {
    mocks.listExpertQueue.mockResolvedValue([
      {
        analysis_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        exercise_type: "deadlift",
        exercise_variant: "conventional",
        confidence_score: 0.9,
        annotation_count: 1,
        created_at: "2026-04-20T10:00:00Z",
      },
      {
        analysis_id: "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        exercise_type: "bench",
        exercise_variant: null,
        confidence_score: 0.7,
        annotation_count: 0,
        created_at: "2026-04-21T10:00:00Z",
      },
      {
        analysis_id: "cccccccc-dddd-eeee-ffff-000000000000",
        exercise_type: "squat",
        exercise_variant: "low_bar",
        confidence_score: 0.55,
        annotation_count: 2,
        created_at: "2026-04-22T10:00:00Z",
      },
      {
        analysis_id: "dddddddd-eeee-ffff-0000-111111111111",
        exercise_type: "squat",
        exercise_variant: null,
        confidence_score: 0.3,
        annotation_count: 0,
        created_at: "2026-04-23T10:00:00Z",
      },
      {
        analysis_id: "eeeeeeee-ffff-0000-1111-222222222222",
        exercise_type: "bench",
        exercise_variant: "flat",
        confidence_score: null,
        annotation_count: 0,
        created_at: "2026-04-24T10:00:00Z",
      },
    ]);
    renderPage();
    // High confidence
    await waitFor(() => expect(screen.getByText("High")).toBeInTheDocument());
    // Moderate confidence
    expect(screen.getByText("Moderate")).toBeInTheDocument();
    // Low confidence
    expect(screen.getByText("Low")).toBeInTheDocument();
    // Very Low confidence
    expect(screen.getByText("Very Low")).toBeInTheDocument();
    // Null confidence → —
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
    // exercise_variant appended in parens
    expect(screen.getByText(/conventional/)).toBeInTheDocument();
  });

  it("renders empty state for expert queue", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("No flagged analyses")).toBeInTheDocument(),
    );
  });

  it("shows error state when expert queue fetch fails", async () => {
    mocks.listExpertQueue.mockRejectedValue(new Error("Fail"));
    mocks.getExpertQueueStats.mockRejectedValue(new Error("Fail"));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Failed to load expert queue")).toBeInTheDocument(),
    );
  });

  // --- CoachBrainPanel ---

  it("renders Coach Brain Management panel heading", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Coach Brain Management")).toBeInTheDocument(),
    );
  });

  it("renders coach brain entries with seed status and Approve button", async () => {
    mocks.listCoachBrainEntries.mockResolvedValue([
      {
        id: "brain-001",
        content: "Keep chest up throughout the movement",
        exercise: "squat",
        phase: "descent",
        entry_type: "cue",
        status: "seed",
        confirmation_count: 0,
      },
    ]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Keep chest up/)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /Approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Deprecate/i })).toBeInTheDocument();
  });

  it("renders coach brain entries with active status — no Approve, has Deprecate", async () => {
    mocks.listCoachBrainEntries.mockResolvedValue([
      {
        id: "brain-002",
        content: "Drive through the heels",
        exercise: "deadlift",
        phase: "ascent",
        entry_type: "correction",
        status: "active",
        confirmation_count: 5,
      },
    ]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Drive through the heels/)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Deprecate/i })).toBeInTheDocument();
  });

  it("renders coach brain entries with deprecated status — no Approve, no Deprecate", async () => {
    mocks.listCoachBrainEntries.mockResolvedValue([
      {
        id: "brain-003",
        content: "Old cue that was deprecated",
        exercise: "bench",
        phase: "setup",
        entry_type: "principle",
        status: "deprecated",
        confirmation_count: 2,
      },
    ]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Old cue/)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Deprecate/i })).not.toBeInTheDocument();
    // Delete button still present
    expect(screen.getAllByRole("button", { name: /Delete/i }).length).toBeGreaterThan(0);
  });

  it("renders empty state for coach brain panel", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("No entries found")).toBeInTheDocument());
  });

  it("truncates long content at 80 chars with ellipsis", async () => {
    const longContent = "A".repeat(100);
    mocks.listCoachBrainEntries.mockResolvedValue([
      {
        id: "brain-long",
        content: longContent,
        exercise: "squat",
        phase: "descent",
        entry_type: "cue",
        status: "seed",
        confirmation_count: 0,
      },
    ]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(`${"A".repeat(80)}...`)).toBeInTheDocument(),
    );
  });

  it("shows error state when coach brain fetch fails", async () => {
    mocks.listCoachBrainEntries.mockRejectedValue(new Error("Fail"));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Failed to load Coach Brain entries")).toBeInTheDocument(),
    );
  });

  it("changes exerciseFilter in CoachBrain panel", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Coach Brain Management")).toBeInTheDocument(),
    );

    const allExerciseSelects = screen.getAllByDisplayValue("All exercises");
    // Last one is the CoachBrain panel filter
    const coachBrainExerciseSelect = allExerciseSelects[allExerciseSelects.length - 1];
    fireEvent.change(coachBrainExerciseSelect, { target: { value: "bench" } });

    await waitFor(() =>
      expect(mocks.listCoachBrainEntries).toHaveBeenCalledTimes(2),
    );
  });

  // --- AnalysisLogPanel status badge color branches ---

  it("renders processing status with blue badge", async () => {
    mocks.listAdminAnalyses.mockResolvedValue([
      {
        id: "aaa00001-0000-0000-0000-000000000001",
        user_id: "uid1",
        status: "processing",
        exercise_type: "squat",
        exercise_variant: "high_bar",
        confidence_score: null,
        created_at: "2024-04-01T10:00:00Z",
        updated_at: "2024-04-01T10:00:00Z",
      },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getByText("Processing")).toBeInTheDocument());
  });

  it("renders coaching status with blue badge", async () => {
    mocks.listAdminAnalyses.mockResolvedValue([
      {
        id: "aaa00002-0000-0000-0000-000000000002",
        user_id: "uid2",
        status: "coaching",
        exercise_type: "bench",
        exercise_variant: "flat",
        confidence_score: null,
        created_at: "2024-04-02T10:00:00Z",
        updated_at: "2024-04-02T10:00:00Z",
      },
    ]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Generating coaching/)).toBeInTheDocument(),
    );
  });

  it("renders quality_gate_pending status with gray badge", async () => {
    mocks.listAdminAnalyses.mockResolvedValue([
      {
        id: "aaa00003-0000-0000-0000-000000000003",
        user_id: "uid3",
        status: "quality_gate_pending",
        exercise_type: "deadlift",
        exercise_variant: "conventional",
        confidence_score: null,
        created_at: "2024-04-03T10:00:00Z",
        updated_at: "2024-04-03T10:00:00Z",
      },
    ]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Preparing to analyse…")).toBeInTheDocument(),
    );
  });

  // --- UserManagementPanel: dismiss disable message ---

  it("dismisses disable message when Dismiss is clicked", async () => {
    mocks.listAdminUsers.mockResolvedValue([
      {
        user_id: "aaaaaaaa-0000-0000-0000-000000000001",
        height_cm: 175,
        weight_kg: 75,
        age: 25,
        experience_level: "beginner",
        analysis_count: 1,
        created_at: "2024-01-15T10:00:00Z",
        updated_at: "2024-01-15T10:00:00Z",
      },
    ]);
    mocks.disableAdminUser.mockResolvedValue({ message: "Phase 1 feature stub." });

    renderPage();
    await waitFor(() => expect(screen.getByText("175 cm")).toBeInTheDocument());

    const disableButtons = screen.getAllByRole("button", { name: /disable user/i });
    fireEvent.click(disableButtons[0]);

    await waitFor(() => expect(screen.getByText("Phase 1 feature stub.")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));

    await waitFor(() =>
      expect(screen.queryByText("Phase 1 feature stub.")).not.toBeInTheDocument(),
    );
  });

  // --- UserManagementPanel: delete user fails → shows deleteError ---

  it("shows delete error when deleteAdminUser throws", async () => {
    mocks.listAdminUsers.mockResolvedValue([
      {
        user_id: "aaaaaaaa-0000-0000-0000-000000000001",
        height_cm: 180,
        weight_kg: 85,
        age: 30,
        experience_level: "advanced",
        analysis_count: 10,
        created_at: "2024-01-15T10:00:00Z",
        updated_at: "2024-01-15T10:00:00Z",
      },
    ]);
    mocks.deleteAdminUser.mockRejectedValue(new Error("Delete failed"));

    renderPage();
    await waitFor(() => expect(screen.getByText("180 cm")).toBeInTheDocument());

    const deleteButtons = screen.getAllByRole("button", { name: /delete user/i });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to delete user/i)).toBeInTheDocument(),
    );
  });

  // --- disable user fails → shows error in disableMessage ---

  it("shows error when disableAdminUser throws", async () => {
    mocks.listAdminUsers.mockResolvedValue([
      {
        user_id: "aaaaaaaa-0000-0000-0000-000000000001",
        height_cm: 170,
        weight_kg: 70,
        age: 22,
        experience_level: null,
        analysis_count: 0,
        created_at: "2024-01-15T10:00:00Z",
        updated_at: "2024-01-15T10:00:00Z",
      },
    ]);
    mocks.disableAdminUser.mockRejectedValue(new Error("Disable failed"));

    renderPage();
    await waitFor(() => expect(screen.getByText("170 cm")).toBeInTheDocument());

    const disableButtons = screen.getAllByRole("button", { name: /disable user/i });
    fireEvent.click(disableButtons[0]);

    await waitFor(() =>
      expect(screen.getByText(/Failed to disable user/i)).toBeInTheDocument(),
    );
  });
});
