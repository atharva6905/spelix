/**
 * Branch coverage tests for expert.ts — covers expertFetch error, 204,
 * and auth failure branches plus uploadPaperFile XHR branches.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getExpertQueue,
  getExpertAnalysis,
  submitAnnotation,
  getAnnotations,
  requestPaperUploadUrl,
  completePaperUpload,
  reviewPaper,
  labelGoldenDataset,
  uploadPaperFile,
  type AnnotationCreate,
} from "@/api/expert";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "expert-token" } },
      }),
    },
  },
}));

import { supabase } from "@/lib/supabase";

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// expertFetch — error branch
// ---------------------------------------------------------------------------

describe("expertFetch error branch", () => {
  it("throws error object with status on non-ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ message: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getExpertAnalysis("no-id")).rejects.toMatchObject({ status: 404 });
  });

  it("throws with body.detail when present", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { code: "NOT_FOUND" } }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(getExpertAnalysis("no-id")).rejects.toMatchObject({ code: "NOT_FOUND" });
  });

  it("throws Not authenticated when no session", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValueOnce({ data: { session: null }, error: null } as Awaited<ReturnType<typeof supabase.auth.getSession>>);
    await expect(getExpertQueue()).rejects.toThrow("Not authenticated");
  });

  it("handles body parse failure gracefully on error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not json", { status: 500 }),
    );
    await expect(getExpertAnalysis("id")).rejects.toMatchObject({ status: 500 });
  });
});

// ---------------------------------------------------------------------------
// expertFetch — 204 branch
// ---------------------------------------------------------------------------

describe("expertFetch 204 branch", () => {
  it("returns undefined on 204 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    // submitAnnotation would typically use POST — use getAnnotations for a GET to trigger 204
    // Actually any route: use reviewPaper which could return 204
    const result = await reviewPaper("doc-1", { decision: "reviewed_approved" });
    expect(result).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// getExpertQueue — query params
// ---------------------------------------------------------------------------

describe("getExpertQueue", () => {
  it("passes limit, offset, queueType as params", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await getExpertQueue(10, 5, "flagged");
    expect(capturedUrl).toContain("limit=10");
    expect(capturedUrl).toContain("offset=5");
    expect(capturedUrl).toContain("queue_type=flagged");
  });

  it("uses default values", async () => {
    let capturedUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    });
    await getExpertQueue();
    expect(capturedUrl).toContain("limit=20");
    expect(capturedUrl).toContain("offset=0");
    expect(capturedUrl).toContain("queue_type=all");
  });
});

// ---------------------------------------------------------------------------
// submitAnnotation
// ---------------------------------------------------------------------------

describe("submitAnnotation", () => {
  it("POSTs annotation and returns response", async () => {
    const annotation: AnnotationCreate = {
      issues_identified: {},
      coaching_quality_score: 4,
      movement_advice_accurate: true,
      engagement_advice_accurate: null,
      suggested_corrections: "Knees out",
      cited_sources: [],
      is_golden_label: false,
    };
    const resp = { id: "ann-1", analysis_id: "a1", annotator_id: "u1", ...annotation, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(resp), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await submitAnnotation("a1", annotation);
    expect(result.id).toBe("ann-1");
  });
});

// ---------------------------------------------------------------------------
// getAnnotations
// ---------------------------------------------------------------------------

describe("getAnnotations", () => {
  it("returns list of annotations", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await getAnnotations("a1");
    expect(result).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// requestPaperUploadUrl / completePaperUpload
// ---------------------------------------------------------------------------

describe("requestPaperUploadUrl", () => {
  it("returns upload URL on success", async () => {
    const resp = { id: "p1", upload_url: "https://s3/url", storage_path: "papers/p1.pdf", expires_at: "2026-01-01T01:00:00Z" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(resp), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await requestPaperUploadUrl({ title: "Test paper", filename: "test.pdf", file_size_bytes: 1024 });
    expect(result.id).toBe("p1");
  });
});

describe("completePaperUpload", () => {
  it("returns complete response on success", async () => {
    const resp = { id: "p1", review_status: "pending" as const, storage_path: "papers/p1.pdf" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(resp), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const result = await completePaperUpload("p1");
    expect(result.review_status).toBe("pending");
  });
});

// ---------------------------------------------------------------------------
// labelGoldenDataset
// ---------------------------------------------------------------------------

describe("labelGoldenDataset", () => {
  it("returns updated golden dataset flag", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ id: "a1", is_golden_dataset: true }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const result = await labelGoldenDataset("a1", true);
    expect(result.is_golden_dataset).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// uploadPaperFile — XHR branches
// ---------------------------------------------------------------------------

describe("uploadPaperFile", () => {
  // Stores the last XHR instance created so tests can fire events on it
  let xhrInstance: {
    open: ReturnType<typeof vi.fn>;
    setRequestHeader: ReturnType<typeof vi.fn>;
    send: ReturnType<typeof vi.fn>;
    status: number;
    upload: { addEventListener: ReturnType<typeof vi.fn> };
    addEventListener: ReturnType<typeof vi.fn>;
    _fire(event: string, data?: unknown): void;
    _fireUpload(event: string, data?: unknown): void;
  };

  function setupXHRMock(xhrStatus: number) {
    const handlers: Record<string, (data: unknown) => void> = {};
    const uploadHandlers: Record<string, (data: unknown) => void> = {};

    class MockXHR {
      open = vi.fn();
      setRequestHeader = vi.fn();
      send = vi.fn();
      status = xhrStatus;
      upload = {
        addEventListener: vi.fn((event: string, handler: (e: unknown) => void) => {
          uploadHandlers[event] = handler;
        }),
      };
      addEventListener(event: string, handler: (e: unknown) => void) {
        handlers[event] = handler;
      }
    }

    const instance = new MockXHR() as InstanceType<typeof MockXHR> & {
      _fire(event: string, data?: unknown): void;
      _fireUpload(event: string, data?: unknown): void;
    };

    (instance as { _fire: (event: string, data?: unknown) => void })._fire = (event, data) => handlers[event]?.(data);
    (instance as { _fireUpload: (event: string, data?: unknown) => void })._fireUpload = (event, data) => uploadHandlers[event]?.(data);

    vi.stubGlobal("XMLHttpRequest", class { constructor() { return instance; } });

    xhrInstance = instance as typeof xhrInstance;
    return instance;
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves on successful upload (status 200)", async () => {
    setupXHRMock(200);
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });

    const promise = uploadPaperFile("https://upload/url", file, vi.fn());

    xhrInstance._fire("load");

    await expect(promise).resolves.toBeUndefined();
  });

  it("rejects on failed upload (status 500)", async () => {
    setupXHRMock(500);
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });

    const promise = uploadPaperFile("https://upload/url", file, vi.fn());

    xhrInstance._fire("load");

    await expect(promise).rejects.toThrow("upload failed: HTTP 500");
  });

  it("rejects on network error", async () => {
    setupXHRMock(200);
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });

    const promise = uploadPaperFile("https://upload/url", file, vi.fn());

    xhrInstance._fire("error");

    await expect(promise).rejects.toThrow("upload failed: network error");
  });

  it("rejects on abort", async () => {
    setupXHRMock(200);
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });

    const promise = uploadPaperFile("https://upload/url", file, vi.fn());

    xhrInstance._fire("abort");

    await expect(promise).rejects.toThrow("upload aborted");
  });

  it("calls onProgress when length is computable", async () => {
    setupXHRMock(200);
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });
    const onProgress = vi.fn();

    const promise = uploadPaperFile("https://upload/url", file, onProgress);

    xhrInstance._fireUpload("progress", { lengthComputable: true, loaded: 50, total: 100 });

    expect(onProgress).toHaveBeenCalledWith(50);

    xhrInstance._fire("load");
    await promise;
  });

  it("does NOT call onProgress when length is not computable", async () => {
    setupXHRMock(200);
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });
    const onProgress = vi.fn();

    const promise = uploadPaperFile("https://upload/url", file, onProgress);

    xhrInstance._fireUpload("progress", { lengthComputable: false, loaded: 50, total: 100 });

    expect(onProgress).not.toHaveBeenCalled();

    xhrInstance._fire("load");
    await promise;
  });
});
