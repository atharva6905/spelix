import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

const mockFetch = vi.fn();

import {
  completePaperUpload,
  requestPaperUploadUrl,
  uploadPaperFile,
  ExpertApiError,
  isExpertApiError,
} from "@/api/expert";

interface MockXhr {
  upload: {
    listeners: Record<string, (e: ProgressEvent) => void>;
    addEventListener: (e: string, cb: (e: ProgressEvent) => void) => void;
  };
  listeners: Record<string, (e: Event) => void>;
  open: ReturnType<typeof vi.fn>;
  setRequestHeader: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  addEventListener: (e: string, cb: (e: Event) => void) => void;
  status: number;
  _triggerProgress: (loaded: number, total: number) => void;
  _triggerLoad: (status: number) => void;
  _triggerError: () => void;
}

let lastXhr: MockXhr;

function makeMockXhr(): MockXhr {
  const xhr: MockXhr = {
    upload: {
      listeners: {},
      addEventListener(e, cb) {
        this.listeners[e] = cb;
      },
    },
    listeners: {},
    open: vi.fn(),
    setRequestHeader: vi.fn(),
    send: vi.fn(),
    addEventListener(e, cb) {
      this.listeners[e] = cb;
    },
    status: 0,
    _triggerProgress(loaded, total) {
      const fn = this.upload.listeners.progress;
      if (fn)
        fn({ loaded, total, lengthComputable: true } as unknown as ProgressEvent);
    },
    _triggerLoad(status) {
      this.status = status;
      this.listeners.load?.(new Event("load"));
    },
    _triggerError() {
      this.listeners.error?.(new Event("error"));
    },
  };
  return xhr;
}

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal("fetch", mockFetch);
  vi.stubGlobal(
    "XMLHttpRequest",
    vi.fn(function () {
      lastXhr = makeMockXhr();
      return lastXhr;
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestPaperUploadUrl", () => {
  it("POSTs metadata + filename + size, returns signed URL", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "paper-1",
          upload_url: "https://s/upload",
          storage_path: "papers/paper-1/x.pdf",
          expires_at: "2026-04-15T12:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const res = await requestPaperUploadUrl({
      title: "t",
      doi: "10.1000/abc123",
      filename: "x.pdf",
      file_size_bytes: 1000,
    });

    expect(res.upload_url).toBe("https://s/upload");
    expect(res.storage_path).toBe("papers/paper-1/x.pdf");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/expert/papers"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      }),
    );
  });
});

describe("uploadPaperFile", () => {
  it("PUTs the file via XHR and reports progress", async () => {
    const file = new File([new Uint8Array(1024)], "x.pdf", {
      type: "application/pdf",
    });
    const onProgress = vi.fn();

    const p = uploadPaperFile("https://s/upload", file, onProgress);

    await new Promise((r) => setTimeout(r, 0));
    lastXhr._triggerProgress(512, 1024);
    lastXhr._triggerLoad(200);

    await p;

    expect(lastXhr.open).toHaveBeenCalledWith("PUT", "https://s/upload");
    expect(lastXhr.setRequestHeader).toHaveBeenCalledWith(
      "Content-Type",
      "application/pdf",
    );
    expect(lastXhr.send).toHaveBeenCalledWith(file);
    expect(onProgress).toHaveBeenCalledWith(50);
  });

  it("rejects on XHR error", async () => {
    const file = new File([new Uint8Array(10)], "x.pdf", {
      type: "application/pdf",
    });
    const p = uploadPaperFile("https://s/upload", file, () => {});

    await new Promise((r) => setTimeout(r, 0));
    lastXhr._triggerError();

    await expect(p).rejects.toThrow(/upload failed/i);
  });

  it("rejects on non-2xx HTTP status", async () => {
    const file = new File([new Uint8Array(10)], "x.pdf", {
      type: "application/pdf",
    });
    const p = uploadPaperFile("https://s/upload", file, () => {});

    await new Promise((r) => setTimeout(r, 0));
    lastXhr._triggerLoad(403);

    await expect(p).rejects.toThrow(/HTTP 403/);
  });
});

describe("expertFetch — ExpertApiError unwrap (issue #235)", () => {
  it("unwraps FastAPI {detail:{error:{code,message}}} into a real ExpertApiError", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: { error: { code: "INVALID_PDF", message: "Not a valid PDF." } },
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    const err = await completePaperUpload("p-1").then(
      () => null,
      (e) => e,
    );

    // It is a real thrown Error, not a hand-rolled object literal.
    expect(err).toBeInstanceOf(ExpertApiError);
    expect(err).toBeInstanceOf(Error);
    expect(isExpertApiError(err)).toBe(true);
    expect(err.status).toBe(422);
    expect(err.code).toBe("INVALID_PDF");
    expect(err.message).toBe("Not a valid PDF.");
    expect(err.detail).toEqual({ error: { code: "INVALID_PDF", message: "Not a valid PDF." } });
  });

  it("synthesizes a message from a Pydantic array detail (code undefined)", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: [
            { loc: ["body", "doi"], msg: "field required", type: "value_error.missing" },
          ],
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    const err = await completePaperUpload("p-1").then(
      () => null,
      (e) => e,
    );

    expect(isExpertApiError(err)).toBe(true);
    expect(err.status).toBe(422);
    expect(err.code).toBeUndefined();
    // First element's msg is surfaced.
    expect(err.message).toContain("field required");
    expect(err.detail).toEqual([
      { loc: ["body", "doi"], msg: "field required", type: "value_error.missing" },
    ]);
  });

  it("uses a string detail directly as the message", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Queue unavailable, retry shortly." }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const err = await completePaperUpload("p-1").then(
      () => null,
      (e) => e,
    );

    expect(isExpertApiError(err)).toBe(true);
    expect(err.status).toBe(503);
    expect(err.code).toBeUndefined();
    expect(err.message).toBe("Queue unavailable, retry shortly.");
  });

  it("falls back to a safe message on an empty/unparseable body", async () => {
    mockFetch.mockResolvedValueOnce(new Response("not json", { status: 500 }));

    const err = await completePaperUpload("p-1").then(
      () => null,
      (e) => e,
    );

    expect(isExpertApiError(err)).toBe(true);
    expect(err.status).toBe(500);
    expect(typeof err.message).toBe("string");
    expect(err.message.length).toBeGreaterThan(0);
  });

  it("isExpertApiError returns false for a bare object literal (drift guard)", () => {
    expect(isExpertApiError({ status: 409, error: { code: "X" } })).toBe(false);
    expect(isExpertApiError(new Error("plain"))).toBe(false);
  });
});

describe("completePaperUpload", () => {
  it("POSTs to /:id/complete and returns status", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "p-1",
          review_status: "pending",
          storage_path: "papers/p-1/x.pdf",
        }),
        { status: 200 },
      ),
    );

    const res = await completePaperUpload("p-1");
    expect(res.review_status).toBe("pending");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/expert/papers/p-1/complete"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
