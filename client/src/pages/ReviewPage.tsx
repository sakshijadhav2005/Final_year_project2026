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
      const all = await listJobs(token, { all: user?.role === "admin" });
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
        <div className="mb-21 flex items-center justify-between">
          <div>
            <h1 className="font-display text-h1 font-semibold text-ink-light dark:text-ink-dark">
              Content Review
            </h1>
          </div>
          {jobs.data?.job && (
            <Link
              to={`/jobs/${jobs.data.job.id}`}
              className="btn-ghost btn-sm"
            >
              ← Back to Job
            </Link>
          )}
        </div>

        {piece ? (
          <div className="glass p-21 md:p-34 space-y-21 border-gold/25">
            <div className="flex items-center justify-between border-b border-line/10 pb-13">
              <span className="rounded-full bg-gold/15 px-13 py-1 text-xs font-semibold text-gold-soft">
                {piece.type} · {piece.language.toUpperCase()}
              </span>
              <span className="text-xs opacity-60">Human approval required for release</span>
            </div>
            <h2 className="font-display text-h2 text-ink-light dark:text-ink-dark">{piece.title}</h2>
            <div className="whitespace-pre-wrap font-sans text-sm leading-relaxed opacity-90">
              {piece.body}
            </div>
            <div className="flex gap-13 pt-13 border-t border-line/10">
              <button
                type="button"
                className="rounded-full border border-teal/40 bg-teal/20 px-21 py-8 text-sm font-semibold text-teal hover:bg-teal/30 transition-all"
                onClick={() => approve.mutate()}
              >
                ✓ Approve &amp; Mark Ready
              </button>
              <button
                type="button"
                className="btn-danger"
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
