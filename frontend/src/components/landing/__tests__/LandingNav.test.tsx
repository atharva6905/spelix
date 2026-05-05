import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import LandingNav from "../LandingNav";

describe("LandingNav", () => {
  test("renders wordmark", () => {
    render(<LandingNav />);
    expect(screen.getByText("Spelix")).toBeInTheDocument();
  });

  test("renders private beta badge", () => {
    render(<LandingNav />);
    expect(screen.getByText("Private Beta")).toBeInTheDocument();
  });
});
