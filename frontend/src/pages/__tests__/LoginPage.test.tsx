import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import LoginPage from "@/pages/LoginPage";

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
const mockSignIn = vi.fn();
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      signInWithPassword: (...args: unknown[]) => mockSignIn(...args),
    },
  },
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderPage() {
    return render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
  }

  it("renders email input", () => {
    renderPage();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it("renders password input", () => {
    renderPage();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("renders a link to signup page", () => {
    renderPage();
    expect(screen.getByText(/sign up/i)).toBeInTheDocument();
  });

  it("shows loading state while signing in", async () => {
    let resolveFn!: (val: unknown) => void;
    const pending = new Promise((res) => { resolveFn = res; });
    mockSignIn.mockReturnValue(pending);

    renderPage();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();
    });

    // Cleanup
    resolveFn({ error: null });
  });

  it("navigates to /upload on successful sign in", async () => {
    mockSignIn.mockResolvedValue({ error: null });
    mockNavigate.mockResolvedValue(undefined);

    renderPage();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/upload");
    });
  });

  it("displays error message on auth failure", async () => {
    mockSignIn.mockResolvedValue({
      error: { message: "Invalid login credentials" },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "bad@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid login credentials/i)).toBeInTheDocument();
    });
  });

  it("re-enables button after auth failure", async () => {
    mockSignIn.mockResolvedValue({
      error: { message: "Bad credentials" },
    });

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /sign in/i })).not.toBeDisabled();
    });
  });

  it("updates email state on input change", () => {
    renderPage();
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: "new@email.com" } });
    expect(emailInput).toHaveValue("new@email.com");
  });

  it("updates password state on input change", () => {
    renderPage();
    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(passwordInput, { target: { value: "mypassword" } });
    expect(passwordInput).toHaveValue("mypassword");
  });

  it("does not show error initially", () => {
    renderPage();
    // No error div should be present initially
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
