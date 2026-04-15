import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import DifferentiatorsSection from "../DifferentiatorsSection";

describe("DifferentiatorsSection", () => {
  test("renders 3 differentiator accordion buttons", () => {
    render(<DifferentiatorsSection />);
    expect(
      screen.getByRole("button", { name: /every claim has a source/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /built with a kinesiology specialist/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /coach brain/i })).toBeInTheDocument();
  });

  test("first accordion item is open by default", () => {
    render(<DifferentiatorsSection />);
    const first = screen.getByRole("button", { name: /every claim has a source/i });
    expect(first).toHaveAttribute("aria-expanded", "true");
  });

  test("renders verbatim SRS §829 credential line", () => {
    render(<DifferentiatorsSection />);
    expect(
      screen.getByText(
        /ai coaching validated by a kinesiology specialist \(b\.sc\. candidate\)\. all coaching claims are grounded in peer-reviewed literature reviewed and curated by a qualified expert\./i,
      ),
    ).toBeInTheDocument();
  });
});
