import { useState } from "react";

interface InstagramCardProps {
  title?: string | null;
  body: string;
  onCopy?: () => void;
}

export function InstagramCard({ title, body, onCopy }: InstagramCardProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(body);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  }

  return (
    <div className="w-full max-w-lg overflow-hidden rounded-card border border-black/10 bg-surface-light shadow-lg dark:border-white/10 dark:bg-surface-dark">
      {/* Instagram Header */}
      <div className="flex items-center justify-between border-b border-black/5 p-13 dark:border-white/5">
        <div className="flex items-center gap-13">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-tr from-[#FD1D1D] via-[#F56040] to-[#FFDC80] text-xs font-bold text-white shadow-sm">
            ✦
          </div>
          <span className="text-xs font-semibold">eventai_live</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-4 rounded-card border border-[#E1306C]/40 bg-[#E1306C]/10 px-13 py-8 text-xs font-medium text-[#E1306C] transition-all hover:bg-[#E1306C] hover:text-white"
        >
          {copied ? "✓ Copied!" : "📋 Copy Caption"}
        </button>
      </div>

      {/* Visual Photo Card Placeholder */}
      <div className="relative flex aspect-square w-full items-center justify-center bg-gradient-to-br from-[#833AB4] via-[#FD1D1D] to-[#FCB045] p-34 text-center text-white">
        <div className="rounded-card bg-black/40 p-21 backdrop-blur-md">
          <p className="text-xs font-semibold uppercase tracking-widest text-white/80">Recap Quote</p>
          <p className="mt-8 font-display text-lg font-bold">"{title || "Key Session Moments"}"</p>
        </div>
      </div>

      {/* Caption Content */}
      <div className="p-21">
        <div className="flex items-center gap-13 pb-13 text-sm">
          <span>❤️ 214</span>
          <span>💬 19</span>
          <span>✈️ 8</span>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-light/90 dark:text-ink-dark/90">
          <span className="mr-8 font-semibold">eventai_live</span>
          {body}
        </p>
      </div>
    </div>
  );
}
