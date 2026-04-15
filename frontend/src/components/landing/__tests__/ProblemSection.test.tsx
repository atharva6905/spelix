import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import ProblemSection from "../ProblemSection";

describe("ProblemSection", () => {
  test("renders the 8% stat and three failure-mode headings", () => {
    render(<ProblemSection />);
    expect(screen.getByText("8%")).toBeInTheDocument();
    // "JMIR, 2024" appears in both the stat caption and the failure-mode body
    expect(screen.getAllByText(/jmir, 2024/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("heading", { name: /no source/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /no consistency/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /one body fits all/i })).toBeInTheDocument();
  });

  test("renders the section H2", () => {
    render(<ProblemSection />);
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /you've watched yourself lift/i,
      }),
    ).toBeInTheDocument();
  });
});
