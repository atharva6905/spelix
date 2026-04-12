import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ChatPanel from "@/components/ChatPanel";
import type { UseChatResult } from "@/hooks/useChat";

const mockUseChat = vi.fn<(id: string) => UseChatResult>();

vi.mock("@/hooks/useChat", () => ({
  useChat: (id: string) => mockUseChat(id),
}));

const ANALYSIS_ID = "analysis-abc-123";

function defaultChatResult(overrides: Partial<UseChatResult> = {}): UseChatResult {
  return {
    messages: [],
    isLoading: false,
    error: null,
    sendMessage: vi.fn(),
    ...overrides,
  };
}

describe("ChatPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseChat.mockReturnValue(defaultChatResult());
  });

  it("renders chat panel container", () => {
    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    expect(screen.getByTestId("chat-panel")).toBeInTheDocument();
  });

  it("renders input textarea and send button", () => {
    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send-button")).toBeInTheDocument();
  });

  it("renders user messages right-aligned", () => {
    mockUseChat.mockReturnValue(
      defaultChatResult({
        messages: [
          { id: "m1", role: "user", content: "Why knee cave?", created_at: "2026-04-12T10:00:00Z" },
        ],
      }),
    );

    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    expect(screen.getByTestId("chat-message-user")).toBeInTheDocument();
  });

  it("renders assistant messages left-aligned", () => {
    mockUseChat.mockReturnValue(
      defaultChatResult({
        messages: [
          { id: "m1", role: "assistant", content: "Weak glutes.", created_at: "2026-04-12T10:00:00Z" },
        ],
      }),
    );

    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    expect(screen.getByTestId("chat-message-assistant")).toBeInTheDocument();
  });

  it("disables send button when loading", () => {
    mockUseChat.mockReturnValue(defaultChatResult({ isLoading: true }));

    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    expect(screen.getByTestId("chat-send-button")).toBeDisabled();
  });

  it("disables send button when textarea is empty", () => {
    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    expect(screen.getByTestId("chat-send-button")).toBeDisabled();
  });

  it("calls sendMessage on Enter press and clears input", async () => {
    const sendMessage = vi.fn();
    mockUseChat.mockReturnValue(defaultChatResult({ sendMessage }));

    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "How to fix?" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: false });

    expect(sendMessage).toHaveBeenCalledWith("How to fix?");
    await waitFor(() => {
      expect((input as HTMLTextAreaElement).value).toBe("");
    });
  });

  it("does not send on Shift+Enter (allows newline)", () => {
    const sendMessage = vi.fn();
    mockUseChat.mockReturnValue(defaultChatResult({ sendMessage }));

    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, { target: { value: "line 1" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("renders error message when error is set", () => {
    mockUseChat.mockReturnValue(
      defaultChatResult({ error: "Network error" }),
    );

    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    expect(screen.getByTestId("chat-error")).toBeInTheDocument();
    expect(screen.getByText(/Network error/)).toBeInTheDocument();
  });

  it("renders messages-end marker for auto-scroll", () => {
    render(<ChatPanel analysisId={ANALYSIS_ID} />);
    expect(screen.getByTestId("chat-messages-end")).toBeInTheDocument();
  });
});
