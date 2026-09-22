import { useState } from "react";

interface LinkedInCardProps {
  title?: string | null;
  body: string;
  onCopy?: () => void;
}

export function LinkedInCard({ title, body, onCopy }: LinkedInCardProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(`${title ? `${title}\n\n` : ""}${body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  }

  // Extract hashtags
  const hashtags = body.match(/#[a-zA-Z0-9_]+/g) || [];
  const cleanBody = body.replace(/#[a-zA-Z0-9_]+/g, "").trim();

  return (
    <div className="w-full max-w-2xl rounded-card border border-black/10 bg-surface-light shadow-lg transition-all dark:border-white/10 dark:bg-[#1B1F24]">
      {/* LinkedIn Post Header */}
      <div className="flex items-center justify-between border-b border-black/5 p-21 dark:border-white/5">
        <div className="flex items-center gap-13">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-tr from-[#0077B5] to-[#00A0DC] font-display font-bold text-white shadow-sm">
            E
          </div>
          <div>
            <div className="flex items-center gap-8">
              <span className="font-medium text-ink-light dark:text-ink-dark">EventAI Team</span>
              <span className="rounded bg-accent/15 px-8 py-2 text-[10px] font-semibold text-accent">PRO</span>
            </div>
            <p className="text-xs text-ink-light/60 dark:text-ink-dark/60">Content Operations • 1d • 🌐</p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-8 rounded-card border border-primary/30 bg-primary/10 px-13 py-8 text-xs font-medium text-primary transition-all hover:bg-primary hover:text-white"
        >
          {copied ? "✓ Copied!" : "📋 Copy Post"}
        </button>
      </div>

      {/* Post Content */}
      <div className="p-21">
        {title && <h4 className="mb-13 font-semibold text-primary">{title}</h4>}
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink-light/90 dark:text-ink-dark/90">
          {cleanBody}
        </div>

        {/* Hashtags */}
        {hashtags.length > 0 && (
          <div className="mt-13 flex flex-wrap gap-8">
            {hashtags.map((tag, i) => (
              <span key={i} className="font-medium text-[#0077B5] hover:underline dark:text-[#70B5F9]">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Social Engagement Stats Mock */}
      <div className="flex items-center justify-between border-t border-black/5 px-21 py-8 text-xs text-ink-light/50 dark:border-white/5 dark:text-ink-dark/50">
        <div className="flex items-center gap-2">
          <span>👍 💡 48 reactions</span>
        </div>
        <div className="flex gap-13">
          <span>6 comments</span>
          <span>•</span>
          <span>11 reposts</span>
        </div>
      </div>

      {/* Footer Stats & Actions */}
      <div className="grid grid-cols-4 border-t border-black/5 p-8 text-center text-xs font-medium text-ink-light/70 dark:border-white/5 dark:text-ink-dark/70">
        <button type="button" className="rounded-lg py-8 hover:bg-black/5 dark:hover:bg-white/5">
          👍 Like
        </button>
        <button type="button" className="rounded-lg py-8 hover:bg-black/5 dark:hover:bg-white/5">
          💬 Comment
        </button>
        <button type="button" className="rounded-lg py-8 hover:bg-black/5 dark:hover:bg-white/5">
          🔁 Repost
        </button>
        <button type="button" className="rounded-lg py-8 hover:bg-black/5 dark:hover:bg-white/5">
          📤 Send
        </button>
      </div>
    </div>
  );
}
