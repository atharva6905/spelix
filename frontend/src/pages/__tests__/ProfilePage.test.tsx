import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import ProfilePage from "@/pages/ProfilePage";

// Mock the profiles API module
vi.mock("@/api/profiles", () => ({
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

// Mock supabase
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

import { getProfile } from "@/api/profiles";

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no existing profile (404)
    vi.mocked(getProfile).mockRejectedValue({ status: 404 });
  });

  function renderPage() {
    return render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
  }

  it("renders height field", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/height/i)).toBeInTheDocument();
    });
  });

  it("renders weight field", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/weight/i)).toBeInTheDocument();
    });
  });

  it("renders age field", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/age/i)).toBeInTheDocument();
    });
  });

  it("renders experience level field", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/experience level/i)).toBeInTheDocument();
    });
  });

  it("renders save button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    });
  });

  it("renders experience level options", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/beginner/i)).toBeInTheDocument();
      expect(screen.getByText(/intermediate/i)).toBeInTheDocument();
      expect(screen.getByText(/advanced/i)).toBeInTheDocument();
    });
  });

  it("pre-populates form when profile exists", async () => {
    vi.mocked(getProfile).mockResolvedValue({
      id: "uuid-1",
      user_id: "user-uuid",
      height_cm: 180,
      weight_kg: 82,
      age: 30,
      experience_level: "intermediate",
      arm_span_cm: null,
      femur_length_cm: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/height/i)).toHaveValue(180);
      expect(screen.getByLabelText(/weight/i)).toHaveValue(82);
      expect(screen.getByLabelText(/age/i)).toHaveValue(30);
    });
  });

  it("renders optional arm span field", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/arm span/i)).toBeInTheDocument();
    });
  });

  it("renders optional femur length field", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/femur length/i)).toBeInTheDocument();
    });
  });
});
