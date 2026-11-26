import { useState } from "react";

import { xLength } from "@/lib/social";

interface XCardProps {
  body: string;
  onCopy?: () => void;
}

export function XCard({ body, onCopy }: XCardProps) {
  const [copied, setCopied] = useState(false);
  const count = xLength(body);
  const over = count > 280;

  function handleCopy() {
    navigator.clipboard.writeText(body);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  }

  return (
    <div className="w-full max-w-lg rounded-card border border-black/10 bg-surface-light p-21 dark:border-white/10 dark:bg-[#0F1419]">
      <div className="mb-13 flex items-center justify-between">
        <div className="flex items-center gap-13">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black text-sm font-bold text-white dark:bg-white dark:text-black">
            𝕏
          </div>
          <div>
            <span className="block text-sm font-semibold text-ink-light dark:text-ink-dark">EventAI</span>
            <span className="text-xs text-ink-light/60 dark:text-ink-dark/60">@eventai · now</span>
          </div>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="rounded-card border border-white/[0.12] px-13 py-8 text-xs font-medium text-ink transition-colors hover:border-amber-400/50"
        >
          {copied ? "✓ Copied!" : "📋 Copy"}
        </button>
      </div>
      <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink-light dark:text-ink-dark">{body}</p>
      <div className={`mt-13 text-right text-xs ${over ? "font-semibold text-danger" : "text-ink-dim"}`}>
        {count} / 280{over ? " — too long for X, shorten it before publishing" : ""}
      </div>
    </div>
  );
}
