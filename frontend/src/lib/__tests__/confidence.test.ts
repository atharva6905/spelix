import { describe, it, expect } from "vitest";
import { getConfidenceCategory } from "@/lib/confidence";

describe("getConfidenceCategory", () => {
  it("returns High for exactly 0.80", () => {
    expect(getConfidenceCategory(0.80)).toBe("High");
  });

  it("returns High for scores above 0.80", () => {
    expect(getConfidenceCategory(0.95)).toBe("High");
    expect(getConfidenceCategory(1.0)).toBe("High");
  });

  it("returns Moderate for 0.79 (just below High threshold)", () => {
    expect(getConfidenceCategory(0.79)).toBe("Moderate");
  });

  it("returns Moderate for exactly 0.65", () => {
    expect(getConfidenceCategory(0.65)).toBe("Moderate");
  });

  it("returns Low for 0.64 (just below Moderate threshold)", () => {
    expect(getConfidenceCategory(0.64)).toBe("Low");
  });

  it("returns Low for exactly 0.50", () => {
    expect(getConfidenceCategory(0.50)).toBe("Low");
  });

  it("returns Very Low for 0.49 (just below Low threshold)", () => {
    expect(getConfidenceCategory(0.49)).toBe("Very Low");
  });

  it("returns Very Low for 0.0", () => {
    expect(getConfidenceCategory(0.0)).toBe("Very Low");
  });
});
