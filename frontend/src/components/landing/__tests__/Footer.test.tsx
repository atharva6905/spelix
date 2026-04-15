import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import Footer from "../Footer";

describe("Footer", () => {
  test("renders wordmark, disclaimer, beta-terms link", () => {
    render(<Footer />);
    expect(screen.getByText("Spelix")).toBeInTheDocument();
    expect(
      screen.getByText(/private beta. this feedback is for educational/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /beta terms/i })).toBeInTheDocument();
  });
});
