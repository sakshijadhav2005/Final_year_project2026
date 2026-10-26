import { useState, useCallback, useRef } from "react";
import { authFetch } from "@/lib/session";
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
  // The server creates a chat session on the first message and reports its id
  // in the first SSE event; reuse it so follow-up questions keep their history.
  const sessionRef = useRef<string | undefined>(sessionId);

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

      try {
        // authFetch renews an expired token and retries instead of failing.
        const response = await authFetch(`/api/v1/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            session_id: sessionRef.current || null,
            message: userText,
            persona: contextType,
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
          let buffer = "";
          let finished = false;
          while (!finished) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            // SSE events are separated by a blank line; keep any partial event in the buffer.
            const events = buffer.split("\n\n");
            buffer = events.pop() ?? "";

            for (const event of events) {
              const line = event.trim();
              if (!line.startsWith("data:")) continue;
              const data = line.slice(5).trim();
              if (data === "[DONE]") {
                finished = true;
                break;
              }
              try {
                const payload = JSON.parse(data) as { chunk?: string; done?: boolean; session_id?: string };
                if (payload.session_id) sessionRef.current = payload.session_id;
                if (payload.chunk) accumulated += payload.chunk;
                if (payload.done) finished = true;
              } catch {
                accumulated += data;
              }
              setMessages((prev) =>
                prev.map((msg) => (msg.id === assistantMsgId ? { ...msg, content: accumulated } : msg)),
              );
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
    [token, contextType, eventId, jobId],
  );

  return {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    error,
  };
}
