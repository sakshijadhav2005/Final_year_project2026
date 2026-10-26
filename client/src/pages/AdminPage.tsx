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
          <h1 className="font-display text-h1 font-semibold text-ink-light dark:text-ink-dark">Admin Console</h1>
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
            <h1 className="font-display text-h1 font-semibold text-ink-light dark:text-ink-dark">
              Administrative Overview
            </h1>
          </div>

          <Link
            to="/dashboard"
            className="btn-ghost btn-sm"
          >
            ← Back to Dashboard
          </Link>
        </div>

        <div className="grid md:grid-cols-2 gap-21">
          {/* Jobs List */}
          <div className="glass p-21 space-y-13">
            <h2 className="font-display text-h2 text-ink-light dark:text-ink-dark border-b border-line/10 pb-8">
              All Workspace Jobs
            </h2>
            <div className="flex flex-col gap-8 max-h-[60vh] overflow-y-auto">
              {(jobs.data ?? []).length === 0 ? (
                <p className="text-xs opacity-60">No jobs recorded yet.</p>
              ) : (
                jobs.data?.map((job) => (
                  <div key={job.id} className="glass p-13 text-xs flex justify-between items-center">
                    <span className=" text-[11px] opacity-80">{job.id.slice(0, 10)}</span>
                    <span className="font-semibold text-gold-soft text-[10px] bg-gold/10 px-8 py-[2px] rounded-full">
                      {job.status}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Audit Trail */}
          <div className="glass p-21 space-y-13">
            <h2 className="font-display text-h2 text-ink-light dark:text-ink-dark border-b border-line/10 pb-8">
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
