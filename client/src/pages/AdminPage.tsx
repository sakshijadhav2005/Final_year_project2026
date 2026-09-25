import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listAdminJobs, listAudit } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function AdminPage() {
  const token = useAuthStore((s) => s.accessToken) as string;
  const role = useAuthStore((s) => s.user?.role);
  const jobs = useQuery({ queryKey: ["admin-jobs"], queryFn: () => listAdminJobs(token), enabled: role === "admin" });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => listAudit(token), enabled: role === "admin" });

  if (role !== "admin") {
    return (
      <GoldenShell>
        <div className="max-w-md mx-auto py-55 text-center">
          <h1 className="font-display text-2xl font-bold text-ink-light dark:text-ink-dark">Admin Console</h1>
          <p className="mt-13 text-sm text-ink-dim">Admin role required. Sign in or register as an administrator.</p>
        </div>
      </GoldenShell>
    );
  }

  return (
    <GoldenShell>
      <div className="space-y-34">
        <div className="flex flex-wrap items-center justify-between gap-13">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gold">System Management</p>
            <h1 className="font-display text-3xl font-normal italic text-ink-light dark:text-ink-dark">
              Administrative <em className="not-italic text-gold-soft">Overview</em>
            </h1>
          </div>

          <Link
            to="/dashboard"
            className="rounded-full border border-gold/30 bg-surface-light/80 dark:bg-white/[0.03] px-21 py-8 text-xs font-medium text-gold hover:border-gold transition-all dark:text-gold-soft"
          >
            ← Back to Dashboard
          </Link>
        </div>

        <div className="grid md:grid-cols-2 gap-21">
          {/* Jobs List */}
          <div className="glass p-21 space-y-13">
            <h2 className="font-display text-lg text-ink-light dark:text-ink-dark border-b border-[#D8B478]/15 pb-8">
              All Workspace Jobs
            </h2>
            <div className="flex flex-col gap-8 max-h-[60vh] overflow-y-auto">
              {(jobs.data ?? []).length === 0 ? (
                <p className="text-xs opacity-60">No jobs recorded yet.</p>
              ) : (
                jobs.data?.map((job) => (
                  <div key={job.id} className="glass p-13 text-xs flex justify-between items-center">
                    <span className="font-mono text-[11px] opacity-80">{job.id.slice(0, 10)}</span>
                    <span className="font-semibold uppercase text-gold-soft text-[10px] bg-gold/10 px-8 py-2 rounded-full">
                      {job.status}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Audit Trail */}
          <div className="glass p-21 space-y-13">
            <h2 className="font-display text-lg text-ink-light dark:text-ink-dark border-b border-[#D8B478]/15 pb-8">
              Audit Trail
            </h2>
            <div className="flex flex-col gap-8 max-h-[60vh] overflow-y-auto">
              {(audit.data ?? []).length === 0 ? (
                <p className="text-xs opacity-60">No audit events logged.</p>
              ) : (
                audit.data?.slice(0, 20).map((row) => (
                  <div key={String(row.id)} className="glass p-13 text-xs flex justify-between">
                    <span className="font-medium text-ink-light dark:text-ink-dark">{row.action}</span>
                    <span className="opacity-60 text-[11px]">{row.resource_type}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </GoldenShell>
  );
}
