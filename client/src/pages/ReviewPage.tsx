import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { approveContent, getJobContent, listJobs, rejectContent } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function ReviewPage() {
  const { contentId = "" } = useParams();
  const token = useAuthStore((s) => s.accessToken) as string;
  const jobs = useQuery({
    queryKey: ["jobs-for-review", contentId],
    queryFn: async () => {
      const all = await listJobs(token);
      for (const job of all) {
        const pieces = await getJobContent(token, job.id);
        const hit = pieces.find((p) => p.id === contentId);
        if (hit) return { job, piece: hit };
      }
      return null;
    },
  });
  const piece = jobs.data?.piece;
  const approve = useMutation({
    mutationFn: () => approveContent(token, contentId),
  });
  const reject = useMutation({
    mutationFn: () => rejectContent(token, contentId, "Rejected from review screen"),
  });

  return (
    <GoldenShell>
      <div className="max-w-3xl mx-auto">
        <div className="mb-21 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gold">Human Gate Validation</p>
            <h1 className="font-display text-2xl font-bold md:text-3xl text-ink-light dark:text-ink-dark">
              Content Review
            </h1>
          </div>
          {jobs.data?.job && (
            <Link
              to={`/jobs/${jobs.data.job.id}`}
              className="rounded-full border border-gold/30 bg-white/[0.03] px-21 py-8 text-xs font-medium text-gold-soft hover:border-gold transition-all"
            >
              ← Back to Job
            </Link>
          )}
        </div>

        {piece ? (
          <div className="glass p-34 space-y-21 border-gold/25">
            <div className="flex items-center justify-between border-b border-[#D8B478]/15 pb-13">
              <span className="rounded-full bg-gold/15 px-13 py-4 text-xs font-semibold uppercase tracking-wider text-gold-soft">
                {piece.type} · {piece.language.toUpperCase()}
              </span>
              <span className="text-xs opacity-60">Human approval required for release</span>
            </div>
            <h2 className="font-display text-xl text-ink-light dark:text-ink-dark">{piece.title}</h2>
            <div className="whitespace-pre-wrap font-sans text-sm leading-relaxed opacity-90">
              {piece.body}
            </div>
            <div className="flex gap-13 pt-13 border-t border-[#D8B478]/15">
              <button
                type="button"
                className="rounded-full border border-teal/40 bg-teal/20 px-21 py-13 text-sm font-semibold text-teal hover:bg-teal/30 transition-all"
                onClick={() => approve.mutate()}
              >
                ✓ Approve &amp; Mark Ready
              </button>
              <button
                type="button"
                className="rounded-full border border-danger/40 bg-danger/20 px-21 py-13 text-sm font-semibold text-danger hover:bg-danger/30 transition-all"
                onClick={() => reject.mutate()}
              >
                ✕ Reject Draft
              </button>
            </div>
          </div>
        ) : (
          <p className="mt-21 opacity-70">Loading content…</p>
        )}
      </div>
    </GoldenShell>
  );
}
