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
    "Identify top 3 actionable takeaways from this session",
    "Suggest 3 interactive LinkedIn poll ideas from talk",
    "Summarize speaker tone and audience engagement",
  ];

  const handleSend = (text: string) => {
    if (!text.trim() || isStreaming) return;
    sendMessage(text);
    setInput("");
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col w-[380px] max-w-[calc(100vw-32px)] h-[540px] max-h-[85vh] rounded-panel border border-white/15 bg-slate-900/95 shadow-black/80 overflow-hidden animate-fadeIn">
      {/* Drawer Header */}
      <div className="flex items-center justify-between border-b border-white/[0.08] px-21 py-13 bg-white/[0.02]">
        <div className="flex items-center gap-8">
          <div className="flex h-8 w-8 items-center justify-center rounded-card bg-amber-400 font-bold text-on-accent text-sm">
            🤖
          </div>
          <div>
            <h2 className="text-xs font-semibold text-white flex items-center gap-8">
              <span>Organizer AI Co-Pilot</span>
              <span className="rounded-full bg-amber-500/20 px-8 py-0.5 text-[9px] font-bold text-amber-300 border border-amber-500/30">
                Live
              </span>
            </h2>
            <p className="text-[10px] text-slate-400">Grounded session co-pilot</p>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-8 text-slate-400 hover:bg-white/10 hover:text-white transition-colors"
          title="Close assistant"
        >
          ✕
        </button>
      </div>

      {/* Messages Body */}
      <div className="flex-1 overflow-y-auto p-13 space-y-13 font-sans text-xs">
        {messages.length === 0 && (
          <div className="py-13 text-center">
            <div className="mx-auto mb-8 flex h-10 w-10 items-center justify-center rounded-panel bg-amber-500/10 border border-amber-500/20 text-xl">
              ✨
            </div>
            <h3 className="font-bold text-slate-200 text-xs">How can I assist your event ops?</h3>
            <p className="mt-1 text-slate-400 max-w-xs mx-auto text-[10px]">
              Ask me to draft emails, analyze drop-off points, brainstorm social hooks, or extract key quotes.
            </p>

            <div className="mt-13 space-y-8 text-left">
              <p className="text-[10px] font-bold text-amber-400/80 px-1">
                Suggested Prompts:
              </p>
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => handleSend(prompt)}
                  className="w-full text-left rounded-card border border-white/5 bg-white/[0.03] p-8 text-[11px] text-slate-300 hover:border-amber-500/30 hover:bg-amber-500/10 hover:text-amber-200 transition-all"
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
              <div
                className={`max-w-[85%] rounded-panel px-13 py-8 text-xs leading-relaxed ${
                  isUser
                    ? "bg-amber-400 font-medium text-on-accent"
                    : "border border-white/[0.08] bg-slate-800/80 text-slate-200"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
              <span className="mt-1 px-1 text-[9px] text-slate-500">
                {isUser ? "You" : "AI Co-Pilot"}
              </span>
            </div>
          );
        })}

        {isStreaming && (
          <div className="flex items-center gap-8 text-xs text-amber-400">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            <span className="text-[10px]">Co-Pilot is composing response…</span>
          </div>
        )}

        {error && (
          <div className="rounded-card border border-rose-500/30 bg-rose-500/10 p-8 text-[11px] text-rose-300">
            ⚠️ {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="border-t border-white/[0.08] bg-white/[0.02] p-13">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
          }}
          className="flex items-center gap-8"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Co-Pilot or request rewrite..."
            disabled={isStreaming}
            className="flex-1 rounded-card border border-white/[0.08] bg-white/5 px-13 py-8 text-xs text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-1 focus:ring-amber-500/30"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="btn-primary btn-sm"
          >
            {isStreaming ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
