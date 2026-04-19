import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listCoachBrainCandidates,
  approveCoachBrainCandidate,
  rejectCoachBrainCandidate,
  getCoachBrainCandidateSimilar,
  type CoachBrainCandidate,
} from "@/api/admin";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

const fakeCandidate: CoachBrainCandidate = {
  id: "11111111-1111-1111-1111-111111111111",
  exercise: "bench",
  phase: "descent",
  entry_type: "cue",
  content: "Tuck elbows.",
  trigger_tags: ["bench"],
  source_analysis_ids: ["22222222-2222-2222-2222-222222222222"],
  confidence_score: null,
  eval_scores: { faithfulness: 0.82 },
  cove_verified: false,
  cove_explanation: "evaluation_failed",
  lifecycle_decision: "ADD",
  nearest_entry_id: null,
  nearest_cosine_sim: null,
  contradiction_flag: false,
  review_status: "pending",
  created_at: "2026-04-17T10:02:31Z",
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("listCoachBrainCandidates", () => {
  it("calls GET with auth header", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([fakeCandidate]), { status: 200 }),
    );
    const rows = await listCoachBrainCandidates(10, 0);
    expect(rows).toHaveLength(1);
    expect(rows[0]!.exercise).toBe("bench");
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/admin/coach-brain/candidates?limit=10&offset=0"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
        }),
      }),
    );
  });
});

describe("approveCoachBrainCandidate", () => {
  it("POSTs empty body when no override provided", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          candidate_id: fakeCandidate.id,
          entry_id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
          qdrant_point_id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
        }),
        { status: 200 },
      ),
    );
    const resp = await approveCoachBrainCandidate(fakeCandidate.id);
    expect(resp.entry_id).toBe("ffffffff-ffff-ffff-ffff-ffffffffffff");
    const init = fetchSpy.mock.calls[0]![1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({}));
  });

  it("POSTs content_override when provided", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          candidate_id: fakeCandidate.id,
          entry_id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
          qdrant_point_id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
        }),
        { status: 200 },
      ),
    );
    await approveCoachBrainCandidate(fakeCandidate.id, "edited cue");
    const init = fetchSpy.mock.calls[0]![1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ content_override: "edited cue" }));
  });
});

describe("rejectCoachBrainCandidate", () => {
  it("POSTs reason in body", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          candidate_id: fakeCandidate.id,
          rejected_reason: "off-topic",
        }),
        { status: 200 },
      ),
    );
    await rejectCoachBrainCandidate(fakeCandidate.id, "off-topic");
    const init = fetchSpy.mock.calls[0]![1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ reason: "off-topic" }));
  });
});

describe("getCoachBrainCandidateSimilar", () => {
  it("fetches top 2 similar entries", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              id: "aaa",
              content: "knees out",
              exercise: "squat",
              phase: "descent",
              entry_type: "cue",
              cosine_sim: 0.88,
            },
            {
              id: "bbb",
              content: "push floor apart",
              exercise: "squat",
              phase: "ascent",
              entry_type: "cue",
              cosine_sim: 0.81,
            },
          ],
        }),
        { status: 200 },
      ),
    );
    const resp = await getCoachBrainCandidateSimilar("c1");
    expect(resp.items).toHaveLength(2);
    expect(resp.items[0]!.cosine_sim).toBe(0.88);
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/admin/coach-brain/candidates/c1/similar"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
        }),
      }),
    );
  });
});
