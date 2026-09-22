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

  // Split paragraphs for nice editorial rendering
  const paragraphs = body.split(/\n\n+/);

  return (
    <div className="w-full max-w-3xl rounded-card border border-black/10 bg-surface-light p-34 shadow-lg dark:border-white/10 dark:bg-surface-dark">
      {/* Blog Meta Header */}
      <div className="flex items-center justify-between border-b border-black/5 pb-21 text-xs text-ink-light/60 dark:border-white/5 dark:text-ink-dark/60">
        <div className="flex items-center gap-13">
          <span className="rounded-full bg-primary/10 px-8 py-2 font-medium text-primary">Article Draft</span>
          <span>•</span>
          <span>{readTime} min read</span>
          <span>•</span>
          <span>{wordCount} words</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-8 rounded-card border border-primary/30 bg-primary/10 px-13 py-8 text-xs font-medium text-primary transition-all hover:bg-primary hover:text-white"
        >
          {copied ? "✓ Copied!" : "📋 Copy Markdown"}
        </button>
      </div>

      {/* Article Title */}
      <h1 className="mt-21 font-display text-2xl font-bold tracking-tight text-ink-light dark:text-ink-dark md:text-3xl">
        {title || "Event Insights & Analysis"}
      </h1>

      {/* Article Body */}
      <div className="mt-21 space-y-21 text-body leading-relaxed text-ink-light/90 dark:text-ink-dark/90">
        {paragraphs.map((p, idx) => (
          <p key={idx} className="whitespace-pre-wrap">
            {p}
          </p>
        ))}
      </div>
    </div>
  );
}
