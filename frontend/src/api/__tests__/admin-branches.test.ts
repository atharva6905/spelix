/**
 * Branch coverage tests for admin.ts — covers the adminFetch error branches,
 * 204 status handling, auth failure, and optional filter params.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  listAdminUsers,
  deleteAdminUser,
  disableAdminUser,
  listAdminAnalyses,
  getAdminHealth,
  listRagDocuments,
  deleteRagDocument,
  reEmbedRagDocument,
  listExpertQueue,
  getExpertQueueStats,
  listCoachBrainEntries,
} from "@/api/admin";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "admin-token" } },
      }),
    },
  },
}));

import { supabase } from "@/lib/supabase";

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// adminFetch — error branch
// ---------------------------------------------------------------------------

describe("adminFetch error branch", () => {
  it("throws error object with status when response is not ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ message: "Forbidden" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getAdminHealth()).rejects.toMatchObject({ status: 403 });
  });

  it("throws with body.detail when present", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { code: "PERMISSION_DENIED" } }),
        { status: 403, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(getAdminHealth()).rejects.toMatchObject({ status: 403, code: "PERMISSION_DENIED" });
  });

  it("throws Not authenticated when no session", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValueOnce({ data: { session: null }, error: null } as Awaited<ReturnType<typeof supabase.auth.getSession>>);
    await expect(getAdminHealth()).rejects.toThrow("Not authenticated");
  });

  it("handles body parse failure gracefully on error (catches to {})", async () => {
    // Response body not valid JSON → catch(() => ({})) branch
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not json", { status: 500 }),
    );
    await expect(getAdminHealth()).rejects.toMatchObject({ status: 500 });
  });
});

// ---------------------------------------------------------------------------
// adminFetch — 204 status branch
// ---------------------------------------------------------------------------

describe("adminFetch 204 branch", () => {
  it("deleteAdminUser: returns undefined on 204 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    const result = await deleteAdminUser("user-1");
    expect(result).toBeUndefined();
  });

  it("deleteRagDocument: returns undefined on 204", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    const result = await deleteRagDocument("doc-1");
    expect(result).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// listAdminUsers
// ---------------------------------------------------------------------------

describe("listAdminUsers", () => {
  it("passes default limit and offset", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listAdminUsers();
    expect(capturedUrl).toContain("limit=50");
    expect(capturedUrl).toContain("offset=0");
  });

  it("passes custom limit and offset", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listAdminUsers(10, 20);
    expect(capturedUrl).toContain("limit=10");
    expect(capturedUrl).toContain("offset=20");
  });
});

// ---------------------------------------------------------------------------
// disableAdminUser
// ---------------------------------------------------------------------------

describe("disableAdminUser", () => {
  it("returns message object on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ message: "User disabled" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const result = await disableAdminUser("user-1");
    expect(result.message).toBe("User disabled");
  });
});

// ---------------------------------------------------------------------------
// listAdminAnalyses — status filter branch
// ---------------------------------------------------------------------------

describe("listAdminAnalyses", () => {
  it("does NOT include status param when not provided", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listAdminAnalyses();
    expect(capturedUrl).not.toContain("status=");
  });

  it("includes status param when provided", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listAdminAnalyses(50, 0, "completed");
    expect(capturedUrl).toContain("status=completed");
  });
});

// ---------------------------------------------------------------------------
// listRagDocuments — filter branch
// ---------------------------------------------------------------------------

describe("listRagDocuments", () => {
  it("adds no filter params when filters is undefined", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listRagDocuments();
    expect(capturedUrl).not.toContain("review_status=");
    expect(capturedUrl).not.toContain("exercise_tag=");
    expect(capturedUrl).not.toContain("quality_tier=");
  });

  it("adds review_status filter when provided", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listRagDocuments(50, 0, { review_status: "approved" });
    expect(capturedUrl).toContain("review_status=approved");
  });

  it("adds exercise_tag filter when provided", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listRagDocuments(50, 0, { exercise_tag: "squat" });
    expect(capturedUrl).toContain("exercise_tag=squat");
  });

  it("adds quality_tier filter when provided", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listRagDocuments(50, 0, { quality_tier: "L1_systematic_review" });
    expect(capturedUrl).toContain("quality_tier=L1_systematic_review");
  });
});

// ---------------------------------------------------------------------------
// listCoachBrainEntries — filter branch
// ---------------------------------------------------------------------------

describe("listCoachBrainEntries", () => {
  it("adds no filter params when filters is undefined", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listCoachBrainEntries();
    expect(capturedUrl).not.toContain("exercise=");
    expect(capturedUrl).not.toContain("status=");
    expect(capturedUrl).not.toContain("entry_type=");
  });

  it("adds exercise filter when provided", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listCoachBrainEntries(50, 0, { exercise: "squat" });
    expect(capturedUrl).toContain("exercise=squat");
  });

  it("adds status filter when provided", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listCoachBrainEntries(50, 0, { status: "active" });
    expect(capturedUrl).toContain("status=active");
  });

  it("adds entry_type filter when provided", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await listCoachBrainEntries(50, 0, { entry_type: "cue" });
    expect(capturedUrl).toContain("entry_type=cue");
  });
});

// ---------------------------------------------------------------------------
// reEmbedRagDocument
// ---------------------------------------------------------------------------

describe("reEmbedRagDocument", () => {
  it("returns message and document_id on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ message: "Re-embedding queued", document_id: "doc-1" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const result = await reEmbedRagDocument("doc-1");
    expect(result.message).toBe("Re-embedding queued");
    expect(result.document_id).toBe("doc-1");
  });
});

// ---------------------------------------------------------------------------
// listExpertQueue / getExpertQueueStats
// ---------------------------------------------------------------------------

describe("listExpertQueue", () => {
  it("returns queue items on success", async () => {
    const items = [{
      analysis_id: "a1",
      exercise_type: "squat",
      exercise_variant: "high_bar",
      confidence_score: null,
      flagged_for_review: true,
      created_at: "2026-01-01T00:00:00Z",
      annotation_count: 0,
      latest_annotation_at: null,
    }];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(items), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await listExpertQueue();
    expect(result).toHaveLength(1);
  });
});

describe("getExpertQueueStats", () => {
  it("returns stats object on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ total_flagged: 5, total_annotated: 3, golden_dataset_count: 1 }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const result = await getExpertQueueStats();
    expect(result.total_flagged).toBe(5);
    expect(result.total_annotated).toBe(3);
  });
});
