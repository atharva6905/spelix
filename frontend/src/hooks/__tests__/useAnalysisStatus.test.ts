/**
 * Unit tests for STATUS_LABELS in useAnalysisStatus.
 *
 * B-049: Verify that quality_gate_pending and quality_gate_rejected labels
 * match SRS Appendix B canonical values.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

// Mock Supabase client — never connect to real Supabase in unit tests.
// Expose captured subscribe callback so tests can simulate channel state.
const channelState: {
  subscribeCallback: ((status: string) => void) | null;
  updateCallback: ((payload: { new: unknown }) => void) | null;
  unsubscribe: ReturnType<typeof vi.fn>;
} = {
  subscribeCallback: null,
  updateCallback: null,
  unsubscribe: vi.fn(),
};

vi.mock("@/lib/supabase", () => ({
  supabase: {
    channel: vi.fn(() => {
      const chan = {
        on: vi.fn((_event: string, _filter: unknown, cb: typeof channelState.updateCallback) => {
          channelState.updateCallback = cb;
          return chan;
        }),
        subscribe: vi.fn((cb: typeof channelState.subscribeCallback) => {
          channelState.subscribeCallback = cb;
          return chan;
        }),
        unsubscribe: channelState.unsubscribe,
      };
      return chan;
    }),
    removeChannel: vi.fn(),
  },
}));

vi.mock("@/api/analyses", () => ({
  getAnalysisStatus: vi.fn(),
}));

import { STATUS_LABELS, useAnalysisStatus } from "../useAnalysisStatus";
import { getAnalysisStatus } from "@/api/analyses";

const mockGetAnalysisStatus = getAnalysisStatus as ReturnType<typeof vi.fn>;

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

describe("useAnalysisStatus reconnecting indicator (D-028)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    channelState.subscribeCallback = null;
    channelState.updateCallback = null;
    channelState.unsubscribe = vi.fn();
  });

  it("does NOT set isReconnecting=true after intentional unsubscribe on terminal status", async () => {
    // Initial status fetch returns a terminal status → hook calls channel.unsubscribe()
    mockGetAnalysisStatus.mockResolvedValue({
      id: "a1",
      status: "completed",
      updated_at: "2026-04-16T00:00:00Z",
      detection_result: null,
      quality_gate_result: null,
      retry_count: 0,
    });

    const { result } = renderHook(() => useAnalysisStatus("a1"));

    // Wait for the initial fetch to settle and the terminal-status unsubscribe to run
    await waitFor(() => {
      expect(result.current.status).toBe("completed");
    });

    // Simulate Supabase firing the subscribe callback with CLOSED after the
    // hook's intentional unsubscribe (this is what Supabase actually does).
    expect(channelState.subscribeCallback).not.toBeNull();
    await act(async () => {
      channelState.subscribeCallback!("CLOSED");
    });

    // D-028: the banner must stay hidden — the analysis is already complete,
    // nothing to reconnect to.
    expect(result.current.isReconnecting).toBe(false);
  });

  it("sets isReconnecting=true on unsolicited CHANNEL_ERROR (pre-terminal)", async () => {
    mockGetAnalysisStatus.mockResolvedValue({
      id: "a2",
      status: "processing",
      updated_at: "2026-04-16T00:00:00Z",
      detection_result: null,
      quality_gate_result: null,
      retry_count: 0,
    });

    const { result } = renderHook(() => useAnalysisStatus("a2"));

    await waitFor(() => {
      expect(result.current.status).toBe("processing");
    });

    // Unsolicited disconnect — no intentional unsubscribe happened first.
    await act(async () => {
      channelState.subscribeCallback!("CHANNEL_ERROR");
    });

    expect(result.current.isReconnecting).toBe(true);
  });

  it("resets intentional-unsubscribe flag when analysisId changes", async () => {
    // First render: terminal status → intentional unsubscribe sets the flag
    mockGetAnalysisStatus.mockResolvedValueOnce({
      id: "a1",
      status: "completed",
      updated_at: "2026-04-16T00:00:00Z",
      detection_result: null,
      quality_gate_result: null,
      retry_count: 0,
    });

    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useAnalysisStatus(id),
      { initialProps: { id: "a1" } },
    );

    await waitFor(() => {
      expect(result.current.status).toBe("completed");
    });

    // Switch to a new, non-terminal analysis
    mockGetAnalysisStatus.mockResolvedValueOnce({
      id: "a2",
      status: "processing",
      updated_at: "2026-04-16T00:01:00Z",
      detection_result: null,
      quality_gate_result: null,
      retry_count: 0,
    });
    rerender({ id: "a2" });

    await waitFor(() => {
      expect(result.current.status).toBe("processing");
    });

    // A real disconnect on the new analysis MUST surface the banner — the
    // intentional-unsubscribe flag from the previous analysis must not leak.
    await act(async () => {
      channelState.subscribeCallback!("CHANNEL_ERROR");
    });

    expect(result.current.isReconnecting).toBe(true);
  });
});
