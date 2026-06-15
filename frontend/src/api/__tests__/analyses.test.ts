import { afterEach, describe, expect, test, vi } from "vitest";

import {
  getAnalysisDetail,
  createAnalysis,
  startAnalysis,
  getAnalysisStatus,
  listAnalyses,
  getChatHistory,
  sendChatMessage,
  authHeaders,
  extractBarPath,
} from "@/api/analyses";
import { isApiError } from "@/api/errors";

// Mock supabase so getAuthToken returns a deterministic token without
// hitting the real client.
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

// Import the mocked supabase to manipulate session in specific tests
import { supabase } from "@/lib/supabase";

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// authHeaders
// ---------------------------------------------------------------------------

describe("authHeaders", () => {
  test("returns Authorization header with Bearer token", async () => {
    const headers = await authHeaders();
    expect(headers).toEqual({ Authorization: "Bearer test-token" });
  });

  test("throws Not authenticated when no session", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValueOnce({
      data: { session: null },
      error: null,
    } as Awaited<ReturnType<typeof supabase.auth.getSession>>);
    await expect(authHeaders()).rejects.toThrow("Not authenticated");
  });
});

// ---------------------------------------------------------------------------
// getAnalysisDetail — 404 error coercion regression
// ---------------------------------------------------------------------------

describe("getAnalysisDetail — 404 error coercion regression", () => {
  // Regression: backend 404 response shape `{"detail": {...object...}}` used to
  // produce a thrown Error with message "[object Object]" because the object
  // was passed directly to `new Error()`, which coerces via String(obj).
  // The UI then rendered that literal "[object Object]" string in the alert.
  test("404 with object-shaped detail produces a readable Error message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            error: {
              code: "ANALYSIS_NOT_FOUND",
              message: "Analysis not found.",
            },
          },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      getAnalysisDetail("00000000-0000-0000-0000-000000000000"),
    ).rejects.toMatchObject({
      message: expect.not.stringMatching(/\[object Object\]/),
    });
  });

  test("404 with top-level error.message falls through to the message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "NOPE", message: "Specific backend reason" },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      getAnalysisDetail("00000000-0000-0000-0000-000000000000"),
    ).rejects.toThrow("Specific backend reason");
  });

  test("404 with string detail passes through verbatim", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      getAnalysisDetail("00000000-0000-0000-0000-000000000000"),
    ).rejects.toThrow("Not found");
  });

  test("200 response returns parsed JSON", async () => {
    const detail = {
      id: "abc",
      status: "completed",
      exercise_type: "squat",
      exercise_variant: "high_bar",
      confidence_score: 0.85,
      video_path: null,
      annotated_video_path: null,
      plot_path: null,
      pdf_path: null,
      tags: null,
      quality_gate_result: null,
      summary_json: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      coaching_result: null,
      rep_metrics: [],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(detail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getAnalysisDetail("abc");
    expect(result.id).toBe("abc");
    expect(result.status).toBe("completed");
  });

  test("throws 'Failed to fetch analysis' when error shape has no message or detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      getAnalysisDetail("abc"),
    ).rejects.toThrow("Failed to fetch analysis");
  });

  // Issue #294: migrated to the shared ApiError idiom. Message + status preserved.
  test("throws an ApiError carrying the status (issue #294)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getAnalysisDetail("abc")).rejects.toSatisfy(
      (e) => isApiError(e) && e.status === 404 && e.message === "Not found",
    );
  });
});

// ---------------------------------------------------------------------------
// createAnalysis
// ---------------------------------------------------------------------------

describe("createAnalysis", () => {
  const req = {
    exercise_type: "squat" as const,
    exercise_variant: "high_bar" as const,
    filename: "test.mp4",
    file_size_bytes: 1024,
  };

  test("returns parsed response on 201", async () => {
    const resp = { id: "a1", upload_url: "https://s3/url", status: "queued", expires_at: "2026-01-01T01:00:00Z" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(resp), { status: 201, headers: { "Content-Type": "application/json" } }),
    );
    const result = await createAnalysis(req);
    expect(result.id).toBe("a1");
    expect(result.upload_url).toBe("https://s3/url");
  });

  test("throws with error.message on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: "LIMIT", message: "File too large" } }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(createAnalysis(req)).rejects.toMatchObject({ message: "File too large" });
  });

  test("throws with spread body on non-ok response when error key absent (covers detail branch)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Validation failed" }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );
    // createAnalysis spreads body.detail ?? body into the error object.
    // When detail is a string, spread produces char-indexed keys.
    // The key point is that the error is thrown (not swallowed).
    await expect(createAnalysis(req)).rejects.toMatchObject({ status: 422 });
  });

  test("throws Not authenticated when no session", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValueOnce({
      data: { session: null },
      error: null,
    } as Awaited<ReturnType<typeof supabase.auth.getSession>>);
    await expect(createAnalysis(req)).rejects.toThrow("Not authenticated");
  });
});

