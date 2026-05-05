import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import LandingHero from "../LandingHero";

vi.mock("@/api/beta", () => ({
  requestBetaAccess: vi.fn(),
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
});
