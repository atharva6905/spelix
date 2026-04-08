import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import UploadPage from "@/pages/UploadPage";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

vi.mock("@/api/analyses", () => ({
  createAnalysis: vi.fn(),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe("UploadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderUploadPage() {
    return render(
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>,
    );
  }

  it("renders exercise type dropdown with squat, bench, deadlift options", () => {
    renderUploadPage();
    const select = screen.getByLabelText(/exercise type/i);
    expect(select).toBeInTheDocument();

    const options = Array.from(select.querySelectorAll("option")).map(
      (o) => o.value,
    );
    expect(options).toContain("squat");
    expect(options).toContain("bench");
    expect(options).toContain("deadlift");
  });

  it("renders variant dropdown that changes based on exercise type selection", () => {
    renderUploadPage();

    // Initially no variant selected — variant dropdown should be present
    const variantSelect = screen.getByLabelText(/exercise variant/i);
    expect(variantSelect).toBeInTheDocument();

    // Select squat → get squat variants
    const typeSelect = screen.getByLabelText(/exercise type/i);
    fireEvent.change(typeSelect, { target: { value: "squat" } });

    const squatOptions = Array.from(
      variantSelect.querySelectorAll("option"),
    ).map((o) => o.value);
    expect(squatOptions).toContain("high_bar");
    expect(squatOptions).toContain("low_bar");

    // Select bench → get bench variants
    fireEvent.change(typeSelect, { target: { value: "bench" } });
    const benchOptions = Array.from(
      variantSelect.querySelectorAll("option"),
    ).map((o) => o.value);
    expect(benchOptions).toContain("flat");
    expect(benchOptions).toContain("incline");
    expect(benchOptions).toContain("decline");

    // Select deadlift → get deadlift variants
    fireEvent.change(typeSelect, { target: { value: "deadlift" } });
    const dlOptions = Array.from(variantSelect.querySelectorAll("option")).map(
      (o) => o.value,
    );
    expect(dlOptions).toContain("conventional");
    expect(dlOptions).toContain("sumo");
    expect(dlOptions).toContain("romanian");
  });

  it("upload button is aria-disabled until both exercise type AND variant are selected", () => {
    renderUploadPage();
    const button = screen.getByRole("button", { name: /upload/i });

    // Initially disabled — neither selected
    expect(button).toHaveAttribute("aria-disabled", "true");

    // Select exercise type only — still disabled
    const typeSelect = screen.getByLabelText(/exercise type/i);
    fireEvent.change(typeSelect, { target: { value: "squat" } });
    expect(button).toHaveAttribute("aria-disabled", "true");

    // Also select variant — now enabled
    const variantSelect = screen.getByLabelText(/exercise variant/i);
    fireEvent.change(variantSelect, { target: { value: "high_bar" } });
    expect(button).toHaveAttribute("aria-disabled", "false");
  });

  it("renders file input that accepts video files", () => {
    renderUploadPage();
    const fileInput = screen.getByLabelText(/video file/i);
    expect(fileInput).toBeInTheDocument();
    expect(fileInput).toHaveAttribute("accept");
    const accept = fileInput.getAttribute("accept") ?? "";
    // Should accept mp4, mov, or webm
    expect(accept).toMatch(/mp4|mov|webm/);
  });

  it("displays filming guidance text", () => {
    renderUploadPage();
    // General guidance should always be visible — heading is always present
    expect(screen.getByText(/filming guidance/i)).toBeInTheDocument();
    // At least one element contains camera/side/hip guidance text
    const guidanceElements = screen.getAllByText(/camera|side|hip/i);
    expect(guidanceElements.length).toBeGreaterThan(0);
  });

  it("displays exercise-specific filming guidance when exercise type is selected", () => {
    renderUploadPage();
    const typeSelect = screen.getByLabelText(/exercise type/i);
    fireEvent.change(typeSelect, { target: { value: "squat" } });

    // Should show squat-specific guidance — use unique phrase from squat guidance
    expect(
      screen.getByText(/for squat:/i),
    ).toBeInTheDocument();
  });

  it("shows selected filename and size when a file is chosen", () => {
    renderUploadPage();

    const fileInput = screen.getByLabelText(/video file/i);
    const file = new File(["content"], "my-squat.mp4", { type: "video/mp4" });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      configurable: true,
    });
    fireEvent.change(fileInput);

    expect(screen.getByText(/my-squat\.mp4/i)).toBeInTheDocument();
  });
});