// ---------------------------------------------------------------------------
// startAnalysis
// ---------------------------------------------------------------------------

describe("startAnalysis", () => {
  test("returns id and status on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ id: "a1", status: "queued" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const result = await startAnalysis("a1");
    expect(result.id).toBe("a1");
    expect(result.status).toBe("queued");
  });

  test("throws error with message on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Analysis not found" } }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(startAnalysis("a1")).rejects.toThrow("Analysis not found");
  });

  test("throws fallback message when error shape missing", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), { status: 500, headers: { "Content-Type": "application/json" } }),
    );
    await expect(startAnalysis("a1")).rejects.toThrow("Failed to start analysis");
  });

  // Issue #294: migrated to the shared ApiError idiom. Message + status preserved.
  test("throws an ApiError carrying the status (issue #294)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Analysis not found" } }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(startAnalysis("a1")).rejects.toSatisfy(
      (e) => isApiError(e) && e.status === 404 && e.message === "Analysis not found",
    );
  });
});

// ---------------------------------------------------------------------------
// getAnalysisStatus
// ---------------------------------------------------------------------------

describe("getAnalysisStatus", () => {
  test("returns status response on success", async () => {
    const resp = { id: "a1", status: "processing", updated_at: "2026-01-01T00:00:00Z" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(resp), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await getAnalysisStatus("a1");
    expect(result.status).toBe("processing");
  });

  test("throws with error.message from body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Status unavailable" } }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(getAnalysisStatus("a1")).rejects.toThrow("Status unavailable");
  });

  test("throws with detail string from body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Not found" }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(getAnalysisStatus("a1")).rejects.toThrow("Not found");
  });

  test("throws fallback message when no message or detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), { status: 500, headers: { "Content-Type": "application/json" } }),
    );
    await expect(getAnalysisStatus("a1")).rejects.toThrow("Failed to fetch status");
  });

  // Issue #294: migrated to the shared ApiError idiom. Message + status preserved.
  test("throws an ApiError carrying the status (issue #294)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Not found" }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(getAnalysisStatus("a1")).rejects.toSatisfy(
      (e) => isApiError(e) && e.status === 404 && e.message === "Not found",
    );
  });
});

// ---------------------------------------------------------------------------
// listAnalyses
// ---------------------------------------------------------------------------

describe("listAnalyses", () => {
  test("returns list on success", async () => {
    const items = [{ id: "a1", status: "completed", exercise_type: "squat", exercise_variant: "high_bar", confidence_score: 0.85, created_at: "2026-01-01T00:00:00Z" }];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(items), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await listAnalyses();
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("a1");
  });

  test("passes limit and offset as query params", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }));
    });
    await listAnalyses(10, 20);
    expect(capturedUrl).toContain("limit=10");
    expect(capturedUrl).toContain("offset=20");
  });

  test("throws with error.message on non-ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Unauthorized" } }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(listAnalyses()).rejects.toThrow("Unauthorized");
  });

  test("throws with detail string on non-ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Rate limited" }),
        { status: 429, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(listAnalyses()).rejects.toThrow("Rate limited");
  });

  test("throws fallback message when no message or detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), { status: 500, headers: { "Content-Type": "application/json" } }),
    );
    await expect(listAnalyses()).rejects.toThrow("Failed to fetch analyses");
  });
});

// ---------------------------------------------------------------------------
// getChatHistory
// ---------------------------------------------------------------------------

describe("getChatHistory", () => {
  test("returns messages on success", async () => {
    const resp = { messages: [{ id: "m1", role: "user", content: "Hello", created_at: "2026-01-01T00:00:00Z" }] };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(resp), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await getChatHistory("a1");
    expect(result.messages).toHaveLength(1);
    expect(result.messages[0].role).toBe("user");
  });

  test("throws with detail on non-ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Chat not found" }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(getChatHistory("a1")).rejects.toThrow("Chat not found");
  });

  test("throws fallback when no detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), { status: 500, headers: { "Content-Type": "application/json" } }),
    );
    await expect(getChatHistory("a1")).rejects.toThrow("Failed to fetch chat history");
  });

  // Issue #294: migrated to the shared ApiError idiom. Message + status preserved.
  test("throws an ApiError carrying the status (issue #294)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Chat not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getChatHistory("a1")).rejects.toSatisfy(
      (e) => isApiError(e) && e.status === 404 && e.message === "Chat not found",
    );
  });
});

