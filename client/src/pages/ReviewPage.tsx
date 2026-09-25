import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { approveContent, getJobContent, listJobs, rejectContent } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function ReviewPage() {
  const { contentId = "" } = useParams();
  const token = useAuthStore((s) => s.accessToken) as string;
  const queryClient = useQueryClient();

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
    enabled: Boolean(token && contentId),
  });
  const piece = jobs.data?.piece;
  const approve = useMutation({
    mutationFn: () => approveContent(token, contentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs-for-review", contentId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const reject = useMutation({
    mutationFn: () => rejectContent(token, contentId, "Rejected from review screen"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs-for-review", contentId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
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
              <span className="text-xs opacity-60">
                {piece.status === "approved"
                  ? "✓ Approved"
                  : piece.status === "rejected"
                  ? "✕ Rejected"
                  : "Human approval required for release"}
              </span>
            </div>
            <h2 className="font-display text-xl text-ink-light dark:text-ink-dark">{piece.title}</h2>
            <div className="whitespace-pre-wrap font-sans text-sm leading-relaxed opacity-90">
              {piece.body}
            </div>
            <div className="flex gap-13 pt-13 border-t border-[#D8B478]/15">
              <button
                type="button"
                disabled={approve.isPending || reject.isPending}
                className="rounded-full border border-teal/40 bg-teal/20 px-21 py-13 text-sm font-semibold text-teal hover:bg-teal/30 transition-all disabled:opacity-50"
                onClick={() => approve.mutate()}
              >
                {approve.isPending ? "Approving..." : "✓ Approve & Mark Ready"}
              </button>
              <button
                type="button"
                disabled={approve.isPending || reject.isPending}
                className="rounded-full border border-danger/40 bg-danger/20 px-21 py-13 text-sm font-semibold text-danger hover:bg-danger/30 transition-all disabled:opacity-50"
                onClick={() => reject.mutate()}
              >
                {reject.isPending ? "Rejecting..." : "✕ Reject Draft"}
              </button>
            </div>
          </div>
        ) : jobs.isLoading ? (
          <p className="mt-21 opacity-70 text-xs animate-pulse">Loading content for review…</p>
        ) : (
          <div className="mt-21 rounded-card border border-black/10 dark:border-white/10 p-21 text-center">
            <p className="text-xs text-ink-light/60 dark:text-ink-dim">
              Content piece not found or has been removed.
            </p>
          </div>
        )}
      </div>
    </GoldenShell>
  );
}
