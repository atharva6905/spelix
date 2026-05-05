import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, test, vi, beforeEach } from "vitest";
import Hero from "../Hero";

const mocks = vi.hoisted(() => ({
  requestBetaAccess: vi.fn(),
  capture: vi.fn(),
}));

vi.mock("@/api/beta", () => ({ requestBetaAccess: mocks.requestBetaAccess }));
vi.mock("@/lib/posthog", () => ({ capture: mocks.capture }));

describe("Hero", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders Option A headline and sub-headline verbatim", () => {
    render(<Hero />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /barbell form coaching where every piece of feedback cites its source/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/computer vision and generates structured coaching grounded in peer-reviewed biomechanics literature/i),
    ).toBeInTheDocument();
  });

  test("renders an email capture form", () => {
    render(<Hero />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /request private-beta access/i })).toBeInTheDocument();
  });

  test("renders disclaimer below CTA", () => {
    render(<Hero />);
    expect(
      screen.getByText(/private beta. this feedback is for educational/i),
    ).toBeInTheDocument();
  });

  test("onAttempt and onSuccess callbacks fire on successful email submit", async () => {
    mocks.requestBetaAccess.mockResolvedValue({});

    render(<Hero />);

    const emailInput = screen.getByLabelText(/email/i);
    const checkbox = screen.getByRole("checkbox");

    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.click(checkbox);

    const submitButton = screen.getByRole("button", { name: /request private-beta access/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      // onAttempt fires: capture("landing_email_submit_attempt", { cta_location: "hero" })
      expect(mocks.capture).toHaveBeenCalledWith(
        "landing_email_submit_attempt",
        { cta_location: "hero" },
      );
    });

    await waitFor(() => {
      // onSuccess fires: capture("landing_email_submit_success", ...)
      expect(mocks.capture).toHaveBeenCalledWith(
        "landing_email_submit_success",
        expect.objectContaining({ cta_location: "hero" }),
      );
    });
  });

  test("onError callback fires when submission fails", async () => {
    mocks.requestBetaAccess.mockRejectedValue({ status: 500 });

    render(<Hero />);

    const emailInput = screen.getByLabelText(/email/i);
    const checkbox = screen.getByRole("checkbox");

    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.click(checkbox);

    const submitButton = screen.getByRole("button", { name: /request private-beta access/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      // onError fires: capture("landing_email_submit_error", { cta_location: "hero", error_code: 500 })
      expect(mocks.capture).toHaveBeenCalledWith(
        "landing_email_submit_error",
        expect.objectContaining({ cta_location: "hero", error_code: 500 }),
      );
    });
  });
});