// ---------------------------------------------------------------------------
// sendChatMessage
// ---------------------------------------------------------------------------

describe("sendChatMessage", () => {
  test("returns message on success", async () => {
    const msg = { id: "m2", role: "assistant", content: "Reply", created_at: "2026-01-01T00:00:00Z" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(msg), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await sendChatMessage("a1", "Hello");
    expect(result.id).toBe("m2");
    expect(result.role).toBe("assistant");
  });

  test("throws with detail on non-ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Rate limited" }),
        { status: 429, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(sendChatMessage("a1", "Hello")).rejects.toThrow("Rate limited");
  });

  test("throws fallback when no detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({}), { status: 500, headers: { "Content-Type": "application/json" } }),
    );
    await expect(sendChatMessage("a1", "Hello")).rejects.toThrow("Failed to send message");
  });

  // Issue #294: migrated to the shared ApiError idiom. Message + status preserved.
  test("throws an ApiError carrying the status (issue #294)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Rate limited" }), {
        status: 429,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(sendChatMessage("a1", "Hello")).rejects.toSatisfy(
      (e) => isApiError(e) && e.status === 429 && e.message === "Rate limited",
    );
  });
});

// ---------------------------------------------------------------------------
// extractBarPath — hardened validation (FR-RESL-05, issue #206)
// ---------------------------------------------------------------------------

describe("extractBarPath", () => {
  test("returns null when summaryJson is null or undefined", () => {
    expect(extractBarPath(null)).toBeNull();
    expect(extractBarPath(undefined)).toBeNull();
  });

  test("returns null when bar_path is missing", () => {
    expect(extractBarPath({ rep_count: 3 })).toBeNull();
  });

  test("returns null when bar_path is explicitly null", () => {
    expect(extractBarPath({ bar_path: null })).toBeNull();
  });

  test("returns null when centroids is not an array", () => {
    expect(
      extractBarPath({ bar_path: { centroids: "nope", path_consistency: 1 } }),
    ).toBeNull();
  });

  test("returns null when a centroid element is non-numeric", () => {
    expect(
      extractBarPath({
        bar_path: { centroids: [["a", "b"]], path_consistency: 0.9 },
      }),
    ).toBeNull();
  });

  test("returns null when a centroid contains NaN", () => {
    expect(
      extractBarPath({
        bar_path: { centroids: [[0.5, NaN]], path_consistency: 0.9 },
      }),
    ).toBeNull();
  });

  test("returns null when a centroid contains Infinity", () => {
    expect(
      extractBarPath({
        bar_path: { centroids: [[0.5, Infinity]], path_consistency: 0.9 },
      }),
    ).toBeNull();
  });

  test("returns null when a centroid has the wrong arity", () => {
    expect(
      extractBarPath({
        bar_path: { centroids: [[0.5]], path_consistency: 0.9 },
      }),
    ).toBeNull();
  });

  test("returns the BarPath for a valid trajectory", () => {
    const result = extractBarPath({
      bar_path: {
        centroids: [
          [0.5, 0.2],
          [0.51, 0.9],
        ],
        path_consistency: 0.96,
      },
    });
    expect(result).not.toBeNull();
    expect(result?.centroids).toEqual([
      [0.5, 0.2],
      [0.51, 0.9],
    ]);
    expect(result?.path_consistency).toBe(0.96);
  });

  test("keeps empty centroids as a valid BarPath (NOT null)", () => {
    const result = extractBarPath({
      bar_path: { centroids: [], path_consistency: 1 },
    });
    expect(result).not.toBeNull();
    expect(result?.centroids).toEqual([]);
  });

  test("keeps the trajectory even when path_consistency is non-finite (decision b)", () => {
    const result = extractBarPath({
      bar_path: { centroids: [[0.5, 0.5]], path_consistency: NaN },
    });
    expect(result).not.toBeNull();
    expect(result?.centroids).toEqual([[0.5, 0.5]]);
  });

  test("keeps the trajectory even when path_consistency is missing (decision b)", () => {
    const result = extractBarPath({
      bar_path: { centroids: [[0.5, 0.5]] },
    });
    expect(result).not.toBeNull();
    expect(result?.centroids).toEqual([[0.5, 0.5]]);
  });
});
