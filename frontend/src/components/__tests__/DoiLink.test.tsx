import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DoiLink } from "@/components/DoiLink";

describe("DoiLink", () => {
  it("renders an anchor to doi.org with target=_blank and rel=noopener noreferrer", () => {
    render(<DoiLink doi="10.1234/squat" />);
    const link = screen.getByRole("link", { name: "10.1234/squat" });
    expect(link).toHaveAttribute("href", "https://doi.org/10.1234/squat");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders children as the link label when provided", () => {
    render(<DoiLink doi="10.1234/squat">DOI: 10.1234/squat</DoiLink>);
    const link = screen.getByRole("link", { name: "DOI: 10.1234/squat" });
    expect(link).toHaveAttribute("href", "https://doi.org/10.1234/squat");
  });

  it("merges extra className onto the base hover:underline class", () => {
    render(<DoiLink doi="10.1234/squat" className="font-mono text-xs text-indigo-600" />);
    const link = screen.getByRole("link", { name: "10.1234/squat" });
    expect(link).toHaveClass("hover:underline");
    expect(link).toHaveClass("font-mono", "text-xs", "text-indigo-600");
  });

  it("applies aria-label when provided", () => {
    render(<DoiLink doi="10.1234/squat" aria-label="DOI link" />);
    expect(screen.getByRole("link", { name: "DOI link" })).toBeInTheDocument();
  });

  it("renders the standardized empty fallback span when doi is null", () => {
    render(<DoiLink doi={null} />);
    const fallback = screen.getByTestId("doi-empty");
    expect(fallback.tagName).toBe("SPAN");
    expect(fallback).toHaveTextContent("—");
    expect(fallback).toHaveClass("text-gray-400");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders the empty fallback when doi is undefined", () => {
    render(<DoiLink />);
    expect(screen.getByTestId("doi-empty")).toBeInTheDocument();
  });
});
