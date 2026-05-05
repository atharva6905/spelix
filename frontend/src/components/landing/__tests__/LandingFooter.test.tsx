import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import LandingFooter from "../LandingFooter";

describe("LandingFooter", () => {
  test("renders wordmark", () => {
    render(<LandingFooter />);
    expect(screen.getByText("Spelix")).toBeInTheDocument();
  });

  test("renders copyright", () => {
    render(<LandingFooter />);
    expect(screen.getByText("© 2026 Spelix")).toBeInTheDocument();
  });

  test("renders footer links", () => {
    render(<LandingFooter />);
    expect(screen.getByText("Privacy Policy")).toBeInTheDocument();
    expect(screen.getByText("Beta Terms")).toBeInTheDocument();
    expect(screen.getByText("spelix.app")).toBeInTheDocument();
  });

  test("renders legal text", () => {
    render(<LandingFooter />);
    expect(
      screen.getByText(/not a medical device/i),
    ).toBeInTheDocument();
  });
});
