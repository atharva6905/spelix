/**
 * Tests for ConsentPage — FR-BRAIN-11
 *
 * TDD gates:
 *   - test_consent_page_renders_three_tiers
 *   - test_tier3_toggle_optional
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import ConsentPage from "@/pages/ConsentPage";

// Mock the useConsent hook
vi.mock("@/hooks/useConsent", () => ({
  useConsent: vi.fn(),
}));

// Mock supabase (referenced transitively)
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

import { useConsent } from "@/hooks/useConsent";

const mockUseConsent = useConsent as ReturnType<typeof vi.fn>;

const EMPTY_CONSENTS = {
  consents: [],
  isLoading: false,
  error: null,
  grant: vi.fn(),
  withdraw: vi.fn(),
};

const GRANTED_CONSENTS = {
  consents: [
    {
      consent_type: "analytics" as const,
      granted: true,
      granted_at: "2026-04-12T00:00:00Z",
      withdrawn_at: null,
      consent_version: "1.0",
    },
    {
      consent_type: "health_data_processing" as const,
      granted: true,
      granted_at: "2026-04-12T00:00:00Z",
      withdrawn_at: null,
      consent_version: "1.0",
    },
    {
      consent_type: "coach_brain_contribution" as const,
      granted: false,
      granted_at: null,
      withdrawn_at: "2026-04-12T00:00:00Z",
      consent_version: "1.0",
    },
  ],
  isLoading: false,
  error: null,
  grant: vi.fn(),
  withdraw: vi.fn(),
};

function renderPage() {
  return render(
    <MemoryRouter>
      <ConsentPage />
    </MemoryRouter>,
  );
}

describe("ConsentPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseConsent.mockReturnValue(EMPTY_CONSENTS);
  });

  // TDD gate: test_consent_page_renders_three_tiers
  it("renders three consent tier cards", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("consent-tier-1")).toBeInTheDocument();
      expect(screen.getByTestId("consent-tier-2")).toBeInTheDocument();
      expect(screen.getByTestId("consent-tier-3")).toBeInTheDocument();
    });
  });

  it("renders tier titles", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Service Analytics")).toBeInTheDocument();
      expect(screen.getByText("Health Data Processing")).toBeInTheDocument();
      expect(screen.getByText("Coach Brain Contribution")).toBeInTheDocument();
    });
  });

  // TDD gate: test_tier3_toggle_optional
  it("marks Tier 3 as optional and Tiers 1 and 2 as not optional", async () => {
    renderPage();
    await waitFor(() => {
      // Only one "Optional" badge should appear — for Tier 3
      const optionalBadges = screen.getAllByText("Optional");
      expect(optionalBadges).toHaveLength(1);
      // The optional badge is inside tier-3
      const tier3 = screen.getByTestId("consent-tier-3");
      expect(tier3).toHaveTextContent("Optional");
    });
  });

  it("shows loading state while fetching", () => {
    mockUseConsent.mockReturnValue({ ...EMPTY_CONSENTS, isLoading: true });
    renderPage();
    expect(screen.getByText(/loading consent status/i)).toBeInTheDocument();
  });

  it("shows error message when fetch fails", async () => {
    mockUseConsent.mockReturnValue({
      ...EMPTY_CONSENTS,
      error: "Failed to load consent status",
    });
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("Failed to load consent status"),
      ).toBeInTheDocument();
    });
  });

  it("shows 'Not granted' badges when consents are empty", async () => {
    renderPage();
    await waitFor(() => {
      const notGrantedBadges = screen.getAllByText("Not granted");
      expect(notGrantedBadges).toHaveLength(3);
    });
  });

  it("shows 'Granted' badges for granted consents", async () => {
    mockUseConsent.mockReturnValue(GRANTED_CONSENTS);
    renderPage();
    await waitFor(() => {
      const grantedBadges = screen.getAllByText("Granted");
      expect(grantedBadges).toHaveLength(2); // analytics + health_data_processing
      const notGrantedBadges = screen.getAllByText("Not granted");
      expect(notGrantedBadges).toHaveLength(1); // coach_brain_contribution
    });
  });

  it("shows grant button when consent not granted", async () => {
    renderPage();
    await waitFor(() => {
      const grantButtons = screen.getAllByRole("button", {
        name: /grant consent/i,
      });
      expect(grantButtons).toHaveLength(3);
    });
  });

  it("shows withdraw button when consent is granted", async () => {
    mockUseConsent.mockReturnValue(GRANTED_CONSENTS);
    renderPage();
    await waitFor(() => {
      const withdrawButtons = screen.getAllByRole("button", {
        name: /withdraw consent/i,
      });
      expect(withdrawButtons).toHaveLength(2); // analytics + health_data_processing
    });
  });

  it("calls grant with correct type and version when grant button clicked", async () => {
    const mockGrant = vi.fn().mockResolvedValue(undefined);
    mockUseConsent.mockReturnValue({ ...EMPTY_CONSENTS, grant: mockGrant });

    renderPage();

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /grant consent/i })).toHaveLength(3);
    });

    // Click the first grant button (Tier 1 — analytics)
    const grantButtons = screen.getAllByRole("button", { name: /grant consent/i });
    fireEvent.click(grantButtons[0]);

    await waitFor(() => {
      expect(mockGrant).toHaveBeenCalledWith("analytics", "1.0");
    });
  });

  it("calls withdraw with correct type when withdraw button clicked", async () => {
    const mockWithdraw = vi.fn().mockResolvedValue(undefined);
    mockUseConsent.mockReturnValue({
      ...GRANTED_CONSENTS,
      withdraw: mockWithdraw,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /withdraw consent/i })).toHaveLength(2);
    });

    const withdrawButtons = screen.getAllByRole("button", { name: /withdraw consent/i });
    fireEvent.click(withdrawButtons[0]);

    await waitFor(() => {
      expect(mockWithdraw).toHaveBeenCalledWith("analytics");
    });
  });

  it("renders page heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /data & privacy consent/i })).toBeInTheDocument();
    });
  });
});
