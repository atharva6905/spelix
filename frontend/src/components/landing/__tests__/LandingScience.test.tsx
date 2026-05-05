import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import LandingScience from "../LandingScience";

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
});
