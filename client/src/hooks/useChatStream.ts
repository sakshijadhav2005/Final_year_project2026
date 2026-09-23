import { useState, useCallback } from "react";
import { useAuthStore } from "@/store/auth";

export type ChatMessage = {
  id: string;
  sender_type: "user" | "assistant" | "system";
  content: string;
  created_at?: string;
};

export function useChatStream(sessionId?: string, contextType: string = "general", eventId?: string, jobId?: string) {
  const token = useAuthStore((s) => s.accessToken);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (userText: string) => {
      if (!userText.trim() || !token) return;

      const userMsgId = "user_" + Date.now();
      const assistantMsgId = "asst_" + (Date.now() + 1);

      // Add user message immediately
      setMessages((prev) => [
        ...prev,
        { id: userMsgId, sender_type: "user", content: userText, created_at: new Date().toISOString() },
        { id: assistantMsgId, sender_type: "assistant", content: "", created_at: new Date().toISOString() },
      ]);

      setIsStreaming(true);
      setError(null);

      const API_BASE = import.meta.env.VITE_API_URL ?? "";

      try {
        const response = await fetch(`${API_BASE}/api/v1/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            session_id: sessionId || null,
            message: userText,
            context_type: contextType,
            event_id: eventId || null,
            job_id: jobId || null,
          }),
        });

        if (!response.ok) {
          throw new Error(`Chat failed with status ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder("utf-8");
        let accumulated = "";

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split("\n");

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                const data = line.slice(6);
                if (data === "[DONE]") {
                  break;
                }
                accumulated += data;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId ? { ...msg, content: accumulated } : msg,
                  ),
                );
              }
            }
          }
        }
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : "Chat streaming failed";
        setError(errMsg);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? { ...msg, content: `⚠️ Error: ${errMsg}. Please check backend connection.` }
              : msg,
          ),
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [token, sessionId, contextType, eventId, jobId],
  );

  return {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    error,
  };
}
