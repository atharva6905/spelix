/**
 * Unit tests for useAnalysisDetail hook.
 *
 * Tests: fetch on mount, loading state, error handling,
 * cancellation on unmount, and no-op when id is empty.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

// Mock API module before importing the hook
vi.mock("@/api/analyses", () => ({
  getAnalysisDetail: vi.fn(),
}));

import { getAnalysisDetail } from "@/api/analyses";
import { useAnalysisDetail } from "../useAnalysisDetail";
import type { AnalysisDetail } from "@/api/analyses";

const mockGetAnalysisDetail = getAnalysisDetail as ReturnType<typeof vi.fn>;

const MOCK_ANALYSIS: AnalysisDetail = {
  id: "analysis-abc",
  status: "completed",
  exercise_type: "squat",
  exercise_variant: "high_bar",
  confidence_score: 0.87,
  created_at: "2026-04-10T00:00:00Z",
  updated_at: "2026-04-10T00:01:00Z",
  quality_gate_result: null,
  annotated_video_path: null,
  video_path: null,
  plot_path: null,
  pdf_path: null,
  tags: null,
  summary_json: null,
  coaching_result: null,
  rep_metrics: [],
};

describe("useAnalysisDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts in loading state", () => {
    mockGetAnalysisDetail.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useAnalysisDetail("analysis-abc"));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.analysis).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("returns analysis data on successful fetch", async () => {
    mockGetAnalysisDetail.mockResolvedValue(MOCK_ANALYSIS);

    const { result } = renderHook(() => useAnalysisDetail("analysis-abc"));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.analysis).toEqual(MOCK_ANALYSIS);
    expect(result.current.error).toBeNull();
  });

  it("sets error string on fetch failure", async () => {
    mockGetAnalysisDetail.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useAnalysisDetail("analysis-abc"));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe("Network error");
    expect(result.current.analysis).toBeNull();
  });

  it("passes through a thrown string directly as the error message", async () => {
    mockGetAnalysisDetail.mockRejectedValue("plain string error");

    const { result } = renderHook(() => useAnalysisDetail("analysis-abc"));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe("plain string error");
  });

  it("uses fallback error message when error is a plain object (not Error or string)", async () => {
    mockGetAnalysisDetail.mockRejectedValue({ code: "OOPS" });

    const { result } = renderHook(() => useAnalysisDetail("analysis-abc"));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe("Failed to load analysis");
  });

  it("calls getAnalysisDetail with the provided id", async () => {
    mockGetAnalysisDetail.mockResolvedValue(MOCK_ANALYSIS);

    renderHook(() => useAnalysisDetail("analysis-xyz"));

    await waitFor(() => {
      expect(mockGetAnalysisDetail).toHaveBeenCalledWith("analysis-xyz");
    });
  });

  it("does not fetch when id is empty string", () => {
    renderHook(() => useAnalysisDetail(""));

    expect(mockGetAnalysisDetail).not.toHaveBeenCalled();
  });

  it("re-fetches when id changes", async () => {
    mockGetAnalysisDetail.mockResolvedValue(MOCK_ANALYSIS);

    const { rerender } = renderHook(({ id }: { id: string }) => useAnalysisDetail(id), {
      initialProps: { id: "analysis-1" },
    });

    await waitFor(() => {
      expect(mockGetAnalysisDetail).toHaveBeenCalledWith("analysis-1");
    });

    rerender({ id: "analysis-2" });

    await waitFor(() => {
      expect(mockGetAnalysisDetail).toHaveBeenCalledWith("analysis-2");
    });

    expect(mockGetAnalysisDetail).toHaveBeenCalledTimes(2);
  });

  it("does not update state after unmount (cancellation)", async () => {
    let resolveFn!: (val: AnalysisDetail) => void;
    const pending = new Promise<AnalysisDetail>((res) => { resolveFn = res; });
    mockGetAnalysisDetail.mockReturnValue(pending);

    const { unmount, result } = renderHook(() => useAnalysisDetail("analysis-abc"));

    // Unmount before fetch resolves
    unmount();

    // Resolve after unmount — should not throw or update state
    resolveFn(MOCK_ANALYSIS);
    await Promise.resolve();

    // State should remain null (cancelled)
    expect(result.current.analysis).toBeNull();
  });

  it("does not set error after unmount (cancellation on failure)", async () => {
    let rejectFn!: (err: Error) => void;
    const pending = new Promise<AnalysisDetail>((_res, rej) => { rejectFn = rej; });
    mockGetAnalysisDetail.mockReturnValue(pending);

    const { unmount, result } = renderHook(() => useAnalysisDetail("analysis-abc"));

    // Unmount before fetch rejects
    unmount();

    // Reject after unmount — should not throw
    rejectFn(new Error("Network error"));
    await Promise.resolve();

    // Error should remain null (cancelled)
    expect(result.current.error).toBeNull();
  });
});
