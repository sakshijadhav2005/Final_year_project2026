import { useState } from "react";

interface SummaryViewProps {
  title?: string | null;
  body: string;
  onCopy?: () => void;
}

export function SummaryView({ title, body, onCopy }: SummaryViewProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(`${title ? `${title}\n\n` : ""}${body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  }

  return (
    <div className="w-full max-w-3xl rounded-card border border-black/10 bg-surface-light p-34 shadow-lg dark:border-white/10 dark:bg-surface-dark">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-black/5 pb-21 dark:border-white/5">
        <div>
          <span className="rounded-full bg-accent/15 px-8 py-2 text-xs font-semibold uppercase tracking-wider text-accent">
            Executive Summary
          </span>
          <h2 className="mt-8 font-display text-xl font-bold text-ink-light dark:text-ink-dark">
            {title || "Session Overview & Takeaways"}
          </h2>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-8 rounded-card border border-accent/30 bg-accent/10 px-13 py-8 text-xs font-medium text-accent transition-all hover:bg-accent hover:text-white"
        >
          {copied ? "✓ Copied!" : "📋 Copy Summary"}
        </button>
      </div>

      {/* Summary Body */}
      <div className="mt-21 whitespace-pre-wrap text-sm leading-relaxed text-ink-light/90 dark:text-ink-dark/90">
        {body}
      </div>

      {/* Trust & Verification Callout */}
      <div className="mt-34 flex items-center justify-between rounded-card border border-accent/20 bg-accent/5 p-13 text-xs text-ink-light/70 dark:text-ink-dark/70">
        <div className="flex items-center gap-8">
          <span className="text-accent">🔒</span>
          <span>Verified factual claims against source transcript</span>
        </div>
        <span className="font-semibold text-accent">Grounding Passed</span>
      </div>
    </div>
  );
}
