import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router";

const mockRequestUrl = vi.fn();
const mockCompleteUpload = vi.fn();
const mockUploadFile = vi.fn();

vi.mock("@/api/expert", () => ({
  requestPaperUploadUrl: (...a: unknown[]) => mockRequestUrl(...a),
  completePaperUpload: (...a: unknown[]) => mockCompleteUpload(...a),
  uploadPaperFile: (...a: unknown[]) => mockUploadFile(...a),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: {
          session: {
            access_token: "t",
            user: {
              app_metadata: { role: "expert_reviewer" },
            },
          },
        },
      }),
    },
  },
}));

import ExpertPaperUploadPage from "@/pages/ExpertPaperUploadPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <ExpertPaperUploadPage />
    </MemoryRouter>,
  );
}

/** Wait for the form to be visible (auth check resolved) */
async function waitForForm() {
  await waitFor(() => screen.getByLabelText(/pdf file/i));
}

describe("ExpertPaperUploadPage — file upload", () => {
  beforeEach(() => {
    mockRequestUrl.mockReset();
    mockCompleteUpload.mockReset();
    mockUploadFile.mockReset();
  });

  it("rejects non-PDF files client-side", async () => {
    renderPage();
    await waitForForm();
    const input = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    const file = new File(["x"], "x.docx", { type: "application/msword" });
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    expect(screen.getByText(/must be a pdf/i)).toBeInTheDocument();
  });

  it("rejects files over 50 MB client-side", async () => {
    renderPage();
    await waitForForm();
    const input = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    const big = new File([new Uint8Array(60 * 1024 * 1024)], "big.pdf", {
      type: "application/pdf",
    });
    await act(async () => {
      fireEvent.change(input, { target: { files: [big] } });
    });
    expect(screen.getByText(/50.?mb/i)).toBeInTheDocument();
  });

  it("runs 3-phase upload and shows success", async () => {
    mockRequestUrl.mockResolvedValue({
      id: "p-1",
      upload_url: "https://s/upload",
      storage_path: "papers/p-1/x.pdf",
      expires_at: "2026-04-15T12:00:00Z",
    });
    mockUploadFile.mockImplementation(
      async (_url: string, _file: File, onProg: (p: number) => void) => {
        onProg(50);
        onProg(100);
      },
    );
    mockCompleteUpload.mockResolvedValue({
      id: "p-1",
      review_status: "pending",
      storage_path: "papers/p-1/x.pdf",
    });

    renderPage();
    await waitForForm();
    const titleInput = screen.getByLabelText(/title/i);
    await act(async () => {
      fireEvent.change(titleInput, { target: { value: "Paper T" } });
    });
    const doiInput = screen.getByLabelText(/doi/i);
    await act(async () => {
      fireEvent.change(doiInput, { target: { value: "10.1000/abc123" } });
    });
    const fileInput = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    const file = new File([new Uint8Array(1024)], "x.pdf", {
      type: "application/pdf",
    });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() =>
      expect(mockCompleteUpload).toHaveBeenCalledWith("p-1"),
    );
    expect(screen.getByText(/uploaded and queued/i)).toBeInTheDocument();
  });

  it("shows error if phase 2 fails and skips completion", async () => {
    mockRequestUrl.mockResolvedValue({
      id: "p-1",
      upload_url: "https://s/u",
      storage_path: "papers/p-1/x.pdf",
      expires_at: "z",
    });
    mockUploadFile.mockRejectedValue(new Error("upload failed: network error"));

    renderPage();
    await waitForForm();
    const titleInput = screen.getByLabelText(/title/i);
    await act(async () => {
      fireEvent.change(titleInput, { target: { value: "X" } });
    });
    const doiInput = screen.getByLabelText(/doi/i);
    await act(async () => {
      fireEvent.change(doiInput, { target: { value: "10.1000/xyz" } });
    });
    const fileInput = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    await act(async () => {
      fireEvent.change(fileInput, {
        target: {
          files: [new File(["a"], "x.pdf", { type: "application/pdf" })],
        },
      });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() =>
      expect(screen.getByText(/network error/i)).toBeInTheDocument(),
    );
    expect(mockCompleteUpload).not.toHaveBeenCalled();
  });

  it("disables submit until a PDF file is selected", async () => {
    renderPage();
    await waitForForm();
    expect(
      screen.getByRole("button", { name: /upload/i }),
    ).toBeDisabled();
  });
});

