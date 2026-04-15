import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import Hero from "../Hero";

vi.mock("@/api/beta", () => ({ requestBetaAccess: vi.fn() }));

describe("Hero", () => {
  test("renders Option A headline and sub-headline verbatim", () => {
    render(<Hero />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /barbell form coaching where every piece of feedback cites its source/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/computer vision and generates structured coaching grounded in peer-reviewed biomechanics literature/i),
    ).toBeInTheDocument();
  });

  test("renders an email capture form", () => {
    render(<Hero />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /request private-beta access/i })).toBeInTheDocument();
  });

  test("renders disclaimer below CTA", () => {
    render(<Hero />);
    expect(
      screen.getByText(/private beta. this feedback is for educational/i),
    ).toBeInTheDocument();
  });
});
