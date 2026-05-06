import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import SignupPage from "@/pages/SignupPage";

// Mock navigate
const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock supabase
const mockSignUp = vi.fn();
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      signUp: (...args: unknown[]) => mockSignUp(...args),
    },
  },
}));

describe("SignupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderPage() {
    return render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );
  }

  function fillForm(email: string, password: string, confirm: string) {
    fireEvent.change(screen.getByLabelText(/^email/i), { target: { value: email } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: password } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: confirm } });
  }

  it("renders email input", () => {
    renderPage();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it("renders password input", () => {
    renderPage();
    const passwordInputs = screen.getAllByLabelText(/password/i);
    expect(passwordInputs.length).toBeGreaterThanOrEqual(1);
  });

  it("renders confirm password input", () => {
    renderPage();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });

  it("renders a link to login page", () => {
    renderPage();
    expect(screen.getByText(/sign in/i)).toBeInTheDocument();
  });

  it("shows error when passwords do not match", async () => {
    renderPage();
    fillForm("test@example.com", "password123", "different456");
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
    expect(mockSignUp).not.toHaveBeenCalled();
  });

  it("shows error when password is too short", async () => {
    renderPage();
    fillForm("test@example.com", "short", "short");
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    });
    expect(mockSignUp).not.toHaveBeenCalled();
  });

  it("navigates to /profile on successful signup with session", async () => {
    mockSignUp.mockResolvedValue({
      data: { session: { access_token: "token" }, user: { id: "u-1" } },
      error: null,
    });
    mockNavigate.mockResolvedValue(undefined);

    renderPage();
    fillForm("new@example.com", "password123", "password123");
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/profile");
    });
  });

  it("shows confirmation message when signup returns no session (email confirmation needed)", async () => {
    mockSignUp.mockResolvedValue({
      data: { session: null, user: { id: "u-2" } },
      error: null,
    });

    renderPage();
    fillForm("pending@example.com", "password123", "password123");
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText(/account created/i)).toBeInTheDocument();
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    });
  });

  it("shows auth error message on signup failure", async () => {
    mockSignUp.mockResolvedValue({
      data: { session: null, user: null },
      error: { message: "Email already registered" },
    });

    renderPage();
    fillForm("exists@example.com", "password123", "password123");
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText(/email already registered/i)).toBeInTheDocument();
    });
  });

  it("shows loading state while creating account", async () => {
    let resolveFn!: (val: unknown) => void;
    const pending = new Promise((res) => { resolveFn = res; });
    mockSignUp.mockReturnValue(pending);

    renderPage();
    fillForm("test@example.com", "password123", "password123");
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /creating account/i })).toBeDisabled();
    });

    // Cleanup
    resolveFn({ data: { session: null, user: null }, error: null });
  });

  it("re-enables button after error", async () => {
    mockSignUp.mockResolvedValue({
      data: { session: null, user: null },
      error: { message: "Sign up error" },
    });

    renderPage();
    fillForm("test@example.com", "password123", "password123");
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /create account/i })).not.toBeDisabled();
    });
  });

  it("updates email field value", () => {
    renderPage();
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: "typed@email.com" } });
    expect(emailInput).toHaveValue("typed@email.com");
  });
});
