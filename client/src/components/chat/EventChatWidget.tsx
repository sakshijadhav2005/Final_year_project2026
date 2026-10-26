import { useState, useRef, useEffect } from "react";
import { useChatStream } from "@/hooks/useChatStream";

type EventChatWidgetProps = {
  eventId?: string;
  jobId?: string;
  eventName?: string;
};

export function EventChatWidget({ eventId, jobId, eventName }: EventChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const { messages, sendMessage, isStreaming, error } = useChatStream(
    undefined,
    "attendee_qa",
    eventId,
    jobId,
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const attendeePrompts = [
    "What was the main topic discussed in this session?",
    "What key advice or tips did the speaker share?",
    "Were there any book or tool recommendations mentioned?",
  ];

  const handleSend = (text: string) => {
    if (!text.trim() || isStreaming) return;
    sendMessage(text);
    setInput("");
  };

  return (
    <div className="fixed bottom-6 right-6 z-40">
      {/* Floating Trigger Button */}
      {!isOpen && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="group flex items-center gap-2.5 rounded-full bg-amber-400 px-5 py-3 text-xs font-bold text-on-accent transition-all border border-amber-300/30"
        >
          <span className="text-base animate-bounce">💬</span>
          <span>Ask Event AI Assistant</span>
          <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
        </button>
      )}

      {/* Expanded Chat Box */}
      {isOpen && (
        <div className="w-80 sm:w-96 rounded-panel border border-white/[0.08] bg-slate-900/95 flex flex-col overflow-hidden animate-fadeIn">
          {/* Box Header */}
          <div className="flex items-center justify-between border-b border-white/[0.08] bg-slate-900 p-13">
            <div className="flex items-center gap-8">
              <div className="flex h-[32px] w-[32px] items-center justify-center rounded-card bg-amber-500/20 border border-amber-500/30 text-amber-300 font-bold text-xs">
                ✨
              </div>
              <div>
                <h3 className="text-xs font-bold text-white">
                  Talk to {eventName ? `"${eventName.slice(0, 18)}..."` : "the Event"}
                </h3>
                <p className="text-[10px] text-slate-400">Ask any question about this session</p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded-lg p-8 text-slate-400 hover:bg-white/10 hover:text-white"
            >
              ✕
            </button>
          </div>

          {/* Messages Area */}
          <div className="h-72 overflow-y-auto p-13 space-y-13 text-xs">
            {messages.length === 0 && (
              <div className="py-13 text-center">
                <span className="text-2xl">🎙️</span>
                <p className="mt-1 font-semibold text-slate-200 text-xs">Got questions about the talk?</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  I have read the full recording transcript and can answer any details instantly.
                </p>

                <div className="mt-13 space-y-8 text-left">
                  {attendeePrompts.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => handleSend(p)}
                      className="w-full text-left rounded-lg border border-white/5 bg-white/[0.02] p-8 text-[10px] text-slate-300 hover:border-amber-500/30 hover:bg-amber-500/10 hover:text-amber-200 transition-all"
                    >
                      ❓ {p}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => {
              const isUser = m.sender_type === "user";
              return (
                <div key={m.id} className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-card p-8 leading-relaxed text-[11px] ${
                      isUser
                        ? "bg-amber-500 text-on-accent font-medium"
                        : "bg-slate-800 border border-white/[0.08] text-slate-200 whitespace-pre-wrap"
                    }`}
                  >
                    {m.content || "..."}
                  </div>
                </div>
              );
            })}

            {error && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-8 text-rose-300 text-[10px]">
                {error}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Box */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
            className="flex items-center gap-8 border-t border-white/[0.08] p-8 bg-white/[0.02]"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about speakers, points, key quotes..."
              disabled={isStreaming}
              className="flex-1 rounded-card border border-white/[0.08] bg-white/5 px-13 py-8 text-xs text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="btn-primary btn-sm"
            >
              Ask
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
