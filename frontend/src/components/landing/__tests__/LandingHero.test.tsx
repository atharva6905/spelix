import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import LandingHero from "../LandingHero";

vi.mock("@/api/beta", () => ({
  requestBetaAccess: vi.fn(),
  getBetaCount: vi.fn().mockResolvedValue({ count: 123 }),
}));

describe("LandingHero", () => {
  test("renders heading text", () => {
    render(<LandingHero />);
    expect(screen.getByText("Every rep,")).toBeInTheDocument();
    expect(screen.getByText("analyzed.")).toBeInTheDocument();
    expect(screen.getByText("Every claim, cited.")).toBeInTheDocument();
  });

  test("renders subtitle", () => {
    render(<LandingHero />);
    expect(screen.getByText(/Upload a set/i)).toBeInTheDocument();
  });

  test("renders email form", () => {
    render(<LandingHero />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  test("renders background elements with aria-hidden", () => {
    const { container } = render(<LandingHero />);
    const hidden = container.querySelectorAll('[aria-hidden="true"]');
    expect(hidden.length).toBeGreaterThanOrEqual(3);
  });

  test("displays dynamic waitlist count from API", async () => {
    render(<LandingHero />);
    await waitFor(() => {
      expect(screen.getByText("123 people on the waitlist")).toBeInTheDocument();
    });
  });

  test("falls back to default count text when API fails", async () => {
    const { getBetaCount } = await import("@/api/beta");
    vi.mocked(getBetaCount).mockRejectedValueOnce(new Error("network"));
    render(<LandingHero />);
    await waitFor(() => {
      expect(screen.getByText(/people on the waitlist/i)).toBeInTheDocument();
    });
  });
});
