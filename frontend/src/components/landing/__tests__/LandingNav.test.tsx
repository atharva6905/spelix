import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import LandingNav from "../LandingNav";

// Mock useNavScroll so we can control scroll state
const mockUseNavScroll = vi.fn(() => false);
vi.mock("@/hooks/landing/useNavScroll", () => ({
  useNavScroll: () => mockUseNavScroll(),
}));

describe("LandingNav", () => {
  test("renders wordmark", () => {
    render(<LandingNav />);
    expect(screen.getByText("Spelix")).toBeInTheDocument();
  });

  test("renders private beta badge", () => {
    render(<LandingNav />);
    expect(screen.getByText("Private Beta")).toBeInTheDocument();
  });

  test("does not have is-scrolled class when not scrolled", () => {
    mockUseNavScroll.mockReturnValue(false);
    const { container } = render(<LandingNav />);
    const nav = container.querySelector("nav");
    expect(nav).not.toHaveClass("is-scrolled");
  });

  test("adds is-scrolled class when scrolled", () => {
    mockUseNavScroll.mockReturnValue(true);
    const { container } = render(<LandingNav />);
    const nav = container.querySelector("nav");
    expect(nav).toHaveClass("is-scrolled");
  });
});
