import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import AnalysisStatusPage from "@/pages/AnalysisStatusPage";

// Use vi.hoisted so mocks are available when vi.mock factories run (hoisted above imports)
const {
  mockUnsubscribe,
  mockSubscribe,
  mockOn,
  mockChannel,
  channelInstance,
} = vi.hoisted(() => {
  const mockUnsubscribe = vi.fn().mockResolvedValue({ error: null });
  const mockSubscribe = vi.fn().mockReturnValue({ unsubscribe: mockUnsubscribe });
  const mockOn = vi.fn();
  const mockChannel = vi.fn();

  const channelInstance = {
    on: mockOn,
    subscribe: mockSubscribe,
    unsubscribe: mockUnsubscribe,
  };
  mockOn.mockReturnValue(channelInstance);
  mockChannel.mockReturnValue(channelInstance);

  return { mockUnsubscribe, mockSubscribe, mockOn, mockChannel, channelInstance };
});

vi.mock("@/lib/supabase", () => ({
  supabase: {
    channel: mockChannel,
    removeChannel: vi.fn().mockResolvedValue(undefined),
  },
}));

// Mock the analyses API
vi.mock("@/api/analyses", () => ({
  getAnalysisStatus: vi.fn().mockResolvedValue({
    id: "test-id",
    status: "processing",
    updated_at: new Date().toISOString(),
  }),
}));

function renderWithRouter(analysisId = "test-id") {
  return render(
    <MemoryRouter initialEntries={[`/analysis/${analysisId}`]}>
      <Routes>
        <Route path="/analysis/:id" element={<AnalysisStatusPage />} />
        <Route path="/results/:id" element={<div>Results Page</div>} />
        <Route path="/upload" element={<div>Upload Page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AnalysisStatusPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOn.mockReturnValue(channelInstance);
    mockChannel.mockReturnValue(channelInstance);
    mockSubscribe.mockReturnValue(channelInstance);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    renderWithRouter();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("displays user-facing label for processing status — never internal status string", async () => {
    const { getByText, queryByText } = renderWithRouter();

    // Simulate a Realtime update arriving
    await act(async () => {
      // Find the callback registered with .on()
      const onCall = mockOn.mock.calls[0];
      if (onCall) {
        const callback = onCall[2];
        callback({ new: { status: "processing", quality_gate_result: null } });
      }
    });

    expect(getByText("Analysing your form…")).toBeInTheDocument();
    expect(queryByText("processing")).not.toBeInTheDocument();
  });

  it("shows quality gate rejection with corrective guidance", async () => {
    renderWithRouter();

    await act(async () => {
      const onCall = mockOn.mock.calls[0];
      if (onCall) {
        const callback = onCall[2];
        callback({
          new: {
            status: "quality_gate_rejected",
            quality_gate_result: {
              checks: [
                {
                  name: "body_visibility",
                  passed: false,
                  user_message:
                    "Please ensure your full body is visible in the frame.",
                },
              ],
            },
          },
        });
      }
    });

    expect(
      screen.getByText("Video quality check failed"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Please ensure your full body is visible in the frame.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /upload/i })).toBeInTheDocument();
    expect(queryByText("quality_gate_rejected")).not.toBeInTheDocument();

    function queryByText(text: string) {
      return screen.queryByText(text);
    }
  });

  it("shows completed state with link to results page", async () => {
    renderWithRouter("test-id");

    await act(async () => {
      const onCall = mockOn.mock.calls[0];
      if (onCall) {
        const callback = onCall[2];
        callback({
          new: {
            status: "completed",
            quality_gate_result: null,
          },
        });
      }
    });

    expect(screen.getByText("Analysis complete")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /view results/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText("completed")).not.toBeInTheDocument();
  });

  it("shows failed state with retry information", async () => {
    renderWithRouter();

    await act(async () => {
      const onCall = mockOn.mock.calls[0];
      if (onCall) {
        const callback = onCall[2];
        callback({
          new: {
            status: "failed",
            quality_gate_result: null,
            retry_count: 1,
          },
        });
      }
    });

    expect(screen.getByText("Analysis failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.queryByText("failed")).not.toBeInTheDocument();
  });

  it("shows queued status with correct user-facing label", async () => {
    renderWithRouter();

    await act(async () => {
      const onCall = mockOn.mock.calls[0];
      if (onCall) {
        const callback = onCall[2];
        callback({
          new: { status: "queued", quality_gate_result: null },
        });
      }
    });

    expect(screen.getByText("Preparing to analyse…")).toBeInTheDocument();
    expect(screen.queryByText("queued")).not.toBeInTheDocument();
  });

  it("never displays raw internal status strings to users", async () => {
    renderWithRouter();

    const internalStatuses = [
      "queued",
      "quality_gate_pending",
      "quality_gate_rejected",
      "processing",
      "coaching",
      "completed",
      "failed",
    ];

    await act(async () => {
      const onCall = mockOn.mock.calls[0];
      if (onCall) {
        const callback = onCall[2];
        callback({ new: { status: "coaching", quality_gate_result: null } });
      }
    });

    for (const status of internalStatuses) {
      expect(screen.queryByText(status)).not.toBeInTheDocument();
    }
    expect(
      screen.getByText("Generating coaching feedback…"),
    ).toBeInTheDocument();
  });
});
