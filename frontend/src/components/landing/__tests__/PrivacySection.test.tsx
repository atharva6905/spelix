import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import PrivacySection from "../PrivacySection";

describe("PrivacySection", () => {
  test("renders the three privacy accordion items", () => {
    render(<PrivacySection />);
    expect(
      screen.getByRole("button", { name: /your video is not kept/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /spelix is not a medical device/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /your data belongs to you/i }),
    ).toBeInTheDocument();
  });

  test("section heading reads verbatim", () => {
    render(<PrivacySection />);
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /what spelix does with your video/i,
      }),
    ).toBeInTheDocument();
  });
});
