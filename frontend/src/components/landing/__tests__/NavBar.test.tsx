import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import NavBar from "../NavBar";

describe("NavBar", () => {
  test("renders Spelix wordmark and 3 anchor links + CTA", () => {
    render(<NavBar />);
    expect(screen.getByRole("link", { name: /^spelix$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /how it works/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /why spelix/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /privacy/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /request beta access/i })).toBeInTheDocument();
  });
});
