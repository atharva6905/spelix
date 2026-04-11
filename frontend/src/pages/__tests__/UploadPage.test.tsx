import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import UploadPage, { validateDuration } from "@/pages/UploadPage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  },
}));

const mockCreateAnalysis = vi.fn();
const mockStartAnalysis = vi.fn();

vi.mock("@/api/analyses", () => ({
  createAnalysis: (...args: unknown[]) => mockCreateAnalysis(...args),
  startAnalysis: (...args: unknown[]) => mockStartAnalysis(...args),
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

// ---------------------------------------------------------------------------
// XMLHttpRequest mock — captures the in-flight upload so tests can drive
// progress / load / error events. The frontend uses XHR (not tus-js-client
// or fetch) for the REST PUT to Supabase's signed upload URL because XHR
// is the only browser API that exposes upload progress events.
// ---------------------------------------------------------------------------

type MockXhrInstance = {
  open: ReturnType<typeof vi.fn>;
  setRequestHeader: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  abort: ReturnType<typeof vi.fn>;
  upload: { addEventListener: ReturnType<typeof vi.fn> };
  onload: (() => void) | null;
  onerror: (() => void) | null;
  status: number;
  statusText: string;
  // Test helpers
  _openCalls: unknown[][];
  _sendCalls: unknown[][];
  _triggerProgress: (loaded: number, total: number) => void;
  _triggerLoad: (status?: number) => void;
  _triggerError: () => void;
};

let lastMockXhr: MockXhrInstance | null = null;

function makeMockXhr(): MockXhrInstance {
  const uploadListeners: Record<string, ((e: ProgressEvent) => void)[]> = {};
  const openCalls: unknown[][] = [];
  const sendCalls: unknown[][] = [];

  const xhr: MockXhrInstance = {
    open: vi.fn((...args: unknown[]) => {
      openCalls.push(args);
    }),
    setRequestHeader: vi.fn(),
    send: vi.fn((...args: unknown[]) => {
      sendCalls.push(args);
    }),
    abort: vi.fn(),
    upload: {
      addEventListener: vi.fn((event: string, cb: (e: ProgressEvent) => void) => {
        uploadListeners[event] = uploadListeners[event] ?? [];
        uploadListeners[event].push(cb);
      }),
    },
    onload: null,
    onerror: null,
    status: 0,
    statusText: "",
    _openCalls: openCalls,
    _sendCalls: sendCalls,
    _triggerProgress(loaded: number, total: number) {
      const ev = { lengthComputable: true, loaded, total } as unknown as ProgressEvent;
      uploadListeners["progress"]?.forEach((cb) => cb(ev));
    },
    _triggerLoad(status = 200) {
      xhr.status = status;
      xhr.statusText = status >= 200 && status < 300 ? "OK" : "Error";
      xhr.onload?.();
    },
    _triggerError() {
      xhr.onerror?.();
    },
  };
  return xhr;
}

vi.stubGlobal(
  "XMLHttpRequest",
  vi.fn(function () {
    lastMockXhr = makeMockXhr();
    return lastMockXhr;
  }),
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderUploadPage() {
  return render(
    <MemoryRouter>
      <UploadPage />
    </MemoryRouter>,
  );
}

/** Returns a mock File whose size is under 50 MB. */
function makeVideoFile(name = "squat.mp4", size = 1024) {
  const file = new File(["x".repeat(Math.min(size, 100))], name, {
    type: "video/mp4",
  });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

// ---------------------------------------------------------------------------
// validateDuration unit tests (B-050)
// ---------------------------------------------------------------------------

describe("validateDuration", () => {
  function mockVideoElement(duration: number) {
    const listeners: Record<string, (() => void)[]> = {};
    const video = {
      duration,
      src: "",
      addEventListener: vi.fn((event: string, cb: () => void) => {
        listeners[event] = listeners[event] ?? [];
        listeners[event].push(cb);
      }),
      _trigger(event: string) {
        listeners[event]?.forEach((cb) => cb());
      },
    };

    vi.spyOn(document, "createElement").mockImplementationOnce(
      (tag: string) => {
        if (tag === "video") return video as unknown as HTMLElement;
        return document.createElement(tag);
      },
    );

    const mockUrl = "blob:mock-url";
    vi.spyOn(URL, "createObjectURL").mockReturnValueOnce(mockUrl);
    const revokespy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    return { video, revokespy };
  }

  it("returns null for a 10s video (normal mode)", async () => {
    const { video } = mockVideoElement(10);
    const file = makeVideoFile();
    const promise = validateDuration(file, false);
    video._trigger("loadedmetadata");
    const result = await promise;
    expect(result).toBeNull();
  });

  it("rejects video shorter than 2 seconds", async () => {
    const { video } = mockVideoElement(1);
    const file = makeVideoFile();
    const promise = validateDuration(file, false);
    video._trigger("loadedmetadata");
    const result = await promise;
    expect(result).toMatch(/too short/i);
  });

  it("rejects video longer than 40s in normal mode", async () => {
    const { video } = mockVideoElement(45);
    const file = makeVideoFile();
    const promise = validateDuration(file, false);
    video._trigger("loadedmetadata");
    const result = await promise;
    expect(result).toMatch(/too long/i);
    expect(result).toMatch(/40/);
  });

  it("accepts video up to 40s in normal mode", async () => {
    const { video } = mockVideoElement(40);
    const file = makeVideoFile();
    const promise = validateDuration(file, false);
    video._trigger("loadedmetadata");
    const result = await promise;
    expect(result).toBeNull();
  });

  it("accepts video up to 120s in extended mode", async () => {
    const { video } = mockVideoElement(120);
    const file = makeVideoFile();
    const promise = validateDuration(file, true);
    video._trigger("loadedmetadata");
    const result = await promise;
    expect(result).toBeNull();
  });

  it("rejects video longer than 120s in extended mode", async () => {
    const { video } = mockVideoElement(121);
    const file = makeVideoFile();
    const promise = validateDuration(file, true);
    video._trigger("loadedmetadata");
    const result = await promise;
    expect(result).toMatch(/2 minutes/i);
  });

  it("accepts video between 40s and 120s in extended mode", async () => {
    const { video } = mockVideoElement(60);
    const file = makeVideoFile();
    const promise = validateDuration(file, true);
    video._trigger("loadedmetadata");
    const result = await promise;
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// UploadPage render / interaction tests
// ---------------------------------------------------------------------------

// Track active createElement spy for cleanup
let activeCreateElementSpy: ReturnType<typeof vi.spyOn> | null = null;

describe("UploadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastMockXhr = null;
  });

  afterEach(() => {
    if (activeCreateElementSpy) {
      activeCreateElementSpy.mockRestore();
      activeCreateElementSpy = null;
    }
  });

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

    const variantSelect = screen.getByLabelText(/exercise variant/i);
    expect(variantSelect).toBeInTheDocument();

    const typeSelect = screen.getByLabelText(/exercise type/i);
    fireEvent.change(typeSelect, { target: { value: "squat" } });

    const squatOptions = Array.from(
      variantSelect.querySelectorAll("option"),
    ).map((o) => o.value);
    expect(squatOptions).toContain("high_bar");
    expect(squatOptions).toContain("low_bar");

    fireEvent.change(typeSelect, { target: { value: "bench" } });
    const benchOptions = Array.from(
      variantSelect.querySelectorAll("option"),
    ).map((o) => o.value);
    expect(benchOptions).toContain("flat");
    expect(benchOptions).toContain("incline");
    expect(benchOptions).toContain("decline");

    fireEvent.change(typeSelect, { target: { value: "deadlift" } });
    const dlOptions = Array.from(variantSelect.querySelectorAll("option")).map(
      (o) => o.value,
    );
    expect(dlOptions).toContain("conventional");
    expect(dlOptions).toContain("sumo");
    expect(dlOptions).toContain("romanian");
  });

  // B-056: upload button must have HTML `disabled` attribute (not just aria-disabled)
  it("upload button is HTML-disabled when exercise type is not selected", () => {
    renderUploadPage();
    const button = screen.getByRole("button", { name: /upload/i });
    expect(button).toBeDisabled();
  });

  it("upload button is HTML-disabled when only exercise type is selected (no variant)", () => {
    renderUploadPage();
    const typeSelect = screen.getByLabelText(/exercise type/i);
    fireEvent.change(typeSelect, { target: { value: "squat" } });

    const button = screen.getByRole("button", { name: /upload/i });
    expect(button).toBeDisabled();
  });

  it("upload button is HTML-disabled when type+variant selected but no file", () => {
    renderUploadPage();
    const typeSelect = screen.getByLabelText(/exercise type/i);
    fireEvent.change(typeSelect, { target: { value: "squat" } });
    const variantSelect = screen.getByLabelText(/exercise variant/i);
    fireEvent.change(variantSelect, { target: { value: "high_bar" } });

    const button = screen.getByRole("button", { name: /upload/i });
    expect(button).toBeDisabled();
  });

  it("upload button still has aria-disabled until both type AND variant selected", () => {
    renderUploadPage();
    const button = screen.getByRole("button", { name: /upload/i });

    expect(button).toHaveAttribute("aria-disabled", "true");

    const typeSelect = screen.getByLabelText(/exercise type/i);
    fireEvent.change(typeSelect, { target: { value: "squat" } });
    expect(button).toHaveAttribute("aria-disabled", "true");

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
    expect(accept).toMatch(/mp4|mov|webm/);
  });

  it("displays filming guidance text", () => {
    renderUploadPage();
    expect(screen.getByText(/filming guidance/i)).toBeInTheDocument();
    const guidanceElements = screen.getAllByText(/camera|side|hip/i);
    expect(guidanceElements.length).toBeGreaterThan(0);
  });

  it("displays exercise-specific filming guidance when exercise type is selected", () => {
    renderUploadPage();
    const typeSelect = screen.getByLabelText(/exercise type/i);
    fireEvent.change(typeSelect, { target: { value: "squat" } });
    expect(screen.getByText(/for squat:/i)).toBeInTheDocument();
  });

  it("shows selected filename and size when a valid file is chosen (no duration error)", async () => {
    renderUploadPage();

    // Patch duration validation to always pass in this test by providing a
    // video element mock that reports a valid 10s duration
    const listeners: Record<string, (() => void)[]> = {};
    const mockVideo = {
      duration: 10,
      src: "",
      addEventListener: vi.fn((event: string, cb: () => void) => {
        listeners[event] = listeners[event] ?? [];
        listeners[event].push(cb);
      }),
    };
    vi.spyOn(document, "createElement").mockImplementationOnce((tag) => {
      if (tag === "video") return mockVideo as unknown as HTMLElement;
      return document.createElement(tag);
    });
    vi.spyOn(URL, "createObjectURL").mockReturnValueOnce("blob:mock");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    const fileInput = screen.getByLabelText(/video file/i);
    const file = makeVideoFile("my-squat.mp4");
    Object.defineProperty(fileInput, "files", {
      value: [file],
      configurable: true,
    });

    // Fire change and then trigger loadedmetadata
    await act(async () => {
      fireEvent.change(fileInput);
      listeners["loadedmetadata"]?.forEach((cb) => cb());
    });

    expect(screen.getByText(/my-squat\.mp4/i)).toBeInTheDocument();
  });

  // B-050: duration errors are displayed
  it("shows duration error for a >40s video and button stays disabled", async () => {
    renderUploadPage();

    // Select type + variant first
    fireEvent.change(screen.getByLabelText(/exercise type/i), {
      target: { value: "squat" },
    });
    fireEvent.change(screen.getByLabelText(/exercise variant/i), {
      target: { value: "high_bar" },
    });

    const listeners: Record<string, (() => void)[]> = {};
    const mockVideo = {
      duration: 45,
      src: "",
      addEventListener: vi.fn((event: string, cb: () => void) => {
        listeners[event] = listeners[event] ?? [];
        listeners[event].push(cb);
      }),
    };
    vi.spyOn(document, "createElement").mockImplementationOnce((tag) => {
      if (tag === "video") return mockVideo as unknown as HTMLElement;
      return document.createElement(tag);
    });
    vi.spyOn(URL, "createObjectURL").mockReturnValueOnce("blob:mock");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    const fileInput = screen.getByLabelText(/video file/i);
    Object.defineProperty(fileInput, "files", {
      value: [makeVideoFile("long.mp4")],
      configurable: true,
    });

    await act(async () => {
      fireEvent.change(fileInput);
      listeners["loadedmetadata"]?.forEach((cb) => cb());
    });

    expect(screen.getByRole("alert")).toHaveTextContent(/too long/i);
    expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
  });

  // ---------------------------------------------------------------------------
  // Helper: installs a persistent createElement spy that intercepts "video"
  // tags only, so React's own DOM ops pass through unaffected.
  // Returns { listeners, restore } where listeners accumulates event callbacks
  // registered on the mock video element.
  // ---------------------------------------------------------------------------
  function setupVideoElementMock(duration: number) {
    const listeners: Record<string, (() => void)[]> = {};
    const mockVideo = {
      duration,
      src: "",
      addEventListener: vi.fn((event: string, cb: () => void) => {
        listeners[event] = listeners[event] ?? [];
        listeners[event].push(cb);
      }),
    };

    // Capture from the prototype (never gets wrapped by vi.spyOn which replaces
    // the instance property, not the prototype method) to avoid infinite recursion.
    const originalCreateElement = Document.prototype.createElement.bind(document);
    activeCreateElementSpy = vi
      .spyOn(document, "createElement")
      .mockImplementation((tag: string, ...args: unknown[]) => {
        if (tag === "video") return mockVideo as unknown as HTMLElement;
        return originalCreateElement(tag, ...(args as []));
      });

    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    return { listeners };
  }

  /** Selects exercise type+variant, attaches file, and triggers loadedmetadata. */
  async function setupFormWithFile(
    videoListeners: Record<string, (() => void)[]>,
    file: File,
  ) {
    fireEvent.change(screen.getByLabelText(/exercise type/i), {
      target: { value: "squat" },
    });
    fireEvent.change(screen.getByLabelText(/exercise variant/i), {
      target: { value: "high_bar" },
    });

    const fileInput = screen.getByLabelText(/video file/i);
    Object.defineProperty(fileInput, "files", {
      value: [file],
      configurable: true,
    });

    // First act: fire change so validateDuration's createElement runs and
    // registers the loadedmetadata listener.
    await act(async () => { fireEvent.change(fileInput); });

    // Second act: fire loadedmetadata to resolve the validateDuration promise.
    await act(async () => {
      videoListeners["loadedmetadata"]?.forEach((cb) => cb());
    });
  }

  // B-044, FR-UPLD-12: REST PUT upload to Supabase signed upload URL.
  // Regression test for the production outage where the frontend used
  // tus-js-client (TUS protocol) against a REST signed upload URL —
  // Supabase rejected with 400 "headers must have required property
  // 'authorization'" because TUS and REST signed upload are completely
  // different protocols.
  it("PUTs the file to the upload_url returned by createAnalysis", async () => {
    const uploadUrl = "https://storage.example.com/object/upload/sign/videos/x?token=abc";
    mockCreateAnalysis.mockResolvedValue({
      id: "analysis-123",
      upload_url: uploadUrl,
      status: "queued",
      expires_at: "2026-01-01T00:00:00Z",
    });
    mockStartAnalysis.mockResolvedValue({ id: "analysis-123", status: "queued" });

    const { listeners } = setupVideoElementMock(10);
    renderUploadPage();
    await setupFormWithFile(listeners, makeVideoFile("test.mp4"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(mockCreateAnalysis).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(lastMockXhr).not.toBeNull());

    // The XHR must PUT to the signed upload URL with the file as the body.
    const xhr = lastMockXhr!;
    expect(xhr._openCalls.length).toBe(1);
    expect(xhr._openCalls[0][0]).toBe("PUT");
    expect(xhr._openCalls[0][1]).toBe(uploadUrl);
    expect(xhr.send).toHaveBeenCalledTimes(1);
    // The body must be the File itself (not a FormData or arraybuffer wrapper).
    const sentBody = xhr._sendCalls[0][0];
    expect(sentBody).toBeInstanceOf(File);
    // Content-Type header set to the file's MIME type so Supabase stores it correctly.
    expect(xhr.setRequestHeader).toHaveBeenCalledWith(
      "Content-Type",
      "video/mp4",
    );
  });

  it("updates uploadProgress state on XHR upload progress events", async () => {
    mockCreateAnalysis.mockResolvedValue({
      id: "analysis-abc",
      upload_url: "https://storage.example.com/object/upload/sign/videos/x?token=abc",
      status: "queued",
      expires_at: "2026-01-01T00:00:00Z",
    });
    mockStartAnalysis.mockResolvedValue({ id: "analysis-abc", status: "queued" });

    const { listeners } = setupVideoElementMock(10);
    renderUploadPage();
    await setupFormWithFile(listeners, makeVideoFile("test.mp4"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(lastMockXhr).not.toBeNull());

    // Simulate 50% progress via the XHR upload.progress event
    await act(async () => {
      lastMockXhr!._triggerProgress(500, 1000);
    });

    // Progress bar should appear with 50% (appears in both label and counter spans)
    expect(screen.getAllByText(/50%/).length).toBeGreaterThan(0);
  });

  it("navigates to analysis page only after startAnalysis succeeds", async () => {
    mockCreateAnalysis.mockResolvedValue({
      id: "analysis-xyz",
      upload_url: "https://storage.example.com/object/upload/sign/videos/x?token=abc",
      status: "queued",
      expires_at: "2026-01-01T00:00:00Z",
    });
    mockStartAnalysis.mockResolvedValue({ id: "analysis-xyz", status: "queued" });

    const { listeners } = setupVideoElementMock(10);
    renderUploadPage();
    await setupFormWithFile(listeners, makeVideoFile("test.mp4"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(lastMockXhr).not.toBeNull());

    // Navigation should NOT have happened yet (XHR has not completed)
    expect(mockNavigate).not.toHaveBeenCalled();

    // Trigger XHR onload with status 200 (Supabase REST upload success)
    await act(async () => {
      lastMockXhr!._triggerLoad(200);
    });

    await waitFor(() => expect(mockStartAnalysis).toHaveBeenCalledWith("analysis-xyz"));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/analysis/analysis-xyz"));
  });

  it("surfaces an error when XHR upload fails with non-2xx status", async () => {
    mockCreateAnalysis.mockResolvedValue({
      id: "analysis-fail",
      upload_url: "https://storage.example.com/object/upload/sign/videos/x?token=abc",
      status: "queued",
      expires_at: "2026-01-01T00:00:00Z",
    });

    const { listeners } = setupVideoElementMock(10);
    renderUploadPage();
    await setupFormWithFile(listeners, makeVideoFile("test.mp4"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await waitFor(() => expect(lastMockXhr).not.toBeNull());

    // Simulate Supabase Storage rejecting the upload (400, 403, etc.)
    await act(async () => {
      lastMockXhr!._triggerLoad(403);
    });

    // Error alert should show; startAnalysis must NOT be called.
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(mockStartAnalysis).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
