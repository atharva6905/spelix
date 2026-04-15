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
  submitBetaRequest: vi.fn(),
}));

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
      expect(
        screen.getByRole("heading", {
          level: 1,
          name: /barbell form coaching where every piece of feedback cites its source/i,
        }),
      ).toBeInTheDocument();
    });

    // Problem section
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /you've watched yourself lift/i,
      }),
    ).toBeInTheDocument();

    // HowItWorks section
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /three steps, one lift at a time/i,
      }),
    ).toBeInTheDocument();

    // Differentiators section
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /three things no other app does/i,
      }),
    ).toBeInTheDocument();

    // Privacy section
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /what spelix does with your video/i,
      }),
    ).toBeInTheDocument();

    // FinalCta section
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /you have filmed your lifts/i,
      }),
    ).toBeInTheDocument();

    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
