import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import LandingReport from "../LandingReport";
import { SNIPPET_LABEL_FINAL, SNIPPET_LABEL_INITIAL } from "@/constants/landing";

// Mock hooks used by LandingReport
const mockUseTypewriter = vi.fn(() => ({
  ref: { current: null },
  displayText: "",
  isDone: false,
}));
vi.mock("@/hooks/landing/useTypewriter", () => ({
  useTypewriter: () => mockUseTypewriter(),
}));
vi.mock("@/hooks/landing/useScrollReveal", () => ({
  useScrollReveal: () => ({ current: null }),
}));

describe("LandingReport", () => {
  test("renders section label", () => {
    render(<LandingReport />);
    expect(screen.getByText("03 / Report")).toBeInTheDocument();
  });

  test("renders all 4 dimension names", () => {
    render(<LandingReport />);
    expect(screen.getByText("Movement Quality")).toBeInTheDocument();
    expect(screen.getByText("Technique")).toBeInTheDocument();
    expect(screen.getByText("Path & Balance")).toBeInTheDocument();
    expect(screen.getByText("Control")).toBeInTheDocument();
  });

  test("renders snippet with initial label when isDone=false", () => {
    mockUseTypewriter.mockReturnValue({ ref: { current: null }, displayText: "", isDone: false });
    render(<LandingReport />);
    expect(screen.getByText(SNIPPET_LABEL_INITIAL)).toBeInTheDocument();
  });

  test("renders snippet with final label when isDone=true", () => {
    mockUseTypewriter.mockReturnValue({
      ref: { current: null },
      displayText: "Your squat depth...",
      isDone: true,
    });
    render(<LandingReport />);
    expect(screen.getByText(SNIPPET_LABEL_FINAL)).toBeInTheDocument();
  });

  test("does not render cursor when isDone=true", () => {
    mockUseTypewriter.mockReturnValue({
      ref: { current: null },
      displayText: "Full text here",
      isDone: true,
    });
    const { container } = render(<LandingReport />);
    expect(container.querySelector(".landing-snippet-cursor")).not.toBeInTheDocument();
  });

  test("renders cursor when isDone=false", () => {
    mockUseTypewriter.mockReturnValue({ ref: { current: null }, displayText: "", isDone: false });
    const { container } = render(<LandingReport />);
    expect(container.querySelector(".landing-snippet-cursor")).toBeInTheDocument();
  });
});
