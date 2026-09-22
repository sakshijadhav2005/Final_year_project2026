import { useState } from "react";

interface NewsletterPreviewProps {
  title?: string | null;
  body: string;
  onCopy?: () => void;
}

export function NewsletterPreview({ title, body, onCopy }: NewsletterPreviewProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(`Subject: ${title || "Event Recap"}\n\n${body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  }

  return (
    <div className="w-full max-w-2xl overflow-hidden rounded-card border border-black/10 bg-surface-light shadow-lg dark:border-white/10 dark:bg-surface-dark">
      {/* Email Client Header Bar */}
      <div className="border-b border-black/5 bg-canvas-light/60 p-21 dark:border-white/5 dark:bg-canvas-dark/60">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-8 text-xs text-ink-light/60 dark:text-ink-dark/60">
            <span className="flex h-3 w-3 rounded-full bg-danger"></span>
            <span className="flex h-3 w-3 rounded-full bg-warning"></span>
            <span className="flex h-3 w-3 rounded-full bg-success"></span>
            <span className="ml-8 font-medium">Newsletter Preview</span>
          </div>
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-8 rounded-card border border-accent/40 bg-accent/10 px-13 py-8 text-xs font-medium text-accent transition-all hover:bg-accent hover:text-white"
          >
            {copied ? "✓ Copied!" : "📋 Copy Email Text"}
          </button>
        </div>

        <div className="mt-13 space-y-4 text-xs">
          <div className="flex gap-8">
            <span className="w-16 font-semibold opacity-60">From:</span>
            <span>EventAI Editorial &lt;newsletter@eventai.app&gt;</span>
          </div>
          <div className="flex gap-8">
            <span className="w-16 font-semibold opacity-60">Subject:</span>
            <span className="font-semibold text-primary">{title || "This Week's Key Event Recap"}</span>
          </div>
        </div>
      </div>

      {/* Email Body Container */}
      <div className="p-34">
        {/* Email Header / Branding */}
        <div className="mb-21 border-b border-primary/20 pb-21 text-center">
          <p className="text-xs uppercase tracking-[0.25em] text-accent">Event Intelligence Digest</p>
          <h2 className="mt-8 font-display text-h3 font-bold text-ink-light dark:text-ink-dark">
            {title || "Special Edition: Session Insights"}
          </h2>
        </div>

        {/* Formatted Content */}
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink-light/90 dark:text-ink-dark/90">
          {body}
        </div>

        {/* Email Call-To-Action Box */}
        <div className="mt-34 rounded-card border border-primary/20 bg-primary/5 p-21 text-center">
          <h4 className="font-semibold text-primary">Enjoyed this recap?</h4>
          <p className="mt-4 text-xs opacity-70">Share this digest with your team or read the full discussion transcript.</p>
          <button
            type="button"
            className="mt-13 rounded-card bg-primary px-21 py-8 text-xs font-medium text-white shadow hover:bg-primary-dark"
          >
            View Event Archive →
          </button>
        </div>

        <div className="mt-34 border-t border-black/5 pt-21 text-center text-xs opacity-50 dark:border-white/5">
          You are receiving this because you attended this session. Unsubscribe anytime.
        </div>
      </div>
    </div>
  );
}
