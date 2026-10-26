import type { ReactNode } from "react";

/**
 * Minimal, dependency-free Markdown renderer for generated drafts.
 * Supports #/##/### headings, "-", "*" and "•" bullets, numbered lists,
 * **bold** and *italic*. Everything is rendered as React text, never as HTML,
 * so model output cannot inject markup.
 */
function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const token = m[0];
    if (token.startsWith("**")) {
      parts.push(
        <strong key={key++} className="font-semibold text-ink">
          {token.slice(2, -2)}
        </strong>,
      );
    } else {
      parts.push(<em key={key++}>{token.slice(1, -1)}</em>);
    }
    last = m.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

type Block =
  | { kind: "h"; level: number; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "p"; text: string };

function parse(source: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ kind: "p", text: para.join(" ") });
    para = [];
  };
  for (const raw of source.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trim();
    if (!line) {
      flush();
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    const ul = /^(?:[-*•])\s+(.*)$/.exec(line);
    const ol = /^\d+[.)]\s+(.*)$/.exec(line);
    if (h) {
      flush();
      blocks.push({ kind: "h", level: h[1].length, text: h[2] });
    } else if (ul) {
      flush();
      const prev = blocks[blocks.length - 1];
      if (prev && prev.kind === "ul") prev.items.push(ul[1]);
      else blocks.push({ kind: "ul", items: [ul[1]] });
    } else if (ol) {
      flush();
      const prev = blocks[blocks.length - 1];
      if (prev && prev.kind === "ol") prev.items.push(ol[1]);
      else blocks.push({ kind: "ol", items: [ol[1]] });
    } else {
      para.push(line);
    }
  }
  flush();
  return blocks;
}

export function MarkdownText({ source, className = "" }: { source: string; className?: string }) {
  const blocks = parse(source || "");
  return (
    <div className={`space-y-13 text-[15px] leading-[1.7] text-ink/90 ${className}`}>
      {blocks.map((b, i) => {
        if (b.kind === "h") {
          const cls =
            b.level <= 2
              ? "pt-8 font-display text-h3 font-semibold text-ink"
              : "pt-8 text-sm font-semibold text-ink";
          return (
            <p key={i} className={cls} role="heading" aria-level={Math.min(b.level + 1, 6)}>
              {inline(b.text)}
            </p>
          );
        }
        if (b.kind === "ul") {
          return (
            <ul key={i} className="space-y-8 pl-21">
              {b.items.map((item, j) => (
                <li key={j} className="list-disc marker:text-amber-400">
                  {inline(item)}
                </li>
              ))}
            </ul>
          );
        }
        if (b.kind === "ol") {
          return (
            <ol key={i} className="space-y-8 pl-21">
              {b.items.map((item, j) => (
                <li key={j} className="list-decimal marker:text-ink-dim">
                  {inline(item)}
                </li>
              ))}
            </ol>
          );
        }
        return <p key={i}>{inline(b.text)}</p>;
      })}
    </div>
  );
}
