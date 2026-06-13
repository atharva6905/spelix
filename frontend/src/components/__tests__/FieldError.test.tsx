import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FieldError } from "@/components/FieldError";

describe("FieldError", () => {
  it("renders its children as the error text", () => {
    render(<FieldError>DOI is required.</FieldError>);
    expect(screen.getByText("DOI is required.")).toBeInTheDocument();
  });

  it("exposes role=alert for assistive tech", () => {
    render(<FieldError>Something went wrong</FieldError>);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong");
  });

  it("applies the normalized error styling", () => {
    render(<FieldError>oops</FieldError>);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveClass("text-sm", "text-red-600");
  });

  it("merges extra className onto the normalized base", () => {
    render(<FieldError className="mt-1">oops</FieldError>);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveClass("text-sm", "text-red-600", "mt-1");
  });

  it("renders nothing when there are no children", () => {
    const { container } = render(<FieldError>{null}</FieldError>);
    expect(container.firstChild).toBeNull();
  });
});
