import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";
import EmailCaptureForm from "../EmailCaptureForm";

vi.mock("@/api/beta", () => ({
  requestBetaAccess: vi.fn(),
}));

import { requestBetaAccess } from "@/api/beta";

afterEach(() => {
  vi.resetAllMocks();
});

describe("EmailCaptureForm", () => {
  test("submit button is aria-disabled until consent is checked", async () => {
    const user = userEvent.setup();
    render(<EmailCaptureForm source="hero" />);

    const btn = screen.getByRole("button", {
      name: /request private-beta access/i,
    });
    expect(btn).toHaveAttribute("aria-disabled", "true");

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, "a@b.com");
    expect(btn).toHaveAttribute("aria-disabled", "true");

    const checkbox = screen.getByRole("checkbox");
    await user.click(checkbox);
    expect(btn).toHaveAttribute("aria-disabled", "false");
  });

  test("invalid email is rejected client-side", async () => {
    const user = userEvent.setup();
    render(<EmailCaptureForm source="hero" />);
    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, "not-an-email");
    await user.click(screen.getByRole("checkbox"));
    await user.click(
      screen.getByRole("button", { name: /request private-beta access/i }),
    );
    expect(screen.getByText(/valid email/i)).toBeInTheDocument();
    expect(requestBetaAccess).not.toHaveBeenCalled();
  });

  test("successful submission shows thanks state", async () => {
    vi.mocked(requestBetaAccess).mockResolvedValue({
      id: "id1",
      email: "a@b.com",
      status: "pending",
      created_at: "2026-04-15T00:00:00Z",
    });
    const user = userEvent.setup();
    render(<EmailCaptureForm source="hero" />);
    await user.type(screen.getByLabelText(/email/i), "a@b.com");
    await user.click(screen.getByRole("checkbox"));
    await user.click(
      screen.getByRole("button", { name: /request private-beta access/i }),
    );
    await waitFor(() =>
      expect(screen.getByText(/thanks/i)).toBeInTheDocument(),
    );
  });

  test("409 duplicate shows specific message", async () => {
    vi.mocked(requestBetaAccess).mockRejectedValue({
      status: 409,
      error: {
        code: "beta_request_duplicate",
        message: "This email is already in our private-beta queue.",
      },
    });
    const user = userEvent.setup();
    render(<EmailCaptureForm source="hero" />);
    await user.type(screen.getByLabelText(/email/i), "dup@b.com");
    await user.click(screen.getByRole("checkbox"));
    await user.click(
      screen.getByRole("button", { name: /request private-beta access/i }),
    );
    await waitFor(() =>
      expect(screen.getByText(/already in our private-beta queue/i)).toBeInTheDocument(),
    );
  });

  test("generic 500 shows fallback message", async () => {
    vi.mocked(requestBetaAccess).mockRejectedValue({ status: 500 });
    const user = userEvent.setup();
    render(<EmailCaptureForm source="final_cta" buttonLabel="Join the private beta" />);
    await user.type(screen.getByLabelText(/email/i), "a@b.com");
    await user.click(screen.getByRole("checkbox"));
    await user.click(
      screen.getByRole("button", { name: /join the private beta/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByText(/something went wrong|try again/i),
      ).toBeInTheDocument(),
    );
  });
});
