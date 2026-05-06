import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useChat } from "@/hooks/useChat";

// Mock the API module
const mockGetChatHistory = vi.fn();
const mockSendChatMessage = vi.fn();

vi.mock("@/api/analyses", () => ({
  getChatHistory: (...args: unknown[]) => mockGetChatHistory(...args),
  sendChatMessage: (...args: unknown[]) => mockSendChatMessage(...args),
}));

const ANALYSIS_ID = "analysis-abc-123";

describe("useChat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetChatHistory.mockResolvedValue({ messages: [] });
  });

  it("loads chat history on mount", async () => {
    const existingMessages = [
      { id: "m1", role: "user", content: "Why knee cave?", created_at: "2026-04-12T10:00:00Z" },
      { id: "m2", role: "assistant", content: "Weak glutes.", created_at: "2026-04-12T10:00:01Z" },
    ];
    mockGetChatHistory.mockResolvedValue({ messages: existingMessages });

    const { result } = renderHook(() => useChat(ANALYSIS_ID));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    expect(mockGetChatHistory).toHaveBeenCalledWith(ANALYSIS_ID);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[1].role).toBe("assistant");
  });

  it("sendMessage appends optimistic user message and then assistant response", async () => {
    const assistantMsg = {
      id: "m2",
      role: "assistant",
      content: "Cue knees out.",
      created_at: "2026-04-12T10:00:01Z",
    };
    mockSendChatMessage.mockResolvedValue(assistantMsg);

    const { result } = renderHook(() => useChat(ANALYSIS_ID));

    // Wait for initial load
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // Send message
    await act(async () => {
      await result.current.sendMessage("How to fix knee cave?");
    });

    expect(mockSendChatMessage).toHaveBeenCalledWith(ANALYSIS_ID, "How to fix knee cave?");
    // Should have user message + assistant response
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("How to fix knee cave?");
    expect(result.current.messages[1].role).toBe("assistant");
    expect(result.current.messages[1].content).toBe("Cue knees out.");
  });

  it("sets isLoading during send", async () => {
    let resolvePromise: (value: unknown) => void;
    const pendingPromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    mockSendChatMessage.mockReturnValue(pendingPromise);

    const { result } = renderHook(() => useChat(ANALYSIS_ID));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // Start sending without awaiting
    act(() => {
      result.current.sendMessage("hello");
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve
    await act(async () => {
      resolvePromise!({
        id: "m2",
        role: "assistant",
        content: "hi",
        created_at: "2026-04-12T10:00:01Z",
      });
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("sets error on sendMessage failure and removes optimistic message", async () => {
    mockSendChatMessage.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useChat(ANALYSIS_ID));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.error).toBe("Network error");
    expect(result.current.isLoading).toBe(false);
    // Optimistic message should be removed on error
    expect(result.current.messages).toHaveLength(0);
  });

  it("ignores sendMessage when already loading", async () => {
    let resolvePromise: (value: unknown) => void;
    const pendingPromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    mockSendChatMessage.mockReturnValue(pendingPromise);

    const { result } = renderHook(() => useChat(ANALYSIS_ID));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // First send
    act(() => {
      result.current.sendMessage("first");
    });

    await waitFor(() => expect(result.current.isLoading).toBe(true));

    // Second send should be ignored
    await act(async () => {
      await result.current.sendMessage("second");
    });

    expect(mockSendChatMessage).toHaveBeenCalledTimes(1);

    // Cleanup
    await act(async () => {
      resolvePromise!({
        id: "m2",
        role: "assistant",
        content: "ok",
        created_at: "2026-04-12T10:00:01Z",
      });
    });
  });

  it("does not update state after unmount (cancelled history load)", async () => {
    let resolveFn!: (val: { messages: unknown[] }) => void;
    const pending = new Promise<{ messages: unknown[] }>((res) => { resolveFn = res; });
    mockGetChatHistory.mockReturnValue(pending);

    const { unmount, result } = renderHook(() => useChat(ANALYSIS_ID));

    // Unmount before history load resolves
    unmount();

    // Resolve after unmount — should not throw or update state
    resolveFn({ messages: [{ id: "m1", role: "user", content: "hi", created_at: "2026-04-12T10:00:00Z" }] });
    await Promise.resolve();

    // Messages should remain empty (cancelled)
    expect(result.current.messages).toHaveLength(0);
  });

  it("sets error as fallback message when non-Error is thrown in sendMessage", async () => {
    mockSendChatMessage.mockRejectedValue("plain string error");

    const { result } = renderHook(() => useChat(ANALYSIS_ID));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.error).toBe("Failed to send message");
  });
});
