import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CitationTooltip, parseWithCitations } from "@/components/CitationTooltip";
import type { Citation } from "@/api/analyses";

const CITATION_1: Citation = {
  title: "Biomechanics of the Squat",
  authors: ["Smith J", "Jones K"],
  year: 2022,
  doi: "10.1234/squat.2022",
};

const CITATION_2: Citation = {
  title: "Knee Valgus in Athletes",
  authors: ["Brown A"],
  year: 2020,
  doi: null,
};

describe("parseWithCitations", () => {
  it("returns plain text when no markers present", () => {
    const { container } = render(
      <>{parseWithCitations("plain text with no citations", [])}</>,
    );
    expect(container.textContent).toBe("plain text with no citations");
  });

  it("returns plain text when citations array is empty", () => {
    const { container } = render(
      <>{parseWithCitations("some text [1] here", [])}</>,
    );
    // Out-of-range markers render as plain text
    expect(container.textContent).toContain("[1]");
  });

  it("renders a citation marker for valid [N] reference", () => {
    render(
      <>{parseWithCitations("Valgus collapse [1] observed", [CITATION_1])}</>,
    );
    expect(screen.getByTestId("citation-marker-1")).toBeInTheDocument();
    expect(screen.getByTestId("citation-marker-1").tagName).toBe("BUTTON");
  });

  it("renders surrounding text correctly around markers", () => {
    const { container } = render(
      <>{parseWithCitations("Before [1] after", [CITATION_1])}</>,
    );
    expect(container.textContent).toContain("Before");
    expect(container.textContent).toContain("after");
  });

  it("renders multiple citation markers", () => {
    render(
      <>
        {parseWithCitations("First [1] and second [2]", [
          CITATION_1,
          CITATION_2,
        ])}
      </>,
    );
    expect(screen.getByTestId("citation-marker-1")).toBeInTheDocument();
    expect(screen.getByTestId("citation-marker-2")).toBeInTheDocument();
  });

  it("renders out-of-range index as plain text", () => {
    const { container } = render(
      <>{parseWithCitations("Reference [5] here", [CITATION_1])}</>,
    );
    expect(container.textContent).toContain("[5]");
    expect(screen.queryByTestId("citation-marker-5")).not.toBeInTheDocument();
  });

  it("renders [0] as plain text (citations are 1-based)", () => {
    const { container } = render(
      <>{parseWithCitations("Reference [0] here", [CITATION_1])}</>,
    );
    expect(container.textContent).toContain("[0]");
    expect(screen.queryByTestId("citation-marker-0")).not.toBeInTheDocument();
  });
});

describe("CitationTooltip", () => {
  it("renders superscript marker button", () => {
    render(<CitationTooltip index={1} citation={CITATION_1} />);
    const btn = screen.getByTestId("citation-marker-1");
    expect(btn).toBeInTheDocument();
    expect(btn.textContent).toBe("[1]");
  });

  it("shows tooltip panel on hover with citation details", () => {
    render(<CitationTooltip index={1} citation={CITATION_1} />);
    screen.getByTestId("citation-marker-1");

    // Tooltip exists in DOM but hidden via CSS class (jsdom has no CSS engine)
    const panel = screen.getByTestId("citation-tooltip-panel-1");
    expect(panel.className).toContain("invisible");
    expect(panel.textContent).toContain("Biomechanics of the Squat");
    expect(panel.textContent).toContain("Smith J");
    expect(panel.textContent).toContain("2022");
  });

  it("shows tooltip panel on focus (keyboard accessible)", () => {
    render(<CitationTooltip index={1} citation={CITATION_1} />);
    const btn = screen.getByTestId("citation-marker-1");
    fireEvent.focus(btn);
    const panel = screen.getByTestId("citation-tooltip-panel-1");
    expect(panel.textContent).toContain("Biomechanics of the Squat");
  });

  it("renders DOI link when doi is present", () => {
    render(<CitationTooltip index={1} citation={CITATION_1} />);
    const link = screen.getByRole("link", { name: /doi/i });
    expect(link).toHaveAttribute(
      "href",
      "https://doi.org/10.1234/squat.2022",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("does not render DOI link when doi is null", () => {
    render(<CitationTooltip index={2} citation={CITATION_2} />);
    expect(screen.queryByRole("link", { name: /doi/i })).not.toBeInTheDocument();
  });

  it("has correct aria-label", () => {
    render(<CitationTooltip index={1} citation={CITATION_1} />);
    const btn = screen.getByTestId("citation-marker-1");
    expect(btn).toHaveAttribute("aria-label", "Citation 1");
  });
});
