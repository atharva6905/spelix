import { useState, useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";

interface ChatPanelProps {
  analysisId: string;
}

export default function ChatPanel({ analysisId }: ChatPanelProps) {
  const { messages, isLoading, error, sendMessage } = useChat(analysisId);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages.length]);

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    sendMessage(trimmed);
    setInput("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div
      data-testid="chat-panel"
      className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
    >
      <h3 className="mb-4 text-base font-semibold text-gray-900">
        Ask a follow-up question
      </h3>

      {/* Message list */}
      <div className="mb-4 h-72 space-y-3 overflow-y-auto rounded-md bg-gray-50 p-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
            data-testid={`chat-message-${msg.role}`}
            className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
              msg.role === "user"
                ? "ml-auto bg-blue-50 text-right text-blue-900"
                : "mr-auto bg-white text-left text-gray-700 shadow-sm"
            }`}
          >
            {msg.content}
          </div>
        ))}

        {/* Typing indicator */}
        {isLoading && messages.length > 0 && messages[messages.length - 1].role === "user" && (
          <div className="mr-auto flex gap-1 rounded-lg bg-white px-3 py-2 shadow-sm">
            <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400" />
            <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400 [animation-delay:150ms]" />
            <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400 [animation-delay:300ms]" />
          </div>
        )}

        <div ref={endRef} data-testid="chat-messages-end" />
      </div>

      {/* Error display */}
      {error && (
        <p data-testid="chat-error" className="mb-3 text-sm text-red-600">
          {error}
        </p>
      )}

      {/* Input area */}
      <div className="flex gap-2">
        <textarea
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your form analysis..."
          rows={1}
          className="flex-1 resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          type="button"
          data-testid="chat-send-button"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
