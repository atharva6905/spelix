import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import LandingProblem from "../LandingProblem";

describe("LandingProblem", () => {
  test("renders section label", () => {
    render(<LandingProblem />);
    expect(screen.getByText("01 / Problem")).toBeInTheDocument();
  });

  test("renders all 3 card titles", () => {
    render(<LandingProblem />);
    expect(
      screen.getByText("Same clip. Different feedback."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("You get feedback. You don't get why."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No expert in the loop."),
    ).toBeInTheDocument();
  });

  test("renders card tags", () => {
    render(<LandingProblem />);
    expect(screen.getByText("INCONSISTENT")).toBeInTheDocument();
    expect(screen.getByText("UNVERIFIABLE")).toBeInTheDocument();
    expect(screen.getByText("UNVALIDATED")).toBeInTheDocument();
  });
});
