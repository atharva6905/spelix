import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import LandingReport from "../LandingReport";

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

  test("renders snippet with initial label", () => {
    render(<LandingReport />);
    expect(screen.getByText("GENERATING...")).toBeInTheDocument();
  });
});
