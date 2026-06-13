import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";
import LandingEmailForm from "../LandingEmailForm";

vi.mock("@/api/beta", () => ({
  requestBetaAccess: vi.fn(),
}));

import { requestBetaAccess } from "@/api/beta";
import { buildApiError } from "@/api/errors";

afterEach(() => {
  vi.resetAllMocks();
});

describe("LandingEmailForm", () => {
  test("renders email input and submit button", () => {
    render(<LandingEmailForm source="hero" />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /request access/i }),
    ).toBeInTheDocument();
  });

  test("successful submission shows permanent success state", async () => {
    vi.mocked(requestBetaAccess).mockResolvedValue({
      id: "id1",
      status: "pending",
      created_at: "2026-04-15T00:00:00Z",
    });
    const user = userEvent.setup({ delay: null });
    render(<LandingEmailForm source="hero" />);

    await user.type(screen.getByLabelText(/email/i), "a@b.com");
    await user.click(
      screen.getByRole("button", { name: /request access/i }),
    );

    expect(await screen.findByText(/on the list/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/reach out/i)).toBeInTheDocument();
    expect(requestBetaAccess).toHaveBeenCalledWith({
      email: "a@b.com",
      source: "hero",
      consented: true,
    });
  });

  test(
    "409 duplicate shows message then auto-resets",
    async () => {
      vi.mocked(requestBetaAccess).mockRejectedValue(buildApiError(409, {}));
      const user = userEvent.setup({ delay: null });
      render(<LandingEmailForm source="final_cta" />);

      await user.type(screen.getByLabelText(/email/i), "dup@b.com");
      await user.click(
        screen.getByRole("button", { name: /request access/i }),
      );

      expect(
        await screen.findByText(/already on the list/i),
      ).toBeInTheDocument();

      await waitFor(
        () =>
          expect(
            screen.getByRole("button", { name: /request access/i }),
          ).toBeInTheDocument(),
        { timeout: 5000 },
      );
    },
    10000,
  );

  test(
    "generic error shows message then auto-resets",
    async () => {
      vi.mocked(requestBetaAccess).mockRejectedValue(buildApiError(500, {}));
      const user = userEvent.setup({ delay: null });
      render(<LandingEmailForm source="hero" />);

      await user.type(screen.getByLabelText(/email/i), "a@b.com");
      await user.click(
        screen.getByRole("button", { name: /request access/i }),
      );

      expect(
        await screen.findByText(/something went wrong/i),
      ).toBeInTheDocument();

      await waitFor(
        () =>
          expect(
            screen.getByRole("button", { name: /request access/i }),
          ).toBeInTheDocument(),
        { timeout: 5000 },
      );
    },
    10000,
  );

  test("compact size renders compact button text", () => {
    render(<LandingEmailForm source="hero" size="compact" />);
    expect(
      screen.getByRole("button", { name: /request/i }),
    ).toBeInTheDocument();
  });
});
