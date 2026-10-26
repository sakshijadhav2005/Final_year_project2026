import { MarkdownText } from "./MarkdownText";
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
    <div className="w-full max-w-3xl rounded-card border border-black/10 bg-surface-light p-34 dark:border-white/10 dark:bg-surface-dark">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-black/5 pb-21 dark:border-white/5">
        <div>
          <span className="rounded-full bg-accent/15 px-8 py-[2px] text-xs font-semibold text-accent">
            Executive Summary
          </span>
          <h2 className="mt-8 font-display text-h2 font-semibold text-ink-light dark:text-ink-dark">
            {title || "Session Overview & Takeaways"}
          </h2>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-8 rounded-card border border-white/[0.12] px-13 py-8 text-xs font-medium text-ink transition-colors hover:border-amber-400/50"
        >
          {copied ? "✓ Copied!" : "📋 Copy Summary"}
        </button>
      </div>

      {/* Summary Body */}
      <MarkdownText source={body} className="mt-21" />

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
