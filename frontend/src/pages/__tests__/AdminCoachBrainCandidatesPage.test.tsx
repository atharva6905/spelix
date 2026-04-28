import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import AdminCoachBrainCandidatesPage from "@/pages/AdminCoachBrainCandidatesPage";
import type { CoachBrainCandidate } from "@/api/admin";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: {
          session: {
            access_token: "t",
            user: { app_metadata: { role: "admin" } },
          },
        },
      }),
    },
  },
}));

const apiMock = vi.hoisted(() => ({
  listCoachBrainCandidates: vi.fn(),
  getCoachBrainCandidateStats: vi.fn(),
  approveCoachBrainCandidate: vi.fn(),
  rejectCoachBrainCandidate: vi.fn(),
  getCoachBrainCandidateSimilar: vi.fn().mockResolvedValue({ items: [] }),
}));

vi.mock("@/api/admin", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/admin")>();
  return { ...actual, ...apiMock };
});

const candidate: CoachBrainCandidate = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  exercise: "bench",
  phase: "descent",
  entry_type: "cue",
  content: "Tuck elbows at 45 degrees.",
  trigger_tags: ["bench", "elbow"],
  source_analysis_ids: ["22222222-2222-2222-2222-222222222222"],
  confidence_score: null,
  eval_scores: { faithfulness: 0.82 },
  cove_verified: false,
  cove_explanation: "evaluation_failed",
  lifecycle_decision: "ADD",
  nearest_entry_id: null,
  nearest_cosine_sim: null,
  nearest_entry_confirmation_count: null,
  contradiction_flag: false,
  requires_technical_review: false,
  review_status: "pending",
  created_at: "2026-04-17T10:02:31Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  apiMock.listCoachBrainCandidates.mockReset();
  apiMock.getCoachBrainCandidateStats.mockReset();
  apiMock.approveCoachBrainCandidate.mockReset();
  apiMock.rejectCoachBrainCandidate.mockReset();
  apiMock.getCoachBrainCandidateSimilar.mockReset();
  apiMock.getCoachBrainCandidateSimilar.mockResolvedValue({ items: [] });
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminCoachBrainCandidatesPage />
    </MemoryRouter>,
  );
}

describe("AdminCoachBrainCandidatesPage - loading + list", () => {
  it("shows loading then first candidate", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });

    renderPage();

    expect(screen.getByText(/loading/i)).toBeTruthy();

    await waitFor(() =>
      expect(screen.getByText(/tuck elbows at 45 degrees/i)).toBeTruthy(),
    );
    expect(screen.getByText(/0\.82/)).toBeTruthy();
    expect(screen.getByText(/CoVe verification failed/i)).toBeTruthy();
    expect(screen.getByText(/1 pending/i)).toBeTruthy();
  });

  it("renders empty state when no candidates", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 0 });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/no candidates to review/i)).toBeTruthy(),
    );
  });

  it("surfaces fetch error", async () => {
    apiMock.listCoachBrainCandidates.mockRejectedValue(new Error("boom"));
    apiMock.getCoachBrainCandidateStats.mockRejectedValue(new Error("boom"));

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/failed to load candidates/i)).toBeTruthy(),
    );
  });

  it("renders similar entries panel with cosine when entries returned", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });
    apiMock.getCoachBrainCandidateSimilar.mockResolvedValue({
      items: [
        {
          id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
          content: "brace the lats before unracking",
          exercise: "bench",
          phase: "setup",
          entry_type: "cue",
          cosine_sim: 0.74,
        },
      ],
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/brace the lats before unracking/i)).toBeTruthy(),
    );
    expect(screen.getByText(/0\.740/)).toBeTruthy();
  });

  it("renders source analysis links", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });

    renderPage();

    await waitFor(() => {
      const link = screen.getByRole("link", { name: /22222222/i }) as HTMLAnchorElement;
      expect(link.href).toContain("/analysis/22222222-2222-2222-2222-222222222222");
    });
  });

  it("shows compensation banner when requires_technical_review is true", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([
      { ...candidate, entry_type: "compensation", requires_technical_review: true },
    ]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/biomechanics reviewer required/i)).toBeTruthy(),
    );
  });
});

