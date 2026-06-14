import { afterEach, describe, expect, test, vi, beforeEach } from "vitest";
import { getConsents, grantConsent, withdrawConsent } from "@/api/consent";
import { isApiError } from "@/api/errors";

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
    data: { session: { access_token: "test-token-123" } },
  });
});

// ---------------------------------------------------------------------------
// getConsents
// ---------------------------------------------------------------------------
describe("getConsents", () => {
  test("returns parsed consent status on 200", async () => {
    const payload = [
      {
        consent_type: "analytics",
        granted: true,
        granted_at: "2026-01-01T00:00:00Z",
        withdrawn_at: null,
        consent_version: "1.0",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getConsents();
    expect(result).toHaveLength(1);
    expect(result[0].consent_type).toBe("analytics");
    expect(result[0].granted).toBe(true);
  });

  test("throws with detail message on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getConsents()).rejects.toThrow("Unauthorized");
  });

  test("throws with error.message on non-ok response with error field", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Custom error message" } }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(getConsents()).rejects.toThrow("Custom error message");
  });

  test("throws with fallback message on non-ok response with invalid json", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not json", { status: 503 }),
    );

    await expect(getConsents()).rejects.toThrow("Failed to fetch consent status");
  });

  test("throws Not authenticated when no session token", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    await expect(getConsents()).rejects.toThrow("Not authenticated");
  });

  // Issue #294: migrated to the shared ApiError idiom. Message + status preserved.
  test("throws an ApiError carrying message + status (issue #294)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getConsents()).rejects.toSatisfy(
      (e) => isApiError(e) && e.status === 401 && e.message === "Unauthorized",
    );
  });

  test("sends Authorization header with token", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await getConsents();
    const [, init] = fetchSpy.mock.calls[0]!;
    expect((init?.headers as Record<string, string>)?.Authorization).toBe(
      "Bearer test-token-123",
    );
  });
});

// ---------------------------------------------------------------------------
// grantConsent
// ---------------------------------------------------------------------------
describe("grantConsent", () => {
  test("returns consent record on 200", async () => {
    const record = {
      id: "rec-1",
      user_id: "user-1",
      consent_type: "health_data_processing",
      granted: true,
      granted_at: "2026-01-01T00:00:00Z",
      withdrawn_at: null,
      consent_version: "1.0",
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(record), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await grantConsent("health_data_processing", "1.0");
    expect(result.consent_type).toBe("health_data_processing");
    expect(result.granted).toBe(true);
  });

  test("throws with error.message on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Grant failed" } }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(grantConsent("analytics", "1.0")).rejects.toThrow("Grant failed");
  });

  test("throws with detail on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Bad request detail" }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(grantConsent("analytics", "1.0")).rejects.toThrow("Bad request detail");
  });

  test("throws fallback message when body is not parseable", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not json", { status: 500 }),
    );

    await expect(grantConsent("analytics", "1.0")).rejects.toThrow(
      "Failed to grant consent",
    );
  });

  test("throws Not authenticated when no session", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    await expect(grantConsent("analytics", "1.0")).rejects.toThrow(
      "Not authenticated",
    );
  });

  // Issue #294: migrated to the shared ApiError idiom. Message + status preserved.
  test("throws an ApiError carrying message + status (issue #294)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "Grant failed" } }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(grantConsent("analytics", "1.0")).rejects.toSatisfy(
      (e) => isApiError(e) && e.status === 400 && e.message === "Grant failed",
    );
  });

  test("sends POST with correct body", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ id: "r", user_id: "u", consent_type: "analytics", granted: true, granted_at: null, withdrawn_at: null, consent_version: "2.0", created_at: "2026-01-01T00:00:00Z" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await grantConsent("analytics", "2.0");
    const [, init] = fetchSpy.mock.calls[0]!;
    expect(init?.method).toBe("POST");
    const body = JSON.parse(init!.body as string);
    expect(body).toEqual({ consent_type: "analytics", consent_version: "2.0" });
  });
});

// ---------------------------------------------------------------------------
// withdrawConsent
// ---------------------------------------------------------------------------
describe("withdrawConsent", () => {
  test("returns consent record on 200", async () => {
    const record = {
      id: "rec-2",
      user_id: "user-1",
      consent_type: "coach_brain_contribution",
      granted: false,
      granted_at: null,
      withdrawn_at: "2026-05-01T00:00:00Z",
      consent_version: "1.0",
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(record), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await withdrawConsent("coach_brain_contribution");
    expect(result.granted).toBe(false);
  });

  test("throws with error.message on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error: { message: "Withdraw failed" } }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(withdrawConsent("analytics")).rejects.toThrow("Withdraw failed");
  });

  test("throws with detail on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Withdraw detail error" }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(withdrawConsent("analytics")).rejects.toThrow("Withdraw detail error");
  });

  test("throws fallback message when body is not parseable", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not json", { status: 503 }),
    );

    await expect(withdrawConsent("analytics")).rejects.toThrow(
      "Failed to withdraw consent",
    );
  });

  test("throws Not authenticated when no session", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    await expect(withdrawConsent("analytics")).rejects.toThrow("Not authenticated");
  });

  // Issue #294: migrated to the shared ApiError idiom. Message + status preserved.
  test("throws an ApiError carrying message + status (issue #294)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Withdraw detail error" }), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(withdrawConsent("analytics")).rejects.toSatisfy(
      (e) => isApiError(e) && e.status === 422 && e.message === "Withdraw detail error",
    );
  });

  test("sends POST to withdraw endpoint with correct body", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ id: "r", user_id: "u", consent_type: "analytics", granted: false, granted_at: null, withdrawn_at: "2026-01-01T00:00:00Z", consent_version: "1.0", created_at: "2026-01-01T00:00:00Z" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await withdrawConsent("analytics");
    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toMatch(/\/consent\/withdraw$/);
    expect(init?.method).toBe("POST");
    const body = JSON.parse(init!.body as string);
    expect(body).toEqual({ consent_type: "analytics" });
  });
});
