import { useState } from "react";

interface FlyerStructuredData {
  headline?: string;
  subhead?: string;
  bullets?: string[];
  date?: string;
  location?: string;
  speakers?: string[];
}

interface FlyerPreviewProps {
  title?: string | null;
  body: string;
  structured?: Record<string, unknown> | null;
  onCopy?: () => void;
}

export function FlyerPreview({ title, body, structured, onCopy }: FlyerPreviewProps) {
  const [copied, setCopied] = useState(false);
  const [showJson, setShowJson] = useState(false);

  const data = (structured as FlyerStructuredData) || {};
  const headline = data.headline || title || "Event Key Takeaways";
  const subhead = data.subhead || "Insights from the session";
  const bullets = data.bullets || [
    "Comprehensive session audio transcribed with high accuracy",
    "Multi-agent analysis parsed themes and quotes",
    "Publish-ready drafts generated with zero human latency",
    "Human gate ensured complete factual grounding",
  ];

  function handleCopy() {
    const text = `${headline}\n${subhead}\n\nKey Points:\n${bullets.map((b) => `• ${b}`).join("\n")}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  }

  return (
    <div className="flex flex-col items-center gap-13">
      {/* Controls Bar */}
      <div className="flex w-full max-w-md items-center justify-between">
        <button
          type="button"
          onClick={() => setShowJson(!showJson)}
          className="text-xs text-accent underline hover:opacity-80"
        >
          {showJson ? "← Show Visual Flyer" : "View Structured JSON"}
        </button>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-8 rounded-card border border-primary/30 bg-primary/10 px-13 py-8 text-xs font-medium text-primary transition-all hover:bg-primary hover:text-white"
        >
          {copied ? "✓ Copied!" : "📋 Copy Flyer Text"}
        </button>
      </div>

      {showJson ? (
        <pre className="w-full max-w-md overflow-auto rounded-card bg-[#0F1115] p-21 text-xs text-accent">
          {JSON.stringify({ headline, subhead, bullets, structured }, null, 2)}
        </pre>
      ) : (
        /* Visual Flyer Poster (1 : 1.618 golden-portrait aspect) */
        <div className="relative aspect-golden-portrait w-full max-w-md overflow-hidden rounded-card border border-primary/40 bg-gradient-to-b from-[#1E1B4B] via-[#0F1115] to-[#0A0B0E] p-34 text-white shadow-2xl">
          {/* Ambient Glows */}
          <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-accent/20 blur-3xl"></div>
          <div className="pointer-events-none absolute -bottom-20 -left-20 h-48 w-48 rounded-full bg-primary/30 blur-3xl"></div>

          {/* Flyer Top Header */}
          <div className="relative z-10 flex items-center justify-between border-b border-white/10 pb-13 text-xs">
            <span className="flex items-center gap-8 font-semibold tracking-wider text-accent">
              <span className="h-2 w-2 rounded-full bg-accent animate-pulse"></span>
              EVENT RECAP
            </span>
            <span className="rounded-full bg-white/10 px-8 py-2 text-[10px] uppercase tracking-widest text-white/80">
              Official Brief
            </span>
          </div>

          {/* Headline & Subhead */}
          <div className="relative z-10 my-21">
            <h2 className="font-display text-2xl font-bold leading-tight tracking-tight text-white md:text-3xl">
              {headline}
            </h2>
            <p className="mt-8 text-sm font-medium text-white/70">{subhead}</p>
          </div>

          {/* Highlights Box */}
          <div className="relative z-10 my-21 rounded-card border border-white/10 bg-white/5 p-21 backdrop-blur-md">
            <p className="mb-13 text-xs font-semibold uppercase tracking-wider text-accent">Key Highlights</p>
            <ul className="space-y-13 text-xs leading-relaxed text-white/90">
              {bullets.map((point, index) => (
                <li key={index} className="flex items-start gap-8">
                  <span className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-accent/20 text-[10px] text-accent">
                    ✓
                  </span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Fallback Body Text preview if provided */}
          {body && body !== "Recap highlights from the session." && (
            <div className="relative z-10 my-13 text-xs italic text-white/60 line-clamp-3">
              "{body}"
            </div>
          )}

          {/* Flyer Footer Badge */}
          <div className="relative z-10 mt-auto border-t border-white/10 pt-21">
            <div className="flex items-center justify-between text-xs text-white/60">
              <div className="flex items-center gap-8">
                <span className="font-display font-bold text-accent">EventAI</span>
                <span>• Intelligent Content</span>
              </div>
              <span className="text-[10px] text-white/40">Verified Grounded</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
