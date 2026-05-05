import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useConsent } from "@/hooks/useConsent";

// Mock the consent API module
const mockGetConsents = vi.fn();
const mockGrantConsent = vi.fn();
const mockWithdrawConsent = vi.fn();

vi.mock("@/api/consent", () => ({
  getConsents: (...args: unknown[]) => mockGetConsents(...args),
  grantConsent: (...args: unknown[]) => mockGrantConsent(...args),
  withdrawConsent: (...args: unknown[]) => mockWithdrawConsent(...args),
}));

const CONSENT_FIXTURE = [
  {
    consent_type: "analytics" as const,
    granted: true,
    granted_at: "2026-01-01T00:00:00Z",
    withdrawn_at: null,
    consent_version: "1.0",
  },
  {
    consent_type: "health_data_processing" as const,
    granted: false,
    granted_at: null,
    withdrawn_at: null,
    consent_version: "1.0",
  },
];

describe("useConsent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Initial load
  // -------------------------------------------------------------------------
  it("starts with isLoading=true and empty consents", () => {
    mockGetConsents.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useConsent());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.consents).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it("loads consents on mount", async () => {
    mockGetConsents.mockResolvedValue(CONSENT_FIXTURE);

    const { result } = renderHook(() => useConsent());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.consents).toHaveLength(2);
    expect(result.current.consents[0].consent_type).toBe("analytics");
    expect(result.current.error).toBeNull();
  });

  it("sets error when getConsents throws an Error instance", async () => {
    mockGetConsents.mockRejectedValue(new Error("Failed to load consent status"));

    const { result } = renderHook(() => useConsent());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe("Failed to load consent status");
    expect(result.current.consents).toEqual([]);
  });

  it("sets fallback error message when non-Error is thrown", async () => {
    mockGetConsents.mockRejectedValue("some string error");

    const { result } = renderHook(() => useConsent());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe("Failed to load consent status");
  });

  it("does not set state after unmount (cancelled)", async () => {
    let resolveGets!: (val: unknown) => void;
    const pending = new Promise((res) => { resolveGets = res; });
    mockGetConsents.mockReturnValue(pending);

    const { result, unmount } = renderHook(() => useConsent());

    // Unmount before the fetch resolves
    unmount();

    // Now resolve — should not throw or update state
    await act(async () => {
      resolveGets(CONSENT_FIXTURE);
      await Promise.resolve();
    });

    // State should still be the initial values (not updated after unmount)
    expect(result.current.consents).toEqual([]);
  });

  // -------------------------------------------------------------------------
  // grant()
  // -------------------------------------------------------------------------
  it("grant calls grantConsent then refreshes consents", async () => {
    mockGetConsents.mockResolvedValue(CONSENT_FIXTURE);
    mockGrantConsent.mockResolvedValue(CONSENT_FIXTURE[0]);

    const updatedConsents = [
      { ...CONSENT_FIXTURE[0], granted: true },
      { ...CONSENT_FIXTURE[1], granted: true },
    ];
    // Second call returns updated list
    mockGetConsents
      .mockResolvedValueOnce(CONSENT_FIXTURE)
      .mockResolvedValueOnce(updatedConsents);

    const { result } = renderHook(() => useConsent());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.grant("health_data_processing", "1.0");
    });

    expect(mockGrantConsent).toHaveBeenCalledWith("health_data_processing", "1.0");
    expect(mockGetConsents).toHaveBeenCalledTimes(2);
    expect(result.current.consents[1].granted).toBe(true);
  });

  it("grant clears previous error before calling API", async () => {
    mockGetConsents.mockRejectedValueOnce(new Error("Initial error"));
    mockGetConsents.mockResolvedValueOnce(CONSENT_FIXTURE);
    mockGrantConsent.mockResolvedValue(CONSENT_FIXTURE[0]);

    const { result } = renderHook(() => useConsent());

    await waitFor(() => {
      expect(result.current.error).toBe("Initial error");
    });

    await act(async () => {
      await result.current.grant("analytics", "1.0");
    });

    expect(result.current.error).toBeNull();
  });

  // -------------------------------------------------------------------------
  // withdraw()
  // -------------------------------------------------------------------------
  it("withdraw calls withdrawConsent then refreshes consents", async () => {
    const updatedConsents = [
      { ...CONSENT_FIXTURE[0], granted: false, withdrawn_at: "2026-05-01T00:00:00Z" },
      CONSENT_FIXTURE[1],
    ];
    mockGetConsents
      .mockResolvedValueOnce(CONSENT_FIXTURE)
      .mockResolvedValueOnce(updatedConsents);
    mockWithdrawConsent.mockResolvedValue({
      ...CONSENT_FIXTURE[0],
      granted: false,
      withdrawn_at: "2026-05-01T00:00:00Z",
    });

    const { result } = renderHook(() => useConsent());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.withdraw("analytics");
    });

    expect(mockWithdrawConsent).toHaveBeenCalledWith("analytics");
    expect(mockGetConsents).toHaveBeenCalledTimes(2);
    expect(result.current.consents[0].granted).toBe(false);
  });

  it("withdraw clears previous error before calling API", async () => {
    mockGetConsents.mockRejectedValueOnce(new Error("Load error"));
    mockGetConsents.mockResolvedValueOnce(CONSENT_FIXTURE);
    mockWithdrawConsent.mockResolvedValue({ ...CONSENT_FIXTURE[0], granted: false });

    const { result } = renderHook(() => useConsent());

    await waitFor(() => {
      expect(result.current.error).toBe("Load error");
    });

    await act(async () => {
      await result.current.withdraw("analytics");
    });

    expect(result.current.error).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Return shape
  // -------------------------------------------------------------------------
  it("exposes grant and withdraw functions", async () => {
    mockGetConsents.mockResolvedValue(CONSENT_FIXTURE);

    const { result } = renderHook(() => useConsent());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(typeof result.current.grant).toBe("function");
    expect(typeof result.current.withdraw).toBe("function");
  });
});
