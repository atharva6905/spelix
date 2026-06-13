import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, test, vi, beforeEach } from "vitest";
import FinalCtaSection from "../FinalCtaSection";

const mocks = vi.hoisted(() => ({
  requestBetaAccess: vi.fn(),
  capture: vi.fn(),
}));

vi.mock("@/api/beta", () => ({ requestBetaAccess: mocks.requestBetaAccess }));
vi.mock("@/lib/posthog", () => ({ capture: mocks.capture }));

import { buildApiError } from "@/api/errors";

describe("FinalCtaSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders emotional section heading + 'Join the private beta' button", () => {
    render(<FinalCtaSection />);
    expect(
      screen.getByRole("heading", { level: 2, name: /you have filmed your lifts/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /join the private beta/i }),
    ).toBeInTheDocument();
  });

  test("renders all four 'what beta users get' bullets", () => {
    render(<FinalCtaSection />);
    expect(screen.getByText(/completely free/i)).toBeInTheDocument();
    expect(screen.getByText(/direct line to the team/i)).toBeInTheDocument();
    expect(screen.getByText(/early access to every new feature/i)).toBeInTheDocument();
    expect(screen.getByText(/calibrate the system/i)).toBeInTheDocument();
  });

  test("renders the final disclaimer line", () => {
    render(<FinalCtaSection />);
    expect(
      screen.getByText(/private beta. this feedback is for educational/i),
    ).toBeInTheDocument();
  });

  test("onAttempt and onSuccess fire on successful submission", async () => {
    mocks.requestBetaAccess.mockResolvedValue({ id: "x", status: "pending", created_at: "2026-01-01T00:00:00Z" });

    render(<FinalCtaSection />);

    const emailInput = screen.getByLabelText(/email/i);
    const checkbox = screen.getByRole("checkbox");
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.click(checkbox);

    const submitBtn = screen.getByRole("button", { name: /join the private beta/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mocks.capture).toHaveBeenCalledWith(
        "landing_email_submit_attempt",
        { cta_location: "final" },
      );
    });

    await waitFor(() => {
      expect(mocks.capture).toHaveBeenCalledWith(
        "landing_email_submit_success",
        expect.objectContaining({ cta_location: "final" }),
      );
    });
  });

  test("onError fires when submission fails", async () => {
    mocks.requestBetaAccess.mockRejectedValue(buildApiError(500, {}));

    render(<FinalCtaSection />);

    const emailInput = screen.getByLabelText(/email/i);
    const checkbox = screen.getByRole("checkbox");
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.click(checkbox);

    const submitBtn = screen.getByRole("button", { name: /join the private beta/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mocks.capture).toHaveBeenCalledWith(
        "landing_email_submit_error",
        expect.objectContaining({ cta_location: "final", error_code: 500 }),
      );
    });
  });
});
