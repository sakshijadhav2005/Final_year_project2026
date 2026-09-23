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
          className="group flex items-center gap-2.5 rounded-full bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 px-5 py-3 text-xs font-bold text-white shadow-2xl shadow-orange-500/30 hover:scale-105 hover:shadow-orange-500/50 transition-all border border-amber-300/30"
        >
          <span className="text-base animate-bounce">💬</span>
          <span>Ask Event AI Assistant</span>
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
        </button>
      )}

      {/* Expanded Chat Box */}
      {isOpen && (
        <div className="w-80 sm:w-96 rounded-2xl border border-white/10 bg-slate-900/95 shadow-2xl backdrop-blur-2xl flex flex-col overflow-hidden animate-fadeIn">
          {/* Box Header */}
          <div className="flex items-center justify-between border-b border-white/10 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 p-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-300 font-bold text-xs">
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
              className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
            >
              ✕
            </button>
          </div>

          {/* Messages Area */}
          <div className="h-72 overflow-y-auto p-3.5 space-y-3 text-xs">
            {messages.length === 0 && (
              <div className="py-4 text-center">
                <span className="text-2xl">🎙️</span>
                <p className="mt-1 font-semibold text-slate-200 text-xs">Got questions about the talk?</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  I have read the full recording transcript and can answer any details instantly.
                </p>

                <div className="mt-3 space-y-1.5 text-left">
                  {attendeePrompts.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => handleSend(p)}
                      className="w-full text-left rounded-lg border border-white/5 bg-white/[0.02] p-2 text-[10px] text-slate-300 hover:border-amber-500/30 hover:bg-amber-500/10 hover:text-amber-200 transition-all"
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
                    className={`max-w-[85%] rounded-xl p-2.5 leading-relaxed text-[11px] ${
                      isUser
                        ? "bg-amber-500 text-white font-medium shadow"
                        : "bg-slate-800 border border-white/10 text-slate-200 whitespace-pre-wrap"
                    }`}
                  >
                    {m.content || "..."}
                  </div>
                </div>
              );
            })}

            {error && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2 text-rose-300 text-[10px]">
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
            className="flex items-center gap-1.5 border-t border-white/10 p-2.5 bg-slate-950/80"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about speakers, points, key quotes..."
              disabled={isStreaming}
              className="flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="rounded-xl bg-amber-500 px-3 py-1.5 text-xs font-bold text-white hover:bg-amber-400 transition-colors disabled:opacity-40"
            >
              Ask
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
