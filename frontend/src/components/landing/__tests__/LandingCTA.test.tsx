import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import LandingCTA from "../LandingCTA";

vi.mock("@/api/beta", () => ({
  requestBetaAccess: vi.fn(),
}));

describe("LandingCTA", () => {
  test("renders heading", () => {
    render(<LandingCTA />);
    expect(screen.getByText(/Form coaching/)).toBeInTheDocument();
    expect(screen.getByText(/paper trail/)).toBeInTheDocument();
  });

  test("renders email form", () => {
    render(<LandingCTA />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  test("renders subtext", () => {
    render(<LandingCTA />);
    expect(
      screen.getByText(/Private beta · Invite only/),
    ).toBeInTheDocument();
  });
});