describe("AdminCoachBrainCandidatesPage - approve", () => {
  it("approves and advances on Approve click", async () => {
    apiMock.listCoachBrainCandidates
      .mockResolvedValueOnce([candidate])
      .mockResolvedValueOnce([]);
    apiMock.getCoachBrainCandidateStats
      .mockResolvedValueOnce({ total_pending: 1 })
      .mockResolvedValueOnce({ total_pending: 0 });
    apiMock.approveCoachBrainCandidate.mockResolvedValue({
      candidate_id: candidate.id,
      entry_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      qdrant_point_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
    });

    renderPage();

    const approveBtn = await screen.findByRole("button", { name: /^approve$/i });
    await userEvent.click(approveBtn);

    await waitFor(() =>
      expect(apiMock.approveCoachBrainCandidate).toHaveBeenCalledWith(
        candidate.id,
        undefined,
      ),
    );
    await waitFor(() =>
      expect(screen.getByText(/no candidates to review/i)).toBeTruthy(),
    );
  });

  it("sends content_override when admin edits content inline", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });
    apiMock.approveCoachBrainCandidate.mockResolvedValue({
      candidate_id: candidate.id,
      entry_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      qdrant_point_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
    });

    renderPage();

    const editBtn = await screen.findByRole("button", { name: /^edit$/i });
    await userEvent.click(editBtn);

    const textarea = screen.getByRole("textbox", { name: /content/i });
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "edited cue text");

    const approveBtn = screen.getByRole("button", { name: /approve edited/i });
    await userEvent.click(approveBtn);

    await waitFor(() =>
      expect(apiMock.approveCoachBrainCandidate).toHaveBeenCalledWith(
        candidate.id,
        "edited cue text",
      ),
    );
  });

  it("surfaces approve failure without advancing", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });
    apiMock.approveCoachBrainCandidate.mockRejectedValue({
      status: 502,
      error: { code: "QDRANT_UPSERT_FAILED", message: "retry later" },
    });

    renderPage();

    const approveBtn = await screen.findByRole("button", { name: /^approve$/i });
    await userEvent.click(approveBtn);

    await waitFor(() =>
      expect(screen.getByText(/approve failed/i)).toBeTruthy(),
    );
    expect(screen.getByText(/tuck elbows at 45 degrees/i)).toBeTruthy();
  });
});

describe("AdminCoachBrainCandidatesPage - reject", () => {
  it("prompts for reason then rejects and advances", async () => {
    apiMock.listCoachBrainCandidates
      .mockResolvedValueOnce([candidate])
      .mockResolvedValueOnce([]);
    apiMock.getCoachBrainCandidateStats
      .mockResolvedValueOnce({ total_pending: 1 })
      .mockResolvedValueOnce({ total_pending: 0 });
    apiMock.rejectCoachBrainCandidate.mockResolvedValue({
      candidate_id: candidate.id,
      rejected_reason: "off-topic",
    });

    renderPage();

    const rejectBtn = await screen.findByRole("button", { name: /^reject$/i });
    await userEvent.click(rejectBtn);

    const reasonInput = screen.getByRole("textbox", { name: /reason/i });
    await userEvent.type(reasonInput, "off-topic");

    const confirmBtn = screen.getByRole("button", { name: /confirm reject/i });
    await userEvent.click(confirmBtn);

    await waitFor(() =>
      expect(apiMock.rejectCoachBrainCandidate).toHaveBeenCalledWith(
        candidate.id,
        "off-topic",
      ),
    );
    await waitFor(() =>
      expect(screen.getByText(/no candidates to review/i)).toBeTruthy(),
    );
  });

  it("disables confirm button when reason is blank", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });

    renderPage();

    const rejectBtn = await screen.findByRole("button", { name: /^reject$/i });
    await userEvent.click(rejectBtn);

    const confirmBtn = screen.getByRole("button", {
      name: /confirm reject/i,
    }) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);
  });
});

