import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import LandingProcess from "../LandingProcess";

describe("LandingProcess", () => {
  test("renders section label", () => {
    render(<LandingProcess />);
    expect(screen.getByText("02 / Process")).toBeInTheDocument();
  });

  test("renders all 3 step titles", () => {
    render(<LandingProcess />);
    expect(screen.getByText("Upload your lift")).toBeInTheDocument();
    expect(screen.getByText("Every rep, measured")).toBeInTheDocument();
    expect(screen.getByText("Science-backed coaching")).toBeInTheDocument();
  });

  test("renders step numbers", () => {
    render(<LandingProcess />);
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByText("03")).toBeInTheDocument();
  });
});
