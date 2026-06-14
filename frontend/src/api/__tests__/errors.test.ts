import { describe, it, expect } from "vitest";

import { ApiError, isApiError, buildApiError } from "@/api/errors";

describe("ApiError", () => {
  it("is a real Error subclass carrying status/code/detail", () => {
    const err = new ApiError({
      status: 409,
      message: "Already on the list.",
      code: "DUP",
      detail: { error: { code: "DUP", message: "Already on the list." } },
    });
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.name).toBe("ApiError");
    expect(err.status).toBe(409);
    expect(err.code).toBe("DUP");
    expect(err.message).toBe("Already on the list.");
    expect(err.detail).toEqual({
      error: { code: "DUP", message: "Already on the list." },
    });
  });
});

describe("isApiError", () => {
  it("returns true for a real ApiError instance", () => {
    expect(isApiError(new ApiError({ status: 500, message: "x" }))).toBe(true);
  });

  it("duck-types on name + numeric status across realm boundaries", () => {
    const lookalike = Object.assign(new Error("x"), {
      name: "ApiError",
      status: 409,
    });
    expect(isApiError(lookalike)).toBe(true);
  });

  it("returns false for a bare object literal (drift guard)", () => {
    expect(isApiError({ status: 409, error: { code: "X" } })).toBe(false);
    expect(isApiError(new Error("plain"))).toBe(false);
    expect(isApiError(null)).toBe(false);
  });
});

describe("buildApiError", () => {
  it("unwraps FastAPI {detail:{error:{code,message}}}", () => {
    const err = buildApiError(422, {
      detail: { error: { code: "INVALID_PDF", message: "Not a valid PDF." } },
    });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.code).toBe("INVALID_PDF");
    expect(err.message).toBe("Not a valid PDF.");
    expect(err.detail).toEqual({
      error: { code: "INVALID_PDF", message: "Not a valid PDF." },
    });
  });

  // (a) Quality-review gap from #282: plain detail object {detail:{code,message}}
  // with NO nested `error`.
  it("unwraps a plain detail object {detail:{code,message}} with no nested error", () => {
    const err = buildApiError(404, {
      detail: { code: "NOT_FOUND", message: "Paper not found." },
    });
    expect(err.status).toBe(404);
    expect(err.code).toBe("NOT_FOUND");
    expect(err.message).toBe("Paper not found.");
    expect(err.detail).toEqual({ code: "NOT_FOUND", message: "Paper not found." });
  });

  it("synthesizes a message from a Pydantic array detail (code undefined)", () => {
    const err = buildApiError(422, {
      detail: [
        { loc: ["body", "doi"], msg: "field required", type: "value_error.missing" },
      ],
    });
    expect(err.status).toBe(422);
    expect(err.code).toBeUndefined();
    expect(err.message).toContain("field required");
    expect(err.detail).toEqual([
      { loc: ["body", "doi"], msg: "field required", type: "value_error.missing" },
    ]);
  });

  it("uses a string detail directly as the message", () => {
    const err = buildApiError(503, { detail: "Queue unavailable, retry shortly." });
    expect(err.status).toBe(503);
    expect(err.code).toBeUndefined();
    expect(err.message).toBe("Queue unavailable, retry shortly.");
  });

  // analyses.ts divergence (issue #283): the core path threw
  // `{ status, ...(body.error ?? body.detail ?? body) }`, surfacing a TOP-LEVEL
  // `body.error.{code,message}`. The shared helper must preserve that so
  // createAnalysis keeps reading `.message`.
  it("unwraps a TOP-LEVEL {error:{code,message}} with no detail (analyses path)", () => {
    const err = buildApiError(400, {
      error: { code: "LIMIT", message: "File too large" },
    });
    expect(err.status).toBe(400);
    expect(err.code).toBe("LIMIT");
    expect(err.message).toBe("File too large");
  });

  // (b) Quality-review gap from #282: no-detail top-level {code,message}.
  it("falls back to a top-level {code,message} when there is no detail/error", () => {
    const err = buildApiError(409, { code: "DUPLICATE", message: "Dup." });
    expect(err.status).toBe(409);
    expect(err.code).toBe("DUPLICATE");
    expect(err.message).toBe("Dup.");
  });

  it("falls back to a safe message on an empty/unparseable body", () => {
    const err = buildApiError(500, {});
    expect(err.status).toBe(500);
    expect(typeof err.message).toBe("string");
    expect(err.message.length).toBeGreaterThan(0);
    expect(err.message).not.toMatch(/\[object Object\]/);
  });

  // Issue #294: per-surface fallback override. Modules migrating off the bare
  // `new Error("Failed to fetch X")` idiom must preserve their exact
  // user-facing fallback string when the body yields no usable message. The
  // optional third arg replaces the generic `Request failed (HTTP N).` default.
  describe("fallback override (issue #294)", () => {
    it("uses the provided fallback when the body has no usable message", () => {
      const err = buildApiError(500, {}, "Failed to fetch consent status");
      expect(err.status).toBe(500);
      expect(err.message).toBe("Failed to fetch consent status");
    });

    it("uses the provided fallback for a non-object body", () => {
      const err = buildApiError(503, "boom", "Failed to grant consent");
      expect(err.status).toBe(503);
      expect(err.message).toBe("Failed to grant consent");
    });

    it("prefers a real body message over the fallback override", () => {
      const err = buildApiError(
        404,
        { detail: "Not found" },
        "Failed to fetch status",
      );
      expect(err.message).toBe("Not found");
    });

    it("prefers a top-level error.message over the fallback override", () => {
      const err = buildApiError(
        400,
        { error: { code: "LIMIT", message: "File too large" } },
        "Failed to start analysis",
      );
      expect(err.message).toBe("File too large");
      expect(err.code).toBe("LIMIT");
    });

    it("retains the generic fallback when no override is supplied", () => {
      const err = buildApiError(500, {});
      expect(err.message).toBe("Request failed (HTTP 500).");
    });
  });
});
