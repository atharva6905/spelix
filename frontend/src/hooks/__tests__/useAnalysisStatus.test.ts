/**
 * Unit tests for STATUS_LABELS in useAnalysisStatus.
 *
 * B-049: Verify that quality_gate_pending and quality_gate_rejected labels
 * match SRS Appendix B canonical values.
 */

import { describe, it, expect, vi } from "vitest";

// Mock Supabase client — never connect to real Supabase in unit tests
vi.mock("@/lib/supabase", () => ({
  supabase: {
    channel: vi.fn().mockReturnValue({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
    }),
    removeChannel: vi.fn(),
  },
}));

// Mock API module — not needed for label tests but required for module load
vi.mock("@/api/analyses", () => ({
  getAnalysisStatus: vi.fn(),
}));

import { STATUS_LABELS } from "../useAnalysisStatus";

describe("STATUS_LABELS (SRS Appendix B)", () => {
  it('maps quality_gate_pending to "Preparing to analyse…"', () => {
    expect(STATUS_LABELS.quality_gate_pending).toBe("Preparing to analyse…");
  });

  it('maps quality_gate_rejected to "Video could not be processed"', () => {
    expect(STATUS_LABELS.quality_gate_rejected).toBe(
      "Video could not be processed",
    );
  });

  it('maps queued to "Preparing to analyse…"', () => {
    expect(STATUS_LABELS.queued).toBe("Preparing to analyse…");
  });

  it('maps processing to "Analysing your form…"', () => {
    expect(STATUS_LABELS.processing).toBe("Analysing your form…");
  });

  it('maps coaching to "Generating coaching feedback…"', () => {
    expect(STATUS_LABELS.coaching).toBe("Generating coaching feedback…");
  });

  it('maps completed to "Analysis complete"', () => {
    expect(STATUS_LABELS.completed).toBe("Analysis complete");
  });

  it('maps failed to "Analysis failed"', () => {
    expect(STATUS_LABELS.failed).toBe("Analysis failed");
  });

  it("covers all 7 analysis statuses", () => {
    const expectedStatuses = [
      "queued",
      "quality_gate_pending",
      "quality_gate_rejected",
      "processing",
      "coaching",
      "completed",
      "failed",
    ];
    for (const status of expectedStatuses) {
      expect(STATUS_LABELS).toHaveProperty(status);
    }
  });
});
