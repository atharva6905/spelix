import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import FinalCtaSection from "../FinalCtaSection";

vi.mock("@/api/beta", () => ({ requestBetaAccess: vi.fn() }));
vi.mock("@/lib/posthog", () => ({ capture: vi.fn() }));

describe("FinalCtaSection", () => {
  test("renders emotional section heading + 'Join the private beta' button", () => {
    render(<FinalCtaSection />);
    expect(
      screen.getByRole("heading", { level: 2, name: /you have filmed your lifts/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /join the private beta/i }),
    ).toBeInTheDocument();
  });

  test("renders all four 'what beta users get' bullets", () => {
    render(<FinalCtaSection />);
    expect(screen.getByText(/completely free/i)).toBeInTheDocument();
    expect(screen.getByText(/direct line to the team/i)).toBeInTheDocument();
    expect(screen.getByText(/early access to every new feature/i)).toBeInTheDocument();
    expect(screen.getByText(/calibrate the system/i)).toBeInTheDocument();
  });

  test("renders the final disclaimer line", () => {
    render(<FinalCtaSection />);
    expect(
      screen.getByText(/private beta. this feedback is for educational/i),
    ).toBeInTheDocument();
  });
});
