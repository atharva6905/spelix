import { afterEach, describe, expect, test, vi } from "vitest";
import { requestBetaAccess, type BetaRequestSource } from "@/api/beta";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("requestBetaAccess", () => {
  test("POSTs email + source + consent and returns response body on 201", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "00000000-0000-0000-0000-000000000000",
          email: "a@b.com",
          status: "pending",
          created_at: "2026-04-15T00:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const resp = await requestBetaAccess({
      email: "a@b.com",
      source: "hero" satisfies BetaRequestSource,
      consented: true,
    });

    expect(resp.status).toBe("pending");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toMatch(/\/api\/v1\/beta\/requests$/);
    expect(init?.method).toBe("POST");
    const body = JSON.parse(init!.body as string);
    expect(body).toEqual({
      email: "a@b.com",
      source: "hero",
      consented_to_beta_terms: true,
    });
  });

  test("throws on 409 with parsed error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            error: {
              code: "beta_request_duplicate",
              message: "Already on the list.",
            },
          },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      requestBetaAccess({
        email: "dup@b.com",
        source: "hero",
        consented: true,
      }),
    ).rejects.toMatchObject({ status: 409 });
  });

  test("throws on network error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));

    await expect(
      requestBetaAccess({
        email: "a@b.com",
        source: "hero",
        consented: true,
      }),
    ).rejects.toThrow(/offline/);
  });
});
