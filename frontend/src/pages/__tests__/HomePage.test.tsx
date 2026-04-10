import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

// Mock supabase before importing the component
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
    },
  },
}));

// Mock react-router's useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import { supabase } from "@/lib/supabase";
import HomePage from "@/pages/HomePage";

const mockGetSession = supabase.auth.getSession as ReturnType<typeof vi.fn>;

describe("HomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state before session resolves", () => {
    // Never-resolving promise keeps it in loading state
    mockGetSession.mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders the Spelix heading when user is not authenticated", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /spelix/i })).toBeInTheDocument();
    });
  });

  it("renders tagline when user is not authenticated", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/science-based barbell form coaching/i),
      ).toBeInTheDocument();
    });
  });

  it("renders Sign in link pointing to /login", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const signInLink = screen.getByRole("link", { name: /sign in/i });
      expect(signInLink).toBeInTheDocument();
      expect(signInLink).toHaveAttribute("href", "/login");
    });
  });

  it("renders Create account link pointing to /signup", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const createLink = screen.getByRole("link", { name: /create account/i });
      expect(createLink).toBeInTheDocument();
      expect(createLink).toHaveAttribute("href", "/signup");
    });
  });

  it("navigates to /upload when user is already authenticated", async () => {
    mockGetSession.mockResolvedValue({
      data: {
        session: {
          user: { id: "user-1", email: "user@example.com" },
          access_token: "tok",
        },
      },
      error: null,
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/upload", { replace: true });
    });
  });
});
