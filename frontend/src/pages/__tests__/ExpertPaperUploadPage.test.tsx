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