describe("AdminCoachBrainCandidatesPage - keyboard shortcuts", () => {
  it("approves on 'a' when mode is view", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });
    apiMock.approveCoachBrainCandidate.mockResolvedValue({
      candidate_id: candidate.id,
      entry_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      qdrant_point_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
    });

    renderPage();
    await screen.findByText(/tuck elbows at 45 degrees/i);
    await userEvent.keyboard("a");

    await waitFor(() =>
      expect(apiMock.approveCoachBrainCandidate).toHaveBeenCalledWith(
        candidate.id,
        undefined,
      ),
    );
  });

  it("skips on 's' without mutating backend", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([
      candidate,
      { ...candidate, id: "cccccccc-cccc-cccc-cccc-cccccccccccc", content: "Second" },
    ]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 2 });

    renderPage();
    await screen.findByText(/tuck elbows at 45 degrees/i);
    await userEvent.keyboard("s");

    await waitFor(() => expect(screen.getByText(/second/i)).toBeTruthy());
    expect(apiMock.approveCoachBrainCandidate).not.toHaveBeenCalled();
    expect(apiMock.rejectCoachBrainCandidate).not.toHaveBeenCalled();
  });

  it("does not trigger 'a' while typing in edit textarea", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });

    renderPage();

    const editBtn = await screen.findByRole("button", { name: /^edit$/i });
    await userEvent.click(editBtn);
    const textarea = screen.getByRole("textbox", { name: /content/i });
    await userEvent.click(textarea);
    await userEvent.type(textarea, "a");

    expect(apiMock.approveCoachBrainCandidate).not.toHaveBeenCalled();
  });

});

describe("AdminCoachBrainCandidatesPage - SimilarEntriesList", () => {
  it("renders top 2 similar entries on the review card", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });
    apiMock.getCoachBrainCandidateSimilar.mockResolvedValueOnce({
      items: [
        {
          id: "e1",
          content: "drive knees out at the bottom",
          exercise: "squat",
          phase: "descent",
          entry_type: "cue",
          cosine_sim: 0.88,
        },
        {
          id: "e2",
          content: "push the floor apart",
          exercise: "squat",
          phase: "ascent",
          entry_type: "cue",
          cosine_sim: 0.81,
        },
      ],
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/drive knees out at the bottom/i)).toBeTruthy(),
    );
    expect(screen.getByText(/push the floor apart/i)).toBeTruthy();
    expect(screen.getByText(/0\.880/)).toBeTruthy();
    expect(screen.getByText(/0\.810/)).toBeTruthy();
  });

  it("renders nothing when no similar entries are returned", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValue([candidate]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValue({ total_pending: 1 });
    apiMock.getCoachBrainCandidateSimilar.mockResolvedValueOnce({ items: [] });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/tuck elbows at 45 degrees/i)).toBeTruthy(),
    );
    expect(screen.queryByText(/similar existing entries/i)).toBeNull();
  });
});

describe("AdminCoachBrainCandidatesPage - confirmation count badge", () => {
  it("renders 'Confirms #N' when nearest_entry_confirmation_count is set", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValueOnce([
      {
        ...candidate,
        id: "00000000-0000-0000-0000-000000000001",
        lifecycle_decision: "UPDATE",
        nearest_entry_id: "00000000-0000-0000-0000-000000000099",
        nearest_cosine_sim: 0.81,
        nearest_entry_confirmation_count: 7,
      },
    ]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValueOnce({ total_pending: 1 });

    renderPage();

    expect(await screen.findByText("Confirms #7")).toBeTruthy();
  });

  it("renders 'New (no near match)' when nearest_entry_id is null", async () => {
    apiMock.listCoachBrainCandidates.mockResolvedValueOnce([
      {
        ...candidate,
        id: "00000000-0000-0000-0000-000000000002",
        nearest_entry_id: null,
        nearest_cosine_sim: null,
        nearest_entry_confirmation_count: null,
      },
    ]);
    apiMock.getCoachBrainCandidateStats.mockResolvedValueOnce({ total_pending: 1 });

    renderPage();

    expect(await screen.findByText("New (no near match)")).toBeTruthy();
  });
});
