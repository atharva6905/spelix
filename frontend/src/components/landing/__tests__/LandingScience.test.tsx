import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import LandingScience from "../LandingScience";

// Mock useStatsCounter so we can test done=true and done=false branches
const mockUseStatsCounter = vi.fn(() => ({
  ref: { current: null },
  value: 0,
  done: false,
}));
vi.mock("@/hooks/landing/useStatsCounter", () => ({
  useStatsCounter: () => mockUseStatsCounter(),
}));
vi.mock("@/hooks/landing/useScrollReveal", () => ({
  useScrollReveal: () => ({ current: null }),
}));

describe("LandingScience", () => {
  test("renders section label", () => {
    render(<LandingScience />);
    expect(screen.getByText("04 / The Science Layer")).toBeInTheDocument();
  });

  test("renders expert quote", () => {
    render(<LandingScience />);
    expect(
      screen.getByText(/AI coaching validated by a Kinesiology specialist/),
    ).toBeInTheDocument();
  });

  test("renders stat labels", () => {
    render(<LandingScience />);
    expect(
      screen.getByText(/Of coaching claims cite sources/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Peer-reviewed papers/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/systematic reviews weighted/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/squat, bench press, deadlift/i),
    ).toBeInTheDocument();
  });

  test("stat row has is-done class when done=true", () => {
    mockUseStatsCounter.mockReturnValue({ ref: { current: null }, value: 100, done: true });
    const { container } = render(<LandingScience />);
    const doneStat = container.querySelector(".landing-stat.is-done");
    expect(doneStat).toBeInTheDocument();
  });

  test("stat row does not have is-done class when done=false", () => {
    mockUseStatsCounter.mockReturnValue({ ref: { current: null }, value: 0, done: false });
    const { container } = render(<LandingScience />);
    const doneStats = container.querySelectorAll(".landing-stat.is-done");
    expect(doneStats.length).toBe(0);
  });
});
