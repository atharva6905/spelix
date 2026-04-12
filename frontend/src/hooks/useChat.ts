import { useState, useEffect, useCallback, useRef } from "react";
import type { ChatMessage } from "@/api/analyses";
import { getChatHistory, sendChatMessage } from "@/api/analyses";

export interface UseChatResult {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
}

export function useChat(analysisId: string): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(false);

  // Load history on mount
  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        const { messages: history } = await getChatHistory(analysisId);
        if (!cancelled) {
          setMessages(history);
        }
      } catch {
        // Silently fail on history load — empty chat is fine
      } finally {
        if (!cancelled) {
          setIsLoading(false);
          loadingRef.current = false;
        }
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  const sendMessageFn = useCallback(
    async (content: string) => {
      if (loadingRef.current) return;

      loadingRef.current = true;
      setIsLoading(true);
      setError(null);

      // Optimistic user message
      const optimisticMsg: ChatMessage = {
        id: `optimistic-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimisticMsg]);

      try {
        const assistantMsg = await sendChatMessage(analysisId, content);
        // Replace optimistic message with real user + assistant
        setMessages((prev) => {
          const withoutOptimistic = prev.filter((m) => m.id !== optimisticMsg.id);
          return [
            ...withoutOptimistic,
            { ...optimisticMsg, id: `user-${Date.now()}` },
            assistantMsg,
          ];
        });
      } catch (err) {
        // Remove optimistic message on error
        setMessages((prev) => prev.filter((m) => m.id !== optimisticMsg.id));
        setError(err instanceof Error ? err.message : "Failed to send message");
      } finally {
        setIsLoading(false);
        loadingRef.current = false;
      }
    },
    [analysisId],
  );

  return { messages, isLoading, error, sendMessage: sendMessageFn };
}
