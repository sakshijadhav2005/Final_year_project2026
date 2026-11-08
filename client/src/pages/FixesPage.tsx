import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import {
  approveAutoFix,
  getAutoFix,
  getAutoFixStatus,
  listAutoFixes,
  rejectAutoFix,
  retryAutoFix,
  reviseAutoFix,
  type AutoFixDetail,
  type AutoFixStatus,
  type AutoFixSummary,
} from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

const STATUS: Record<AutoFixStatus, { label: string; tone: string }> = {
  new: { label: "Queued", tone: "bg-white/[0.08] text-ink-dim" },
  fixing: { label: "Agent fixing", tone: "bg-amber-400/15 text-amber-300" },
  revising: { label: "Applying feedback", tone: "bg-amber-400/15 text-amber-300" },
  proposed: { label: "Needs your review", tone: "bg-amber-400 text-on-accent font-semibold" },
  approved: { label: "Pushed", tone: "bg-success/15 text-success" },
  rejected: { label: "Rejected", tone: "bg-white/[0.08] text-ink-dim" },
  failed: { label: "No fix", tone: "bg-danger/15 text-danger" },
  external: { label: "Not a code bug", tone: "bg-white/[0.08] text-ink-dim" },
};

const RISK_TONE = { low: "text-success", medium: "text-warning", high: "text-danger" } as const;
const SOURCE = { api: "API", pipeline: "Pipeline", frontend: "Browser" } as const;

function ago(iso: string | null): string {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

function Chip({ status }: { status: AutoFixStatus }) {
  return <span className={`whitespace-nowrap rounded-full px-8 py-[2px] text-[11px] ${STATUS[status].tone}`}>{STATUS[status].label}</span>;
}

function Check({ label, value }: { label: string; value: boolean | null | undefined }) {
  if (value === undefined) return null;
  const [icon, tone] = value === true ? ["✓", "text-success"] : value === false ? ["✗", "text-danger"] : ["–", "text-ink-dim"];
  return (
    <span className="flex items-center gap-[6px] text-xs">
      <span className={`font-semibold ${tone}`}>{icon}</span>
      <span className="text-ink">{label}</span>
    </span>
  );
}

function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="max-h-[480px] overflow-auto rounded-card bg-black/30 p-13 font-mono text-[11.5px] leading-[1.55]">
      {diff.split("\n").map((line, i) => {
        const tone = line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff ")
          ? "text-ink font-semibold"
          : line.startsWith("+") ? "bg-success/10 text-success"
          : line.startsWith("-") ? "bg-danger/10 text-danger"
          : line.startsWith("@@") ? "text-amber-300"
          : "text-ink-dim";
        return <div key={i} className={`whitespace-pre px-[4px] ${tone}`}>{line || " "}</div>;
      })}
    </pre>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-8">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-dim">{title}</h3>
      {children}
    </section>
  );
}

