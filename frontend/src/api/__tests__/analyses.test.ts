import { afterEach, describe, expect, test, vi } from "vitest";

import { getAnalysisDetail } from "@/api/analyses";

// Mock supabase so getAuthToken returns a deterministic token without
// hitting the real client.
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi
        .fn()
        .mockResolvedValue({ data: { session: { access_token: "test-token" } } }),
    },
  },
}));

afterEach(() => {
  vi.restoreAllMocks();
});

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
});
