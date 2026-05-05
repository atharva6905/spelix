import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import LandingChrome from "../LandingChrome";

vi.mock("@/api/beta", () => ({
  requestBetaAccess: vi.fn(),
}));

describe("LandingChrome", () => {
  test("renders sticky bar label", () => {
    const ref = createRef<HTMLElement>();
    render(<LandingChrome finalRef={ref} />);
    expect(screen.getByText("Request Access")).toBeInTheDocument();
  });

  test("renders dismiss button", () => {
    const ref = createRef<HTMLElement>();
    render(<LandingChrome finalRef={ref} />);
    expect(
      screen.getByRole("button", { name: /dismiss/i }),
    ).toBeInTheDocument();
  });

  test("sticky bar is hidden initially", () => {
    const ref = createRef<HTMLElement>();
    const { container } = render(<LandingChrome finalRef={ref} />);
    const sticky = container.querySelector(".landing-sticky");
    expect(sticky).not.toHaveClass("is-on");
  });
});
