import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import LandingPrivacy from "../LandingPrivacy";

describe("LandingPrivacy", () => {
  test("renders section label", () => {
    render(<LandingPrivacy />);
    expect(screen.getByText("05 / Your Data")).toBeInTheDocument();
  });

  test("renders all 3 privacy titles", () => {
    render(<LandingPrivacy />);
    expect(
      screen.getByText("Classified as health data from day one."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No raw video retained."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Coaching improves — privately."),
    ).toBeInTheDocument();
  });
});
