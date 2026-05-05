import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
    },
  },
}));

vi.mock("@/api/beta", () => ({
  requestBetaAccess: vi.fn(),
}));

vi.mock("@/lib/posthog", () => ({ capture: vi.fn() }));

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate };
});

import { supabase } from "@/lib/supabase";
import LandingPage from "@/pages/LandingPage";

const mockGetSession = supabase.auth.getSession as ReturnType<typeof vi.fn>;

describe("LandingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects authenticated users to /upload", async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { user: { id: "u1" } } },
      error: null,
    });

    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/upload", { replace: true });
    });
  });

  it("renders full landing page for anonymous visitors", async () => {
    mockGetSession.mockResolvedValue({
      data: { session: null },
      error: null,
    });

    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Every rep,")).toBeInTheDocument();
    });

    expect(screen.getByText("01 / Problem")).toBeInTheDocument();
    expect(screen.getByText("02 / Process")).toBeInTheDocument();
    expect(screen.getByText("03 / Report")).toBeInTheDocument();
    expect(screen.getByText("04 / The Science Layer")).toBeInTheDocument();
    expect(screen.getByText("05 / Your Data")).toBeInTheDocument();
    expect(screen.getByText("© 2026 Spelix")).toBeInTheDocument();

    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
