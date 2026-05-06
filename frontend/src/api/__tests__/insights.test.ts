import { afterEach, describe, expect, test, vi, beforeEach } from "vitest";
import { getExerciseInsights, getGlobalInsights } from "@/api/insights";

// Mock supabase
const mockGetSession = vi.fn();
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: (...args: unknown[]) => mockGetSession(...args),
    },
  },
}));

afterEach(() => {
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.clearAllMocks();
  mockGetSession.mockResolvedValue({
    data: { session: { access_token: "test-token-abc" } },
  });
});

// ---------------------------------------------------------------------------
// getExerciseInsights
// ---------------------------------------------------------------------------
describe("getExerciseInsights", () => {
  test("returns exercise insights on 200", async () => {
    const payload = {
      rolling_avg_confidence: [0.8, 0.85, 0.9],
      rep_count_trend: [5, 5, 6],
      most_common_warning: "Depth",
      personal_best_confidence: 0.92,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getExerciseInsights("squat", "high_bar");
    expect(result.personal_best_confidence).toBe(0.92);
    expect(result.most_common_warning).toBe("Depth");
    expect(result.rolling_avg_confidence).toHaveLength(3);
  });

  test("throws Not authenticated when no session token", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    await expect(getExerciseInsights("squat", "high_bar")).rejects.toThrow(
      "Not authenticated",
    );
  });

  test("throws with error.message on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Exercise insights unavailable" } }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(getExerciseInsights("squat", "high_bar")).rejects.toThrow(
      "Exercise insights unavailable",
    );
  });

  test("throws with detail on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Not found" }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(getExerciseInsights("bench", "flat")).rejects.toThrow("Not found");
  });

  test("throws fallback message on non-parseable error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("bad", { status: 500 }),
    );

    await expect(getExerciseInsights("deadlift", "conventional")).rejects.toThrow(
      "Failed to fetch exercise insights",
    );
  });

  test("error includes status code", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Server error" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );

    try {
      await getExerciseInsights("squat", "low_bar");
    } catch (err) {
      expect((err as Error & { status: number }).status).toBe(503);
    }
  });

  test("URL-encodes type and variant", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ rolling_avg_confidence: [], rep_count_trend: [], most_common_warning: null, personal_best_confidence: 0 }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await getExerciseInsights("squat", "high bar");
    const [url] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toContain("high%20bar");
  });
});

// ---------------------------------------------------------------------------
// getGlobalInsights
// ---------------------------------------------------------------------------
describe("getGlobalInsights", () => {
  test("returns global insights on 200", async () => {
    const payload = {
      most_common_warning: "Depth below parallel",
      highest_variance_exercise: "deadlift",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getGlobalInsights();
    expect(result.most_common_warning).toBe("Depth below parallel");
    expect(result.highest_variance_exercise).toBe("deadlift");
  });

  test("returns null fields when no data", async () => {
    const payload = {
      most_common_warning: null,
      highest_variance_exercise: null,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getGlobalInsights();
    expect(result.most_common_warning).toBeNull();
    expect(result.highest_variance_exercise).toBeNull();
  });

  test("throws Not authenticated when no session token", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    await expect(getGlobalInsights()).rejects.toThrow("Not authenticated");
  });

  test("throws with error.message on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Global insights error" } }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(getGlobalInsights()).rejects.toThrow("Global insights error");
  });

  test("throws with detail on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Global detail error" }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(getGlobalInsights()).rejects.toThrow("Global detail error");
  });

  test("throws fallback message on non-parseable error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("broken", { status: 502 }),
    );

    await expect(getGlobalInsights()).rejects.toThrow("Failed to fetch global insights");
  });

  test("error includes status code", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Error" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    try {
      await getGlobalInsights();
    } catch (err) {
      expect((err as Error & { status: number }).status).toBe(404);
    }
  });

  test("sends Authorization header with token", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ most_common_warning: null, highest_variance_exercise: null }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await getGlobalInsights();
    const [, init] = fetchSpy.mock.calls[0]!;
    expect((init?.headers as Record<string, string>)?.Authorization).toBe(
      "Bearer test-token-abc",
    );
  });
});
