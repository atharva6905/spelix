import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import ProfilePage from "@/pages/ProfilePage";

// Mock the profiles API module
const mockGetProfile = vi.fn();
const mockUpdateProfile = vi.fn();

vi.mock("@/api/profiles", () => ({
  getProfile: (...args: unknown[]) => mockGetProfile(...args),
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...args),
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

const PROFILE_FIXTURE = {
  id: "uuid-1",
  user_id: "user-uuid",
  height_cm: 180,
  weight_kg: 82,
  age: 30,
  experience_level: "intermediate",
  arm_span_cm: 185,
  femur_length_cm: 47,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no existing profile (404)
    mockGetProfile.mockRejectedValue({ status: 404 });
  });

  function renderPage() {
    return render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
  }

  // -------------------------------------------------------------------------
  // Basic render tests
  // -------------------------------------------------------------------------
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

  // -------------------------------------------------------------------------
  // Profile loading
  // -------------------------------------------------------------------------
  it("shows loading state initially", () => {
    mockGetProfile.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/loading profile/i)).toBeInTheDocument();
  });

  it("pre-populates form when profile exists", async () => {
    mockGetProfile.mockResolvedValue(PROFILE_FIXTURE);

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/height/i)).toHaveValue(180);
      expect(screen.getByLabelText(/weight/i)).toHaveValue(82);
      expect(screen.getByLabelText(/age/i)).toHaveValue(30);
    });
  });

  it("pre-populates arm span and femur length when present", async () => {
    mockGetProfile.mockResolvedValue(PROFILE_FIXTURE);

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/arm span/i)).toHaveValue(185);
      expect(screen.getByLabelText(/femur length/i)).toHaveValue(47);
    });
  });

  it("leaves optional fields empty when null in profile", async () => {
    mockGetProfile.mockResolvedValue({
      ...PROFILE_FIXTURE,
      arm_span_cm: null,
      femur_length_cm: null,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/arm span/i)).toHaveValue(null);
      expect(screen.getByLabelText(/femur length/i)).toHaveValue(null);
    });
  });

  it("silently ignores 404 when no profile exists yet", async () => {
    mockGetProfile.mockRejectedValue({ status: 404 });

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    });
    // Should not display any error message for 404
    expect(screen.queryByText(/failed/i)).not.toBeInTheDocument();
  });

  it("logs error for non-404 load failure", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockGetProfile.mockRejectedValue({ status: 500, message: "Server error" });

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    });
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  // -------------------------------------------------------------------------
  // Form validation
  // -------------------------------------------------------------------------
  it("shows error when height is empty", async () => {
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /save/i }));

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/valid height/i)).toBeInTheDocument();
    });
  });

  it("shows error when height is zero", async () => {
    renderPage();
    await waitFor(() => screen.getByLabelText(/height/i));

    fireEvent.change(screen.getByLabelText(/height/i), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/valid height/i)).toBeInTheDocument();
    });
  });

  it("shows error when weight is empty", async () => {
    renderPage();
    await waitFor(() => screen.getByLabelText(/height/i));

    fireEvent.change(screen.getByLabelText(/height/i), { target: { value: "175" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/valid weight/i)).toBeInTheDocument();
    });
  });

  it("shows error when weight is zero", async () => {
    renderPage();
    await waitFor(() => screen.getByLabelText(/height/i));

    fireEvent.change(screen.getByLabelText(/height/i), { target: { value: "175" } });
    fireEvent.change(screen.getByLabelText(/weight/i), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/valid weight/i)).toBeInTheDocument();
    });
  });

  it("shows error when age is empty", async () => {
    renderPage();
    await waitFor(() => screen.getByLabelText(/height/i));

    fireEvent.change(screen.getByLabelText(/height/i), { target: { value: "175" } });
    fireEvent.change(screen.getByLabelText(/weight/i), { target: { value: "80" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/valid age/i)).toBeInTheDocument();
    });
  });

  it("shows error when experience level is not selected", async () => {
    renderPage();
    await waitFor(() => screen.getByLabelText(/height/i));

    fireEvent.change(screen.getByLabelText(/height/i), { target: { value: "175" } });
    fireEvent.change(screen.getByLabelText(/weight/i), { target: { value: "80" } });
    fireEvent.change(screen.getByLabelText(/age/i), { target: { value: "28" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/please select an experience level/i)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Save (success & error)
  // -------------------------------------------------------------------------
  it("shows saving state while updating profile", async () => {
    mockGetProfile.mockResolvedValue(PROFILE_FIXTURE);
    let resolveFn!: (val: unknown) => void;
    const pending = new Promise((res) => { resolveFn = res; });
    mockUpdateProfile.mockReturnValue(pending);

    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /save/i }));

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled();
    });

    // Cleanup
    resolveFn(PROFILE_FIXTURE);
  });

  it("shows success message after successful save", async () => {
    mockGetProfile.mockResolvedValue(PROFILE_FIXTURE);
    mockUpdateProfile.mockResolvedValue(PROFILE_FIXTURE);

    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /save/i }));

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/profile saved/i)).toBeInTheDocument();
    });
  });

  it("shows error message when save fails", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockGetProfile.mockResolvedValue(PROFILE_FIXTURE);
    mockUpdateProfile.mockRejectedValue(new Error("Server error"));

    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /save/i }));

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/failed to save/i)).toBeInTheDocument();
    });
    consoleSpy.mockRestore();
  });

  it("saves with optional arm span as null when empty", async () => {
    mockGetProfile.mockResolvedValue({ ...PROFILE_FIXTURE, arm_span_cm: null, femur_length_cm: null });
    mockUpdateProfile.mockResolvedValue(PROFILE_FIXTURE);

    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /save/i }));

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mockUpdateProfile).toHaveBeenCalledWith(
        expect.objectContaining({ arm_span_cm: null, femur_length_cm: null }),
      );
    });
  });

  it("clears success/error on field change", async () => {
    mockGetProfile.mockResolvedValue(PROFILE_FIXTURE);
    mockUpdateProfile.mockResolvedValue(PROFILE_FIXTURE);

    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /save/i }));

    // Save to show success
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => screen.getByText(/profile saved/i));

    // Change a field → success should disappear
    fireEvent.change(screen.getByLabelText(/height/i), { target: { value: "176" } });
    expect(screen.queryByText(/profile saved/i)).not.toBeInTheDocument();
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
