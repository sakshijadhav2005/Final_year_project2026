import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { approveContent, getJobContent, listJobs, rejectContent } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function ReviewPage() {
  const { contentId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const token = useAuthStore((s) => s.accessToken) as string;
  const user = useAuthStore((s) => s.user);

  const targetDashboard = user?.role === "regular_user" ? "/user/dashboard" : "/organizer/dashboard";

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["jobs-for-review"] });
      // Redirect to user dashboard if regular_user, or organizer dashboard if organizer
      navigate(targetDashboard);
    },
  });

  const reject = useMutation({
    mutationFn: () => rejectContent(token, contentId, "Rejected from review screen"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["jobs-for-review"] });
      // Redirect to user dashboard if regular_user, or organizer dashboard if organizer
      navigate(targetDashboard);
    },
  });

  return (
    <GoldenShell>
      <div className="max-w-3xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gold">Human Gate Validation</p>
            <h1 className="font-display text-2xl font-bold md:text-3xl text-ink-light dark:text-ink-dark">
              Content Review
            </h1>
          </div>
          {jobs.data?.job && (
            <Link
              to={`/jobs/${jobs.data.job.id}`}
              className="rounded-full border border-gold/30 bg-white/[0.03] px-4 py-2 text-xs font-medium text-gold-soft hover:border-gold transition-all"
            >
              ← Back to Job
            </Link>
          )}
        </div>

        {piece ? (
          <div className="glass p-6 md:p-8 space-y-5 border-gold/25">
            <div className="flex items-center justify-between border-b border-[#D8B478]/15 pb-4">
              <span className="rounded-full bg-gold/15 px-3.5 py-1 text-xs font-semibold uppercase tracking-wider text-gold-soft">
                {piece.type} · {piece.language.toUpperCase()}
              </span>
              <span className="text-xs opacity-60">Human approval required for release</span>
            </div>
            <h2 className="font-display text-xl text-ink-light dark:text-ink-dark">{piece.title}</h2>
            <div className="whitespace-pre-wrap font-sans text-sm leading-relaxed opacity-90">
              {piece.body}
            </div>
            <div className="flex gap-3 pt-4 border-t border-[#D8B478]/15">
              <button
                type="button"
                className="rounded-full border border-teal/40 bg-teal/20 px-5 py-2.5 text-sm font-semibold text-teal hover:bg-teal/30 transition-all"
                onClick={() => approve.mutate()}
              >
                ✓ Approve &amp; Mark Ready
              </button>
              <button
                type="button"
                className="rounded-full border border-danger/40 bg-danger/20 px-5 py-2.5 text-sm font-semibold text-danger hover:bg-danger/30 transition-all"
                onClick={() => reject.mutate()}
              >
                ✕ Reject Draft
              </button>
            </div>
          </div>
        ) : (
          <p className="mt-6 opacity-70">Loading content…</p>
        )}
      </div>
    </GoldenShell>
  );
}
