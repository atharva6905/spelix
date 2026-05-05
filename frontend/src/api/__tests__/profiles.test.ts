import { afterEach, describe, expect, test, vi, beforeEach } from "vitest";
import { getProfile, updateProfile } from "@/api/profiles";

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
    data: { session: { access_token: "profile-token-xyz" } },
  });
});

const PROFILE_FIXTURE = {
  id: "p-1",
  user_id: "u-1",
  height_cm: 175,
  weight_kg: 80,
  age: 28,
  experience_level: "intermediate",
  arm_span_cm: 178,
  femur_length_cm: 46,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// getProfile
// ---------------------------------------------------------------------------
describe("getProfile", () => {
  test("returns profile on 200", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(PROFILE_FIXTURE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getProfile();
    expect(result.height_cm).toBe(175);
    expect(result.experience_level).toBe("intermediate");
  });

  test("throws Not authenticated when no session", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    await expect(getProfile()).rejects.toThrow("Not authenticated");
  });

  test("throws on 404 with status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    try {
      await getProfile();
      expect.fail("should have thrown");
    } catch (err) {
      expect((err as { status: number }).status).toBe(404);
    }
  });

  test("throws on 500 with body spread", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: { message: "Server error" } }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );

    try {
      await getProfile();
      expect.fail("should have thrown");
    } catch (err) {
      expect((err as { status: number }).status).toBe(500);
    }
  });

  test("throws on non-parseable error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not json", { status: 503 }),
    );

    try {
      await getProfile();
      expect.fail("should have thrown");
    } catch (err) {
      expect((err as { status: number }).status).toBe(503);
    }
  });

  test("sends Authorization header", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(PROFILE_FIXTURE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await getProfile();
    const [, init] = fetchSpy.mock.calls[0]!;
    expect((init?.headers as Record<string, string>)?.Authorization).toBe(
      "Bearer profile-token-xyz",
    );
  });

  test("handles null optional fields", async () => {
    const profileWithNulls = { ...PROFILE_FIXTURE, arm_span_cm: null, femur_length_cm: null };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(profileWithNulls), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getProfile();
    expect(result.arm_span_cm).toBeNull();
    expect(result.femur_length_cm).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// updateProfile
// ---------------------------------------------------------------------------
describe("updateProfile", () => {
  test("returns updated profile on 200", async () => {
    const updated = { ...PROFILE_FIXTURE, height_cm: 180 };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(updated), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await updateProfile({
      height_cm: 180,
      weight_kg: 80,
      age: 28,
      experience_level: "intermediate",
    });
    expect(result.height_cm).toBe(180);
  });

  test("throws Not authenticated when no session", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    await expect(
      updateProfile({
        height_cm: 175,
        weight_kg: 80,
        age: 28,
        experience_level: "beginner",
      }),
    ).rejects.toThrow("Not authenticated");
  });

  test("throws on non-ok response with status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Validation error" }), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      }),
    );

    try {
      await updateProfile({
        height_cm: -1,
        weight_kg: 80,
        age: 28,
        experience_level: "beginner",
      });
      expect.fail("should have thrown");
    } catch (err) {
      expect((err as { status: number }).status).toBe(422);
    }
  });

  test("throws on non-parseable error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("bad body", { status: 500 }),
    );

    try {
      await updateProfile({
        height_cm: 175,
        weight_kg: 80,
        age: 28,
        experience_level: "advanced",
      });
      expect.fail("should have thrown");
    } catch (err) {
      expect((err as { status: number }).status).toBe(500);
    }
  });

  test("sends PUT method with JSON body", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(PROFILE_FIXTURE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const payload = {
      height_cm: 175,
      weight_kg: 80,
      age: 28,
      experience_level: "intermediate" as const,
      arm_span_cm: 178,
      femur_length_cm: null,
    };
    await updateProfile(payload);

    const [, init] = fetchSpy.mock.calls[0]!;
    expect(init?.method).toBe("PUT");
    const body = JSON.parse(init!.body as string);
    expect(body.height_cm).toBe(175);
    expect(body.arm_span_cm).toBe(178);
    expect(body.femur_length_cm).toBeNull();
  });
});