function Detail({ token, id }: { token: string; id: string }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<"none" | "revise" | "reject" | "confirm">("none");
  const [text, setText] = useState("");
  const fix = useQuery({
    queryKey: ["autofix", id],
    queryFn: () => getAutoFix(token, id),
    refetchInterval: (q) => (["new", "fixing", "revising"].includes(q.state.data?.status ?? "") ? 4000 : false),
  });

  const act = useMutation({
    mutationFn: (kind: "approve" | "reject" | "revise" | "retry"): Promise<AutoFixDetail> =>
      kind === "approve" ? approveAutoFix(token, id)
      : kind === "reject" ? rejectAutoFix(token, id, text)
      : kind === "revise" ? reviseAutoFix(token, id, text)
      : retryAutoFix(token, id),
    onSuccess: (data) => {
      qc.setQueryData(["autofix", id], data);
      void qc.invalidateQueries({ queryKey: ["autofixes"] });
      setMode("none");
      setText("");
    },
  });

  if (fix.isLoading || !fix.data) return <p className="p-21 text-sm text-ink-dim">Loading…</p>;
  const f = fix.data;
  const report = f.report ?? {};
  const checks = f.checks;
  const scan = f.review?.scan;
  const llm = f.review?.agent;
  const busy = act.isPending;

  return (
    <div className="space-y-21">
      <header className="space-y-8">
        <div className="flex flex-wrap items-center gap-8">
          <Chip status={f.status} />
          <span className="text-xs text-ink-dim">{SOURCE[f.source]} · seen {f.occurrences}× · last {ago(f.last_seen)}</span>
          {f.risk && <span className={`text-xs font-semibold ${RISK_TONE[f.risk]}`}>{f.risk} risk</span>}
        </div>
        <h2 className="font-display text-h3 text-ink">{report.title ?? `${f.error_type} in ${f.location ?? f.source}`}</h2>
        {f.status_detail && <p className="text-sm text-ink-dim">{f.status_detail}</p>}
        {act.error && <p className="rounded-card bg-danger/10 p-8 text-sm text-danger">{(act.error as Error).message}</p>}
      </header>

      <Section title="The error">
        <p className="font-mono text-xs text-danger">{f.error_type}: {f.message}</p>
        {f.location && <p className="font-mono text-[11px] text-ink-dim">{f.location}</p>}
        {f.stack && (
          <details className="text-xs">
            <summary className="cursor-pointer text-ink-dim hover:text-ink">Stack trace</summary>
            <pre className="mt-8 max-h-[260px] overflow-auto rounded-card bg-black/30 p-13 font-mono text-[11px] text-ink-dim">{f.stack}</pre>
          </details>
        )}
      </Section>

      {(report.root_cause || report.fix) && (
        <Section title="Agent's diagnosis">
          {report.root_cause && <p className="text-sm text-ink"><span className="text-ink-dim">Why: </span>{report.root_cause}</p>}
          {report.fix && <p className="text-sm text-ink"><span className="text-ink-dim">Fix: </span>{report.fix}</p>}
          {report.notes && <p className="text-xs text-ink-dim">Note: {report.notes}</p>}
        </Section>
      )}

      {checks && (
        <Section title="Verification (run by EventAI, not the agent)">
          <div className="flex flex-wrap gap-21">
            <Check label="Backend tests" value={checks.backend ? checks.backend.passed : undefined} />
            <Check label="Type check" value={checks.frontend ? checks.frontend.passed : undefined} />
            <Check label="New test fails without the fix" value={checks.reproduced ?? (checks.backend ? null : undefined)} />
          </div>
          {[checks.backend, checks.frontend].map((c, i) =>
            c && c.passed === false ? (
              <pre key={i} className="max-h-[200px] overflow-auto rounded-card bg-black/30 p-8 font-mono text-[11px] text-ink-dim">{c.output}</pre>
            ) : null,
          )}
        </Section>
      )}

      {scan && (
        <Section title="Security & risk review">
          {scan.findings.length === 0 ? (
            <p className="text-xs text-success">Static scan: nothing risky found.</p>
          ) : (
            <ul className="space-y-[4px]">
              {scan.findings.map((x, i) => (
                <li key={i} className="flex gap-8 text-xs">
                  <span className={`font-semibold ${RISK_TONE[x.risk]}`}>{x.risk}</span>
                  <span className="text-ink">{x.finding}</span>
                  {x.file && <span className="font-mono text-ink-dim">{x.file}{x.line ? `:${x.line}` : ""}</span>}
                </li>
              ))}
            </ul>
          )}
          {llm && (
            <div className="text-xs">
              <p className={llm.verdict === "approve" ? "text-success" : "text-warning"}>
                Reviewer agent: {llm.verdict === "approve" ? "looks correct" : "has concerns"}
              </p>
              <ul className="mt-[4px] list-disc space-y-[2px] pl-21 text-ink-dim">
                {(llm.notes ?? []).map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </div>
          )}
        </Section>
      )}

      {f.diff && (
        <Section title={`Proposed change${f.branch ? ` · ${f.branch}` : ""}`}>
          <DiffView diff={f.diff} />
        </Section>
      )}

      {f.pr_url && (
        <a href={f.pr_url} target="_blank" rel="noreferrer" className="btn-primary btn-sm">
          Open pull request on GitHub ↗
        </a>
      )}

      {/* Decisions */}
      <div className="space-y-13 border-t border-white/[0.08] pt-21">
        {f.status === "proposed" && mode === "none" && (
          <div className="flex flex-wrap gap-8">
            <button type="button" className="btn-primary btn-sm" onClick={() => setMode("confirm")}>Approve &amp; push</button>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setMode("revise")}>Ask for changes</button>
            <button type="button" className="btn-danger btn-sm" onClick={() => setMode("reject")}>Reject</button>
          </div>
        )}
        {mode === "confirm" && (
          <div className="space-y-8 rounded-card border border-amber-400/40 p-13 text-sm">
            <p className="text-ink">
              This commits the change to <span className="font-mono">{f.branch}</span>, pushes it to GitHub and opens a
              pull request into <span className="font-mono">{f.base_branch}</span>. Nothing is merged.
            </p>
            {f.risk === "high" && <p className="text-danger">High risk: read the diff and the findings above before approving.</p>}
            <div className="flex gap-8">
              <button type="button" disabled={busy} className="btn-primary btn-sm" onClick={() => act.mutate("approve")}>
                {busy ? "Pushing…" : "Yes, push it"}
              </button>
              <button type="button" className="btn-ghost btn-sm" onClick={() => setMode("none")}>Cancel</button>
            </div>
          </div>
        )}
        {(mode === "revise" || mode === "reject") && (
          <div className="space-y-8">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={3}
              placeholder={mode === "revise" ? "What should the agent change? e.g. “Fix it in the caller instead”" : "Why? (optional, kept for the record)"}
              className="w-full rounded-card border border-white/[0.1] bg-black/20 p-8 text-sm text-ink"
            />
            <div className="flex gap-8">
              <button
                type="button"
                disabled={busy || (mode === "revise" && text.trim().length < 3)}
                className={mode === "revise" ? "btn-primary btn-sm" : "btn-danger btn-sm"}
                onClick={() => act.mutate(mode)}
              >
                {mode === "revise" ? "Send to agent" : "Reject and delete branch"}
              </button>
              <button type="button" className="btn-ghost btn-sm" onClick={() => setMode("none")}>Cancel</button>
            </div>
          </div>
        )}
        {["failed", "rejected", "external"].includes(f.status) && (
          <button type="button" disabled={busy} className="btn-ghost btn-sm" onClick={() => act.mutate("retry")}>
            Try again with the agent
          </button>
        )}
        {f.cost_usd > 0 && <p className="text-[11px] text-ink-dim">Agent cost so far: ${f.cost_usd.toFixed(2)}</p>}
      </div>
    </div>
  );
}

