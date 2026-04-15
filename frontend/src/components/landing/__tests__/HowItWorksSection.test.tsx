import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import HowItWorksSection from "../HowItWorksSection";

describe("HowItWorksSection", () => {
  test("renders section heading and all three steps", () => {
    render(<HowItWorksSection />);
    expect(
      screen.getByRole("heading", { level: 2, name: /three steps, one lift at a time/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/upload your video/i)).toBeInTheDocument();
    expect(screen.getByText(/analyses every rep/i)).toBeInTheDocument();
    expect(screen.getByText(/cites its sources/i)).toBeInTheDocument();
  });

  test("renders 'what you get' bullet list", () => {
    render(<HowItWorksSection />);
    expect(screen.getByText(/per-rep biomechanical scores/i)).toBeInTheDocument();
    expect(screen.getByText(/annotated video/i)).toBeInTheDocument();
    expect(screen.getByText(/downloadable pdf/i)).toBeInTheDocument();
    expect(screen.getByText(/follow-up chat/i)).toBeInTheDocument();
  });
});
