import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getContentProvenance, jobMediaUrl, type ProvenanceClaim } from "@/lib/api";

interface SourcesPanelProps {
  token: string;
  jobId: string;
  contentId: string;
  /** Changes when the draft is edited, so provenance is recomputed for the new text. */
  body: string;
}

const STATUS_STYLE: Record<ProvenanceClaim["status"], { dot: string; label: string }> = {
  traced: { dot: "bg-success", label: "Found in the recording" },
  partial: { dot: "bg-amber-400", label: "Paraphrased, check the passage" },
  untraced: { dot: "bg-danger", label: "No matching passage" },
};

function clock(seconds: number | null): string {
  if (seconds == null) return "";
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Claim-level provenance: where in the recording each sentence of the draft comes from. */
export function SourcesPanel({ token, jobId, contentId, body }: SourcesPanelProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [audioOk, setAudioOk] = useState(true);
  const [open, setOpen] = useState<number | null>(null);
  const [filter, setFilter] = useState<"all" | "check">("all");

  const prov = useQuery({
    queryKey: ["provenance", contentId, body],
    queryFn: () => getContentProvenance(token, contentId),
  });

  if (prov.isLoading) return <p className="px-8 text-xs text-ink-dim">Tracing sources…</p>;
  const data = prov.data;
  if (!data?.available || !data.summary) return null;

  const { summary } = data;
  const claims = data.claims
    .map((c, i) => ({ ...c, i }))
    .filter((c) => filter === "all" || c.status !== "traced");
  const timed = data.claims.some((c) => c.start != null);

  function play(c: ProvenanceClaim) {
    const audio = audioRef.current;
    if (!audio || c.start == null) return;
    audio.currentTime = c.start;
    void audio.play().catch(() => setAudioOk(false));
  }

  return (
    <div className="space-y-13 rounded-panel border border-white/[0.08] bg-surface p-21">
      <div className="flex items-baseline justify-between gap-8">
        <h3 className="font-display text-h3 text-ink">Sources</h3>
        <span className="text-xs text-ink-dim">
          {summary.traced} of {summary.claims} sentences found in the recording
        </span>
      </div>

      {/* Where in the talk the traced sentences come from */}
      <div>
        <div className="relative h-[21px] rounded-full bg-black/[0.06] dark:bg-white/[0.06]" aria-label="Where in the talk this draft draws from">
          {data.claims.map((c, i) =>
            c.position == null ? null : (
              <button
                key={i}
                type="button"
                title={`${clock(c.start) || `${Math.round(c.position * 100)}%`} · ${c.sentence}`}
                onClick={() => {
                  setFilter("all");
                  setOpen(i);
                  play(c);
                }}
                style={{ left: `calc(${c.position * 100}% - 4px)` }}
                className={`absolute top-[6px] h-[9px] w-[9px] rounded-full ${STATUS_STYLE[c.status].dot} ${
                  open === i ? "ring-2 ring-ink" : ""
                }`}
              />
            ),
          )}
        </div>
        <div className="mt-[4px] flex justify-between text-[11px] text-ink-dim">
          <span>Start of talk</span>
          <span>
            Covers {summary.bins.filter(Boolean).length} of {summary.bins.length} quarters
          </span>
          <span>End</span>
        </div>
      </div>

      {timed && audioOk && (
        <audio
          ref={audioRef}
          controls
          preload="none"
          src={jobMediaUrl(token, jobId)}
          onError={() => setAudioOk(false)}
          className="w-full"
        />
      )}

      <div className="flex gap-[4px] text-xs">
        {(["all", "check"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-full px-13 py-[4px] ${filter === f ? "bg-surface-raised font-semibold text-ink" : "text-ink-dim hover:text-ink"}`}
          >
            {f === "all" ? `All (${summary.claims})` : `To check (${summary.claims - summary.traced})`}
          </button>
        ))}
      </div>

      <ol className="max-h-[420px] space-y-8 overflow-y-auto pr-[4px]">
        {claims.map((c) => (
          <li key={c.i} className="rounded-card border border-white/[0.06] p-8 text-xs">
            <button
              type="button"
              onClick={() => setOpen(open === c.i ? null : c.i)}
              className="flex w-full items-start gap-8 text-left"
              aria-expanded={open === c.i}
            >
              <span className={`mt-[5px] h-[8px] w-[8px] shrink-0 rounded-full ${STATUS_STYLE[c.status].dot}`} title={STATUS_STYLE[c.status].label} />
              <span className="flex-1 text-ink">{c.sentence}</span>
              {c.start != null && <span className="shrink-0 tabular-nums text-ink-dim">{clock(c.start)}</span>}
            </button>
            {open === c.i && (
              <div className="mt-8 space-y-8 pl-[16px]">
                <p className="text-ink-dim">{STATUS_STYLE[c.status].label}</p>
                {c.evidence && (
                  <blockquote className="border-l-2 border-amber-400/50 pl-8 italic text-ink-dim">…{c.evidence}…</blockquote>
                )}
                {c.start != null && timed && audioOk && (
                  <button
                    type="button"
                    onClick={() => play(c)}
                    className="rounded-full border border-white/[0.12] px-13 py-[4px] text-ink hover:border-amber-400/50"
                  >
                    ▶ Play from {clock(c.start)}
                  </button>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>
      <p className="text-[11px] leading-relaxed text-ink-dim">
        Matched by wording, so a missing match means "check this", not "wrong". Times are estimates.
      </p>
    </div>
  );
}
