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
  // Real const re-declared here: vi.mock replaces the whole module, and the
  // page imports these options alongside the mocked API functions.
  SEX_APPLICABILITY_OPTIONS: [
    { value: "male", label: "Male" },
    { value: "female", label: "Female" },
    { value: "both", label: "Both" },
  ],
}));

// Issue #283: the page now reads the shared `isApiError` from `@/api/errors`,
// so error fixtures throw the real typed `ApiError` (`name === "ApiError"`,
// code/message at the TOP level) — the transitional legacy `{ status, error }`
// object literals are gone.
import { buildApiError } from "@/api/errors";

/** Build the real typed ApiError a structured backend failure produces. */
function apiErr(status: number, code: string, message: string) {
  return buildApiError(status, { detail: { error: { code, message } } });
}

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

/** Reset all mocked @/api/expert functions. Shared across every describe block. */
function resetApiMocks() {
  mockRequestUrl.mockReset();
  mockCompleteUpload.mockReset();
  mockUploadFile.mockReset();
}

interface FillFormOptions {
  /** Title text (default "Paper T"). */
  title?: string;
  /**
   * DOI value. Pass a string to type it; omit (undefined) to leave the DOI
   * field untouched — used by the DOI-required and DOI-optional cases.
   */
  doi?: string;
  /** Uploaded file (default a 1 KB application/pdf). */
  file?: File;
}

/** Fill title + (optional) DOI + PDF file so the form is submittable. */
async function fillForm({ title = "Paper T", doi, file }: FillFormOptions = {}) {
  const titleInput = screen.getByLabelText(/title/i);
  await act(async () => {
    fireEvent.change(titleInput, { target: { value: title } });
  });
  if (doi !== undefined) {
    const doiInput = screen.getByLabelText(/doi/i);
    await act(async () => {
      fireEvent.change(doiInput, { target: { value: doi } });
    });
  }
  const fileInput = screen.getByLabelText(/pdf file/i) as HTMLInputElement;
  const pdf =
    file ?? new File([new Uint8Array(1024)], "x.pdf", { type: "application/pdf" });
  await act(async () => {
    fireEvent.change(fileInput, { target: { files: [pdf] } });
  });
}