/** Admin → Error fixes: errors caught while the app runs, and the agent's fixes awaiting approval. */
export function FixesPage() {
  const token = useAuthStore((s) => s.accessToken) as string;
  const role = useAuthStore((s) => s.user?.role);
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState<"review" | "all">("review");

  const status = useQuery({ queryKey: ["autofix-status"], queryFn: () => getAutoFixStatus(token), enabled: role === "admin" });
  const list = useQuery({
    queryKey: ["autofixes"],
    queryFn: () => listAutoFixes(token),
    enabled: role === "admin",
    refetchInterval: 5000,
  });

  if (role !== "admin") {
    return (
      <GoldenShell>
        <p className="py-55 text-center text-sm text-ink-dim">Admin role required.</p>
      </GoldenShell>
    );
  }

  const rows: AutoFixSummary[] = (list.data ?? []).filter(
    (r) => filter === "all" || !["approved", "rejected", "external"].includes(r.status),
  );
  const pending = (list.data ?? []).filter((r) => r.status === "proposed").length;
  const current = selected ?? rows.find((r) => r.status === "proposed")?.id ?? rows[0]?.id ?? null;
  const s = status.data;

  return (
    <GoldenShell>
      <div className="space-y-21">
        <div className="flex flex-wrap items-center justify-between gap-13">
          <div>
            <h1 className="font-display text-h1 font-semibold text-ink">Error fixes</h1>
            <p className="mt-[4px] text-sm text-ink-dim">
              Errors caught while the app runs. An agent proposes a tested fix; nothing is pushed until you approve.
            </p>
          </div>
          <Link to="/admin" className="btn-ghost btn-sm">← Admin</Link>
        </div>

        {s && (
          <div className="glass flex flex-wrap items-center gap-x-21 gap-y-8 p-13 text-xs">
            <span className={s.active ? "text-success" : "text-ink-dim"}>
              ● {s.active ? "Watching for errors" : `Off (environment: ${s.environment})`}
            </span>
            <span className={s.agent_found ? "text-ink-dim" : "text-danger"}>
              {s.agent_found ? "Claude Code found" : "Claude Code CLI not found: set AUTOFIX_AGENT_CMD"}
            </span>
            <span className={s.gateway.ready ? "text-ink-dim" : "text-danger"}>
              {s.gateway.gateway === "portkey"
                ? s.gateway.ready ? `Model calls via Portkey (${s.gateway.route})` : `Portkey not set up: ${s.gateway.detail}`
                : "Model calls direct (no gateway)"}
            </span>
            <span className="text-ink-dim">Fix attempts today: {s.attempts_today} / {s.max_per_day}</span>
            <span className="text-ink-dim">{s.github_cli ? "Opens pull requests with gh" : "Gives a GitHub link to open the pull request"}</span>
            {pending > 0 && <span className="font-semibold text-amber-300">{pending} waiting for your review</span>}
          </div>
        )}

        <div className="grid gap-21 lg:grid-cols-[minmax(260px,1fr)_2fr]">
          <div className="glass space-y-8 p-13">
            <div className="flex gap-[4px] text-xs">
              {(["review", "all"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={`rounded-full px-13 py-[4px] ${filter === f ? "bg-surface-raised font-semibold text-ink" : "text-ink-dim hover:text-ink"}`}
                >
                  {f === "review" ? "Open" : "All"}
                </button>
              ))}
            </div>
            {rows.length === 0 ? (
              <p className="p-13 text-xs text-ink-dim">No errors caught. They appear here as soon as one happens.</p>
            ) : (
              <ul className="max-h-[70vh] space-y-[6px] overflow-y-auto">
                {rows.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(r.id)}
                      className={`w-full space-y-[4px] rounded-card p-8 text-left text-xs transition-colors ${
                        current === r.id ? "bg-white/[0.08]" : "hover:bg-white/[0.04]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-8">
                        <span className="truncate font-mono text-ink">{r.error_type}</span>
                        <Chip status={r.status} />
                      </div>
                      <p className="line-clamp-2 text-ink-dim">{r.title ?? r.message}</p>
                      <p className="text-[11px] text-ink-dim">{SOURCE[r.source]} · {r.occurrences}× · {ago(r.last_seen)}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="glass min-w-0 p-21">
            {current ? <Detail key={current} token={token} id={current} /> : (
              <p className="text-sm text-ink-dim">Select an error to see the agent's fix.</p>
            )}
          </div>
        </div>
      </div>
    </GoldenShell>
  );
}
