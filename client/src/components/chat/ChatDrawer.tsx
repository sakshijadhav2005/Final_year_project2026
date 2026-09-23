import { useState, useRef, useEffect } from "react";
import { useChatStream } from "@/hooks/useChatStream";

type ChatDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  jobId?: string;
  eventId?: string;
};

export function ChatDrawer({ isOpen, onClose, jobId, eventId }: ChatDrawerProps) {
  const [input, setInput] = useState("");
  const { messages, sendMessage, isStreaming, error } = useChatStream(
    undefined,
    "organizer_copilot",
    eventId,
    jobId,
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!isOpen) return null;

  const quickPrompts = [
    "Draft a post-event thank-you email for attendees",
    "Identify the top 3 actionable takeaways from this session",
    "Suggest 3 interactive LinkedIn poll ideas from the talk",
    "Summarize speaker tone and audience engagement points",
  ];

  const handleSend = (text: string) => {
    if (!text.trim() || isStreaming) return;
    sendMessage(text);
    setInput("");
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm transition-opacity">
      <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
        <div className="w-screen max-w-md bg-slate-900 border-l border-white/10 shadow-2xl flex flex-col">
          {/* Drawer Header */}
          <div className="flex items-center justify-between border-b border-white/10 px-6 py-4 bg-slate-950/80 backdrop-blur-md">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-amber-500 to-orange-600 font-bold text-white shadow-md shadow-orange-500/20">
                🤖
              </div>
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <span>Organizer AI Co-Pilot</span>
                  <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
                    Live
                  </span>
                </h2>
                <p className="text-[11px] text-slate-400">Grounded in session transcripts & editorial plan</p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white transition-colors"
            >
              ✕
            </button>
          </div>

          {/* Messages Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 font-sans text-xs">
            {messages.length === 0 && (
              <div className="py-6 text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 border border-amber-500/20 text-2xl">
                  ✨
                </div>
                <h3 className="font-bold text-slate-200">How can I assist your event ops?</h3>
                <p className="mt-1 text-slate-400 max-w-xs mx-auto text-[11px]">
                  Ask me to draft emails, analyze drop-off points, brainstorm social hooks, or extract key quotes.
                </p>

                <div className="mt-5 space-y-2 text-left">
                  <p className="text-[10px] uppercase font-bold tracking-wider text-amber-400/80 px-1">
                    Suggested Prompts:
                  </p>
                  {quickPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleSend(prompt)}
                      className="w-full text-left rounded-xl border border-white/5 bg-white/[0.03] p-2.5 text-[11px] text-slate-300 hover:border-amber-500/30 hover:bg-amber-500/10 hover:text-amber-200 transition-all"
                    >
                      💡 {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => {
              const isUser = msg.sender_type === "user";
              return (
                <div
                  key={msg.id}
                  className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                >
                  <div className="mb-1 text-[10px] text-slate-400">
                    {isUser ? "You" : "EventAI Co-Pilot"}
                  </div>
                  <div
                    className={`max-w-[88%] rounded-2xl p-3.5 leading-relaxed ${
                      isUser
                        ? "bg-gradient-to-r from-amber-500 to-orange-600 text-white font-medium shadow-md shadow-orange-500/10"
                        : "bg-slate-800/80 border border-white/10 text-slate-200 whitespace-pre-wrap"
                    }`}
                  >
                    {msg.content || (
                      <span className="inline-flex items-center gap-1 opacity-70">
                        <span className="animate-pulse">Thinking</span>
                        <span className="inline-block animate-bounce">.</span>
                        <span className="inline-block animate-bounce [animation-delay:0.2s]">.</span>
                        <span className="inline-block animate-bounce [animation-delay:0.4s]">.</span>
                      </span>
                    )}
                  </div>
                </div>
              );
            })}

            {error && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300 text-[11px]">
                {error}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Bar */}
          <div className="border-t border-white/10 p-4 bg-slate-950/90 backdrop-blur-md">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend(input);
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask Co-Pilot or request a rewrite..."
                disabled={isStreaming}
                className="flex-1 rounded-xl border border-white/10 bg-white/5 px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-1 focus:ring-amber-500/30"
              />
              <button
                type="submit"
                disabled={!input.trim() || isStreaming}
                className="rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-orange-500/20 hover:scale-105 transition-all disabled:opacity-50"
              >
                {isStreaming ? "..." : "Send"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
