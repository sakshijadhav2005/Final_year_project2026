import type { ReactNode } from "react";

/**
 * Minimal, dependency-free Markdown renderer for generated drafts.
 * Supports #/##/### headings, "-", "*" and "•" bullets, numbered lists,
 * pipe tables, --- dividers, **bold** and *italic*. Everything is rendered as React text,
 * never as HTML, so model output cannot inject markup.
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
  | { kind: "p"; text: string }
  | { kind: "hr" }
  | { kind: "table"; header: string[] | null; rows: string[][] };

// A pipe-table row starts with "|" and has at least one more "|" (the trailing one is optional).
const isTableRow = (line: string) => line.startsWith("|") && line.indexOf("|", 1) > 0;
// The line under the header, e.g. |:---|---:|
const isTableSeparator = (line: string) =>
  line.includes("|") && /^\|?(\s*:?-{2,}:?\s*\|)*\s*:?-{2,}:?\s*\|?$/.test(line);

function splitRow(line: string): string[] {
  return line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function parse(source: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  // The table being filled; any other line ends it.
  let table: Extract<Block, { kind: "table" }> | null = null;
  const flush = () => {
    if (para.length) blocks.push({ kind: "p", text: para.join(" ") });
    para = [];
  };
  for (const raw of source.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trim();
    if (!line) {
      flush();
      table = null;
      continue;
    }
    if (isTableRow(line) || (table && isTableSeparator(line))) {
      flush();
      if (!table) {
        table = { kind: "table", header: null, rows: [] };
        blocks.push(table);
      }
      if (isTableSeparator(line)) {
        // The row above the separator is the header.
        if (!table.header && table.rows.length === 1) table.header = table.rows.pop() ?? null;
      } else {
        table.rows.push(splitRow(line));
      }
      continue;
    }
    table = null;
    // A line of only ---, *** or ___ (spaces allowed) is a divider.
    if (/^([-*_])(\s*\1){2,}$/.test(line)) {
      flush();
      blocks.push({ kind: "hr" });
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
        if (b.kind === "hr") {
          return <hr key={i} className="border-black/10 dark:border-white/10" />;
        }
        if (b.kind === "table") {
          const cols = Math.max(b.header?.length ?? 0, ...b.rows.map((r) => r.length));
          const pad = (row: string[]) => Array.from({ length: cols }, (_, c) => row[c] ?? "");
          return (
            <div
              key={i}
              className="overflow-x-auto rounded-card border border-black/10 dark:border-white/10"
            >
              <table className="w-full border-collapse text-left text-sm">
                {b.header && (
                  <thead className="bg-black/[0.03] dark:bg-white/[0.04]">
                    <tr>
                      {pad(b.header).map((cell, c) => (
                        <th key={c} scope="col" className="px-13 py-8 font-semibold text-ink">
                          {inline(cell)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {b.rows.map((row, r) => (
                    <tr key={r} className="border-t border-black/[0.06] dark:border-white/[0.06]">
                      {pad(row).map((cell, c) => (
                        <td key={c} className="px-13 py-8 align-top">
                          {inline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={i}>{inline(b.text)}</p>;
      })}
    </div>
  );
}
