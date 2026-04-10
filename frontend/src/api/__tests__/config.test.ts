/**
 * API config — unit tests
 * TDD gate: API_BASE is exported from a single shared module and resolves correctly.
 * Requirements: B-083 (refactor — extract shared API_BASE constant)
 */

import { describe, it, expect } from "vitest";
import { API_BASE } from "@/api/config";

describe("API_BASE", () => {
  it("is a non-empty string", () => {
    expect(typeof API_BASE).toBe("string");
    expect(API_BASE.length).toBeGreaterThan(0);
  });

  it("falls back to localhost:8000 when VITE_API_URL is not set", () => {
    // In test environment import.meta.env.VITE_API_URL is undefined,
    // so API_BASE must default to the localhost URL.
    expect(API_BASE).toBe("http://localhost:8000");
  });

  it("does not include a trailing slash", () => {
    expect(API_BASE.endsWith("/")).toBe(false);
  });
});
