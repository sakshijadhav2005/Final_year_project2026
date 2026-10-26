import { MarkdownText } from "./MarkdownText";
import { useState } from "react";

interface BlogArticleProps {
  title?: string | null;
  body: string;
  onCopy?: () => void;
}

export function BlogArticle({ title, body, onCopy }: BlogArticleProps) {
  const [copied, setCopied] = useState(false);

  const wordCount = body.trim().split(/\s+/).length;
  const readTime = Math.max(1, Math.ceil(wordCount / 200));

  function handleCopy() {
    const full = `# ${title || "Blog Post"}\n\n${body}`;
    navigator.clipboard.writeText(full);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  }

  return (
    <div className="w-full max-w-3xl rounded-card border border-black/10 bg-surface-light p-34 dark:border-white/10 dark:bg-surface-dark">
      {/* Blog Meta Header */}
      <div className="flex items-center justify-between border-b border-black/5 pb-21 text-xs text-ink-light/60 dark:border-white/5 dark:text-ink-dark/60">
        <div className="flex items-center gap-13">
          <span className="rounded-full bg-white/[0.06] px-8 py-[2px] font-medium text-ink-dim">Article Draft</span>
          <span>
            {readTime} min read, {wordCount} words
          </span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-8 rounded-card border border-white/[0.12] px-13 py-8 text-xs font-medium text-ink transition-colors hover:border-amber-400/50"
        >
          {copied ? "✓ Copied!" : "📋 Copy Markdown"}
        </button>
      </div>

      {/* Article Title */}
      <h1 className="mt-21 font-display text-h1 font-semibold tracking-tight text-ink-light dark:text-ink-dark">
        {title || "Event Insights & Analysis"}
      </h1>

      {/* Article Body */}
      <MarkdownText source={body} className="mt-21 text-[16px]" />
    </div>
  );
}