describe("ExpertPaperUploadPage — file upload", () => {
  beforeEach(resetApiMocks);

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
    await fillForm({ doi: "10.1000/abc123" });
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
    await fillForm({ title: "X", doi: "10.1000/xyz" });
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
  beforeEach(resetApiMocks);

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

  it("caps DOI input at 200 characters", async () => {
    renderPage();
    await waitForForm();
    const doiInput = screen.getByLabelText(/doi/i) as HTMLInputElement;
    expect(doiInput).toHaveAttribute("maxLength", "200");
  });

  it("shows inline DOI error when submit fires with empty DOI", async () => {
    renderPage();
    await waitForForm();
    await fillForm(); // title + file set, DOI empty

    // Bypass the disabled button — fire submit on the form element directly
    const formEl = document.querySelector("form");
    expect(formEl).not.toBeNull();
    await act(async () => {
      fireEvent.submit(formEl!);
    });

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("DOI is required.");
    const doiInput = screen.getByLabelText(/doi/i) as HTMLInputElement;
    expect(doiInput.closest("div")).toContainElement(alert);

    // Form stays idle/editable, no request fired
    expect(doiInput).not.toBeDisabled();
    expect(screen.getByLabelText(/title/i)).not.toBeDisabled();
    expect(mockRequestUrl).not.toHaveBeenCalled();
  });

  it("shows required marker on the DOI label", async () => {
    renderPage();
    await waitForForm();
    const doiLabel = document.querySelector('label[for="doi"]');
    expect(doiLabel).not.toBeNull();
    expect(doiLabel!.textContent).toMatch(/\*/);
  });

  it("renders inline DOI error on 409 DUPLICATE_DOI and returns form to editable state", async () => {
    mockRequestUrl.mockRejectedValue(
      apiErr(409, "DUPLICATE_DOI", "A paper with this DOI already exists: Existing Paper"),
    );

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/dup" });
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
    mockRequestUrl.mockRejectedValue(
      apiErr(422, "INVALID_DOI", "DOI must match the 10.xxxx/suffix format."),
    );

    renderPage();
    await waitForForm();
    await fillForm({ doi: "not-a-doi" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/DOI must match the 10\.xxxx\/suffix format\./);
    expect(screen.getByLabelText(/doi/i)).not.toBeDisabled();
  });

  it("clears a stale DOI error when a resubmit succeeds", async () => {
    mockRequestUrl.mockRejectedValueOnce(
      apiErr(409, "DUPLICATE_DOI", "A paper with this DOI already exists: Existing Paper"),
    );
    mockRequestUrl.mockResolvedValueOnce({
      id: "p-1",
      upload_url: "https://s/upload",
      storage_path: "papers/p-1/x.pdf",
      expires_at: "2026-04-15T12:00:00Z",
    });
    mockUploadFile.mockResolvedValue(undefined);
    mockCompleteUpload.mockResolvedValue({
      id: "p-1",
      review_status: "pending",
      storage_path: "papers/p-1/x.pdf",
    });

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/dup" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });
    await screen.findByRole("alert");

    // Edit a non-DOI field, then resubmit the same DOI — now succeeds
    const titleInput = screen.getByLabelText(/title/i);
    await act(async () => {
      fireEvent.change(titleInput, { target: { value: "Paper T v2" } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() =>
      expect(screen.getByText(/uploaded and queued/i)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("clears the DOI error when the DOI value changes", async () => {
    mockRequestUrl.mockRejectedValue(
      apiErr(409, "DUPLICATE_DOI", "A paper with this DOI already exists: Existing Paper"),
    );

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/dup" });
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

describe("ExpertPaperUploadPage — DOI optional by document type (issue #234)", () => {
  beforeEach(resetApiMocks);

  /** Fill title + PDF file with DOI deliberately left empty. */
  const fillFormNoDoi = () => fillForm({ title: "Textbook Chapter" });

  async function selectDocumentType(value: string) {
    const select = screen.getByLabelText(/document type/i);
    await act(async () => {
      fireEvent.change(select, { target: { value } });
    });
  }

  function mockSuccessfulUpload() {
    mockRequestUrl.mockResolvedValue({
      id: "p-1",
      upload_url: "https://s/upload",
      storage_path: "papers/p-1/x.pdf",
      expires_at: "2026-04-15T12:00:00Z",
    });
    mockUploadFile.mockResolvedValue(undefined);
    mockCompleteUpload.mockResolvedValue({
      id: "p-1",
      review_status: "pending",
      storage_path: "papers/p-1/x.pdf",
    });
  }

  it("renders a Document Type select defaulting to research_paper", async () => {
    renderPage();
    await waitForForm();
    const select = screen.getByLabelText(/document type/i) as HTMLSelectElement;
    expect(select.value).toBe("research_paper");
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toEqual([
      "research_paper",
      "textbook",
      "clinical_guideline",
      "expert_annotation",
      "other",
    ]);
  });

  it("removes the DOI required marker for non-research_paper types", async () => {
    renderPage();
    await waitForForm();
    const doiLabel = document.querySelector('label[for="doi"]')!;
    expect(doiLabel.textContent).toMatch(/\*/);
    await selectDocumentType("textbook");
    expect(doiLabel.textContent).not.toMatch(/\*/);
  });

  it("enables submit without a DOI when a DOI-less type is selected", async () => {
    renderPage();
    await waitForForm();
    await fillFormNoDoi();
    expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
    await selectDocumentType("clinical_guideline");
    expect(screen.getByRole("button", { name: /upload/i })).toBeEnabled();
  });

  it("omits doi from the payload when empty for a DOI-less type", async () => {
    mockSuccessfulUpload();
    renderPage();
    await waitForForm();
    await fillFormNoDoi();
    await selectDocumentType("textbook");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(mockRequestUrl).toHaveBeenCalled());
    const payload = mockRequestUrl.mock.calls[0][0] as Record<string, unknown>;
    expect(payload.document_type).toBe("textbook");
    expect("doi" in payload).toBe(false);
  });

  it("still sends a non-empty DOI for a DOI-less type (optional DOI path)", async () => {
    mockSuccessfulUpload();
    renderPage();
    await waitForForm();
    await fillFormNoDoi();
    await selectDocumentType("textbook");
    const doiInput = screen.getByLabelText(/doi/i);
    await act(async () => {
      fireEvent.change(doiInput, { target: { value: "10.1000/textbook1" } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(mockRequestUrl).toHaveBeenCalled());
    expect(mockRequestUrl).toHaveBeenCalledWith(
      expect.objectContaining({
        document_type: "textbook",
        doi: "10.1000/textbook1",
      }),
    );
  });

  it("re-requires the DOI when switching back to research_paper", async () => {
    renderPage();
    await waitForForm();
    await fillFormNoDoi();
    await selectDocumentType("textbook");
    expect(screen.getByRole("button", { name: /upload/i })).toBeEnabled();
    await selectDocumentType("research_paper");
    expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
  });

  it("keeps the in-handler DOI guard for research_paper only", async () => {
    renderPage();
    await waitForForm();
    await fillFormNoDoi();
    await selectDocumentType("textbook");

    // Bypass the button — fire submit on the form element directly
    const formEl = document.querySelector("form");
    await act(async () => {
      fireEvent.submit(formEl!);
    });
    // No inline DOI-required error for a DOI-less type
    expect(screen.queryByText(/doi is required/i)).not.toBeInTheDocument();
  });
});

describe("ExpertPaperUploadPage — complete-step 409 + reset hygiene (issue #236)", () => {
  beforeEach(resetApiMocks);

  function mockUploadReachesComplete() {
    mockRequestUrl.mockResolvedValue({
      id: "p-1",
      upload_url: "https://s/upload",
      storage_path: "papers/p-1/x.pdf",
      expires_at: "2026-04-15T12:00:00Z",
    });
    mockUploadFile.mockResolvedValue(undefined);
  }

  it("appends the discard hint when the complete step returns 409", async () => {
    mockUploadReachesComplete();
    mockCompleteUpload.mockRejectedValue(
      apiErr(409, "PAPER_CONFLICT", "Conflict during finalize."),
    );

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/abc123" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("Conflict during finalize.");
    expect(banner).toHaveTextContent(
      "Your uploaded file was discarded; submitting again will re-upload it.",
    );
  });

  it("surfaces a structured non-409 API error message from an upload phase", async () => {
    mockUploadReachesComplete();
    mockCompleteUpload.mockRejectedValue(
      apiErr(500, "SERVER_ERROR", "Server error, try again."),
    );

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/abc123" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("Server error, try again.");
    // Not a completing-409, so the discard hint must NOT be appended.
    expect(banner).not.toHaveTextContent("Your uploaded file was discarded");
  });

  it("does NOT append the discard hint for a non-completing 409 (request phase)", async () => {
    mockRequestUrl.mockRejectedValue(
      apiErr(409, "PAPER_CONFLICT", "Conflict while requesting."),
    );

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/abc123" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("Conflict while requesting.");
    expect(banner).not.toHaveTextContent(
      "Your uploaded file was discarded; submitting again will re-upload it.",
    );
  });

  it("does NOT append the discard hint for a non-completing 409 (upload phase)", async () => {
    // request phase succeeds, but the direct-to-storage PUT (upload phase)
    // returns 409. The failing phase is "uploading", not "completing", so the
    // discard hint must NOT be appended — nothing has been finalized/discarded.
    mockRequestUrl.mockResolvedValue({
      id: "p-1",
      upload_url: "https://s/upload",
      storage_path: "papers/p-1/x.pdf",
      expires_at: "2026-04-15T12:00:00Z",
    });
    mockUploadFile.mockRejectedValue(
      apiErr(409, "CONFLICT", "Conflict during upload."),
    );

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/abc123" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("Conflict during upload.");
    expect(banner).not.toHaveTextContent(
      "Your uploaded file was discarded; submitting again will re-upload it.",
    );
    // The completing phase never ran, so finalize was never attempted.
    expect(mockCompleteUpload).not.toHaveBeenCalled();
  });

  it("Upload Another resets to a fresh empty form", async () => {
    // After a successful upload the success screen is shown. Clicking
    // "Upload Another" must return the user to a FRESH form: the success
    // banner is gone, the form is rendered again, and the inputs are reset to
    // their initial values (empty title, no file selected).
    //
    // Note: resetForm() also calls clearErrors() (which nulls doiError), but
    // that error-clearing is intentional defense-in-depth and is NOT separately
    // observable here — errors never coexist with the success screen, so the
    // load-bearing assertion below is the observable form reset, not error state.
    mockRequestUrl.mockResolvedValue({
      id: "p-1",
      upload_url: "https://s/upload",
      storage_path: "papers/p-1/x.pdf",
      expires_at: "2026-04-15T12:00:00Z",
    });
    mockUploadFile.mockResolvedValue(undefined);
    mockCompleteUpload.mockResolvedValue({
      id: "p-1",
      review_status: "pending",
      storage_path: "papers/p-1/x.pdf",
    });

    renderPage();
    await waitForForm();
    await fillForm({ title: "Paper T", doi: "10.1000/dup" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });
    await screen.findByText(/uploaded and queued/i);

    // Sanity: while on the success screen, the form-mode submit button is gone.
    expect(
      screen.queryByRole("button", { name: /upload paper/i }),
    ).not.toBeInTheDocument();

    // Click "Upload Another"
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload another/i }));
    });

    // Success screen is gone and the editable form is rendered again.
    expect(screen.queryByText(/uploaded and queued/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /upload paper/i }),
    ).toBeInTheDocument();

    // Inputs reset to initial: empty title, and the selected-file state cleared
    // (the "<name> (<size> MB)" summary line that only renders when
    // selectedFile is set is gone — the React-observable signal of reset).
    expect((screen.getByLabelText(/title/i) as HTMLInputElement).value).toBe("");
    expect(screen.queryByText(/x\.pdf \(/i)).not.toBeInTheDocument();
    // A fresh form with empty title + no selected file leaves submit disabled.
    expect(
      screen.getByRole("button", { name: /upload paper/i }),
    ).toBeDisabled();
  });
});

describe("ExpertPaperUploadPage — recoverable error phase (issue #235)", () => {
  beforeEach(resetApiMocks);

  it("Try again returns the error phase to idle, re-enables inputs, preserves form values", async () => {
    // A non-DOI structured failure freezes the form in the error phase. The
    // "Try again" control must return it to idle WITHOUT wiping the entered
    // metadata or selected file (distinct from "Upload Another"'s full reset).
    mockRequestUrl.mockRejectedValue(
      apiErr(422, "INVALID_FILENAME", "Filename has invalid characters."),
    );

    renderPage();
    await waitForForm();
    await fillForm({ title: "Paper T", doi: "10.1000/abc123" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    // Error banner is shown with the surfaced backend message.
    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("Filename has invalid characters.");

    // While in error phase, inputs are disabled (frozen form).
    expect(screen.getByLabelText(/title/i)).toBeDisabled();

    // Click "Try again".
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    });

    // Banner cleared, inputs re-enabled.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    const titleInput = screen.getByLabelText(/title/i) as HTMLInputElement;
    expect(titleInput).not.toBeDisabled();

    // Form VALUES preserved (this is the distinction from Upload Another).
    expect(titleInput.value).toBe("Paper T");
    expect((screen.getByLabelText(/doi/i) as HTMLInputElement).value).toBe(
      "10.1000/abc123",
    );
    // Selected file preserved: the "<name> (<size> MB)" summary still renders.
    expect(screen.getByText(/x\.pdf \(/i)).toBeInTheDocument();

    // Submit re-enabled (all required fields still satisfied).
    expect(screen.getByRole("button", { name: /upload paper/i })).toBeEnabled();
  });

  it("surfaces the message for a non-DOI structured error thrown as ApiError", async () => {
    // Replicates a real transport throw: the shared typed ApiError carrying
    // status+code (issue #283).
    mockRequestUrl.mockRejectedValue(
      apiErr(503, "QUEUE_UNAVAILABLE", "Queue unavailable, retry shortly."),
    );

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/abc123" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("Queue unavailable, retry shortly.");
  });
});

describe("ExpertPaperUploadPage — Applicable population (FR-EXPV-05 ext.)", () => {
  beforeEach(resetApiMocks);

  function mockSuccessfulUpload() {
    mockRequestUrl.mockResolvedValue({
      id: "p-1",
      upload_url: "https://s/upload",
      storage_path: "papers/p-1/x.pdf",
      expires_at: "2026-04-15T12:00:00Z",
    });
    mockUploadFile.mockResolvedValue(undefined);
    mockCompleteUpload.mockResolvedValue({
      id: "p-1",
      review_status: "pending",
      storage_path: "papers/p-1/x.pdf",
    });
  }

  it("renders the Applicable population select with Male/Female/Both, default Both", async () => {
    renderPage();
    await waitForForm();

    const select = screen.getByLabelText(/applicable population/i) as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    expect(select.value).toBe("both");

    const options = Array.from(select.options).map((o) => o.textContent);
    expect(options).toEqual(["Male", "Female", "Both"]);
  });

  it("includes the selected sex_applicability in the upload payload", async () => {
    mockSuccessfulUpload();

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/abc123" });

    const select = screen.getByLabelText(/applicable population/i);
    await act(async () => {
      fireEvent.change(select, { target: { value: "female" } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(mockRequestUrl).toHaveBeenCalled());
    expect(mockRequestUrl).toHaveBeenCalledWith(
      expect.objectContaining({ sex_applicability: "female" }),
    );
  });

  it("defaults sex_applicability to both in the upload payload", async () => {
    mockSuccessfulUpload();

    renderPage();
    await waitForForm();
    await fillForm({ doi: "10.1000/abc123" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(mockRequestUrl).toHaveBeenCalled());
    expect(mockRequestUrl).toHaveBeenCalledWith(
      expect.objectContaining({ sex_applicability: "both" }),
    );
  });
});