describe("ExpertPaperUploadPage — DOI required + duplicate handling", () => {
  beforeEach(() => {
    mockRequestUrl.mockReset();
    mockCompleteUpload.mockReset();
    mockUploadFile.mockReset();
  });

  /** Fill title + PDF file (leaves DOI alone unless provided) */
  async function fillForm(doi?: string) {
    const titleInput = screen.getByLabelText(/title/i);
    await act(async () => {
      fireEvent.change(titleInput, { target: { value: "Paper T" } });
    });
    if (doi !== undefined) {
      const doiInput = screen.getByLabelText(/doi/i);
      await act(async () => {
        fireEvent.change(doiInput, { target: { value: doi } });
      });
    }
    const fileInput = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
    const file = new File([new Uint8Array(1024)], "x.pdf", {
      type: "application/pdf",
    });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });
  }

  it("disables submit until DOI is filled", async () => {
    renderPage();
    await waitForForm();
    await fillForm(); // title + file set, DOI empty
    expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();

    const doiInput = screen.getByLabelText(/doi/i);
    await act(async () => {
      fireEvent.change(doiInput, { target: { value: "10.1000/abc123" } });
    });
    expect(screen.getByRole("button", { name: /upload/i })).toBeEnabled();
  });

  it("shows required marker on the DOI label", async () => {
    renderPage();
    await waitForForm();
    const doiLabel = document.querySelector('label[for="doi"]');
    expect(doiLabel).not.toBeNull();
    expect(doiLabel!.textContent).toMatch(/\*/);
  });

  it("renders inline DOI error on 409 DUPLICATE_DOI and returns form to editable state", async () => {
    mockRequestUrl.mockRejectedValue({
      status: 409,
      error: {
        code: "DUPLICATE_DOI",
        message: "A paper with this DOI already exists: Existing Paper",
      },
    });

    renderPage();
    await waitForForm();
    await fillForm("10.1000/dup");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      /A paper with this DOI already exists: Existing Paper/,
    );

    // Error rendered adjacent to the DOI input (same field container)
    const doiInput = screen.getByLabelText(/doi/i) as HTMLInputElement;
    expect(doiInput.closest("div")).toContainElement(alert);

    // Form back to editable state with values preserved
    expect(doiInput).not.toBeDisabled();
    expect(screen.getByLabelText(/title/i)).not.toBeDisabled();
    expect(doiInput.value).toBe("10.1000/dup");
    expect((screen.getByLabelText(/title/i) as HTMLInputElement).value).toBe(
      "Paper T",
    );
    expect(mockUploadFile).not.toHaveBeenCalled();
  });

  it("renders inline DOI error on 422 INVALID_DOI", async () => {
    mockRequestUrl.mockRejectedValue({
      status: 422,
      error: {
        code: "INVALID_DOI",
        message: "DOI must match the 10.xxxx/suffix format.",
      },
    });

    renderPage();
    await waitForForm();
    await fillForm("not-a-doi");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/DOI must match the 10\.xxxx\/suffix format\./);
    expect(screen.getByLabelText(/doi/i)).not.toBeDisabled();
  });

  it("clears the DOI error when the DOI value changes", async () => {
    mockRequestUrl.mockRejectedValue({
      status: 409,
      error: {
        code: "DUPLICATE_DOI",
        message: "A paper with this DOI already exists: Existing Paper",
      },
    });

    renderPage();
    await waitForForm();
    await fillForm("10.1000/dup");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });
    await screen.findByRole("alert");

    const doiInput = screen.getByLabelText(/doi/i);
    await act(async () => {
      fireEvent.change(doiInput, { target: { value: "10.1000/dup2" } });
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
