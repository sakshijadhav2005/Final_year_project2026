import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { DashboardUploadCard } from "@/components/dashboard/DashboardUploadCard";
import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { ChatDrawer } from "@/components/chat/ChatDrawer";
import { deleteJob, getTranscript, listJobs, type JobPublic } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

// Mirrors the server's TERMINAL set: the pipeline has stopped working on these.
const FINISHED_STATUSES = new Set([
  "pending_review",
  "ready_to_publish",
  "needs_reupload",
  "needs_review",
  "failed",
  "cancelled",
  "rejected",
]);

export function DashboardPage() {
  const token = useAuthStore((s) => s.accessToken) as string;
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const [showTranscriptPreview, setShowTranscriptPreview] = useState(false);
  const [showChatDrawer, setShowChatDrawer] = useState(false);
  const [showPastSessions, setShowPastSessions] = useState(false);

  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => (token ? listJobs(token) : Promise.resolve([])),
    enabled: Boolean(token),
    refetchInterval: token ? 3000 : false,
  });

  // Only the signed-in person's own sessions, for every role. The server already
  // scopes /jobs to the caller; this filter is a second line of defence.
  // (Admins see everyone's sessions on the Admin page, not on their dashboard.)
  const userSessions = (jobs.data ?? []).filter((j) => Boolean(user) && j.user_id === user?.id);

  // Sessions that were still running while this page was open. Finished ones from
  // earlier visits stay in "Past Recording Sessions" and are not shown up top.
  const [watched, setWatched] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    const running = userSessions.filter((j) => !FINISHED_STATUSES.has(j.status)).map((j) => j.id);
    if (running.some((id) => !watched.has(id))) {
      setWatched((prev) => new Set([...prev, ...running]));
    }
  }, [userSessions, watched]);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteJob(token, id),
    onSuccess: (_, deletedId) => {
      queryClient.setQueryData(["jobs"], (old: JobPublic[] | undefined) =>
        Array.isArray(old) ? old.filter((j) => j.id !== deletedId) : []
      );
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["my_events"] });
      queryClient.invalidateQueries({ queryKey: ["transcript"] });
    },
  });

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to permanently delete session ${id.slice(0, 8)}? All generated content and transcripts will be removed.`)) {
      deleteMutation.mutate(id);
    }
  };

  // The pipeline panel shows a session only while it runs (or just finished during
  // this visit), never an old session from before.
  const latest =
    userSessions.find((j) => !FINISHED_STATUSES.has(j.status)) ??
    userSessions.find((j) => watched.has(j.id));
  const isLatestActive = Boolean(latest && !FINISHED_STATUSES.has(latest.status));

  // Fetch transcript for latest job if available
  const latestTranscript = useQuery({
    queryKey: ["transcript", latest?.id],
    queryFn: () => getTranscript(token, latest!.id),
    enabled: Boolean(
      latest?.id &&
        !["queued", "validating"].includes(latest?.status || "") &&
        showTranscriptPreview,
    ),
    retry: false,
  });

  return (
    <GoldenShell>
      <div className="space-y-34">
        {/* Dashboard Top Header */}
        <div className="flex flex-wrap items-center justify-between gap-13">
          <div>
                        <h1 className="font-display text-h1 font-semibold text-white">
              Dashboard
            </h1>
            <p className="mt-8 text-sm text-ink-dim">
              Signed in as <span className="text-ink">{user?.email}</span>
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowChatDrawer(true)}
            className="inline-flex items-center gap-8 rounded-full border border-amber-500/40 bg-amber-500/20 px-21 py-8 text-xs font-semibold text-amber-300 transition-all"
          >
            <span>Ask the co-pilot</span>
          </button>
        </div>

        <ChatDrawer
          isOpen={showChatDrawer}
          onClose={() => setShowChatDrawer(false)}
          jobId={latest?.id}
        />

        {/* Step 1: Catalog Navigation */}
        <section>
          <CatalogNav />
        </section>

        {/* Step 2: Past Recording Sessions Section (Above Upload with RBAC) */}
        <section className="rounded-panel border border-white/[0.08] bg-surface p-21 transition-all">
          <div className="flex flex-wrap items-center justify-between gap-13">
            <div className="flex items-center gap-13">
              <div className="flex h-10 w-10 items-center justify-center rounded-panel bg-amber-500/10 border border-amber-500/20 text-lg">
                🎙️
              </div>
              <div>
                <div className="flex items-center gap-8">
                  <h2 className="text-h2 font-semibold text-white">Past Recording Sessions</h2>
                  <span className="rounded-full bg-amber-500/20 px-8 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
                    {userSessions.length} {userSessions.length === 1 ? "Session" : "Sessions"}
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  {user?.role === "admin"
                    ? `👤 Your own sessions (${user.email}). Every user's sessions are on the Admin page.`
                    : `👤 Only your sessions: ${user?.email || "Current User"} (${user?.role || "organizer"})`}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowPastSessions((prev) => !prev)}
              className="inline-flex items-center gap-8 rounded-card border border-white/[0.08] bg-white/5 px-13 py-8 text-xs font-semibold text-slate-200 hover:border-amber-500/40 hover:bg-amber-500/10 hover:text-amber-200 transition-all"
            >
              <span>{showPastSessions ? "▲ Hide Previous Sessions" : "▼ Show All Previous Sessions"}</span>
              <span className="rounded-full bg-white/10 px-8 py-0.5 text-[10px] font-bold">
                {userSessions.length}
              </span>
            </button>
          </div>

          {/* Expanded Previous Sessions List */}
          {showPastSessions && (
            <div className="mt-21 space-y-13 border-t border-white/[0.08] pt-21">
              {userSessions.length === 0 ? (
                <div className="rounded-panel border border-white/5 bg-white/[0.02] p-34 text-center">
                  <span className="text-3xl">📭</span>
                  <p className="mt-8 text-sm font-semibold text-slate-300">No past recording sessions found</p>
                  <p className="mt-1 text-xs text-slate-400">
                    Upload a recording below to automatically transcribe, index, and generate multi-format content.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-13 max-h-[420px] overflow-y-auto pr-1">
                  {userSessions.map((job) => {
                    const isReady = job.status === "ready_to_publish";
                    const isPending = job.status === "pending_review";
                    const isFailed = job.status === "failed";

                    return (
                      <Link
                        key={job.id}
                        to={`/jobs/${job.id}`}
                        className="glass-interactive neu-raised group flex flex-col justify-between rounded-panel border border-white/[0.08] bg-white/[0.02] p-13"
                      >
                        <div className="flex items-start justify-between gap-13">
                          <div className="flex items-center gap-8">
                            <div className="flex h-[32px] w-[32px] items-center justify-center rounded-card bg-white/5 border border-white/[0.08] text-xs font-bold text-amber-300 group-hover:border-amber-500/40">
                              ⚡
                            </div>
                            <div>
                              <h4 className="text-xs font-bold text-white group-hover:text-amber-300 transition-colors">
                                Session {job.id.slice(0, 8)}
                              </h4>
                              <p className="text-[10px] text-slate-400">
                                {job.created_at ? new Date(job.created_at).toLocaleString() : "Recently"}
                              </p>
                            </div>
                          </div>

                          <span
                            className={`rounded-full px-8 py-0.5 text-[10px] font-bold ${
                              isReady
                                ? "bg-emerald-500/15 text-emerald-400 border border-white/[0.08]"
                                : isPending
                                ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                                : isFailed
                                ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                                : "bg-sky-500/15 text-sky-400 border border-white/[0.08]"
                            }`}
                          >
                            {job.status.replace("_", " ")}
                          </span>
                        </div>

                        {job.error_message && (
                          <p className="mt-8 text-[11px] text-rose-400 line-clamp-1">⚠️ {job.error_message}</p>
                        )}

                        <div className="mt-13 flex items-center justify-between border-t border-white/5 pt-8 text-[11px]">
                          <span className="text-amber-400 font-semibold group-hover:underline">
                            Open in Studio Hub →
                          </span>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteSession(e, job.id)}
                            className="rounded-lg p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                            title="Delete session"
                          >
                            🗑️
                          </button>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </section>

        {/* Step 3: Upload Options Card */}
        <section>
          <DashboardUploadCard />
        </section>

        {/* Step 2 & 3: Active Session Progression & Transcription */}
        {latest && (
          <section className="space-y-13">
            <div className="flex flex-wrap items-center justify-between gap-13">
              <div>
                <p className="text-sm text-ink-dim">{isLatestActive ? "Processing now" : "Just finished"}</p>
                <h2 className="mt-4 font-display text-h2 font-semibold text-ink">Session {latest.id.slice(0, 8)}</h2>
              </div>

              <div className="flex items-center gap-13">
                <button
                  type="button"
                  onClick={() => setShowTranscriptPreview(!showTranscriptPreview)}
                  className="rounded-full border border-amber-500/30 bg-amber-500/10 px-13 py-8 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 transition-all"
                >
                  {showTranscriptPreview ? "Hide transcript" : "Show transcript"}
                </button>
                <Link
                  to={`/jobs/${latest.id}`}
                  className="btn-primary btn-sm"
                >
                  Open drafts
                </Link>
                <button
                  type="button"
                  onClick={(e) => handleDeleteSession(e, latest.id)}
                  disabled={deleteMutation.isPending}
                  className="rounded-full border border-rose-500/40 bg-rose-500/10 px-13 py-8 text-xs font-medium text-rose-300 hover:bg-rose-500/20 transition-all"
                  title="Delete this session"
                >
                  Delete
                </button>
              </div>
            </div>

            {/* Pipeline Stepper Component */}
            <PipelineStepper
              progress={latest.progress ?? {}}
              jobStatus={latest.status}
              transcriptConfidence={latestTranscript.data?.badge}
              avgConfidence={latestTranscript.data?.avg_confidence}
            />

            {/* Optional Collapsible Transcript Preview */}
            {showTranscriptPreview && (
              <div className="rounded-panel border border-white/[0.08] bg-surface p-21 animate-fadeIn">
                <div className="flex items-center justify-between border-b border-white/[0.08] pb-13 mb-13">
                  <div className="flex items-center gap-8 text-xs font-semibold text-amber-300">
                    <span>🎙️ Source Transcription Text</span>
                    {latestTranscript.data?.badge && (
                      <span className="rounded-full bg-amber-500/20 border border-amber-500/30 px-8 py-0.5 text-[10px] font-bold text-amber-300">
                        {latestTranscript.data.badge} confidence
                      </span>
                    )}
                  </div>
                  <Link
                    to={`/jobs/${latest.id}`}
                    className="text-xs text-amber-400 hover:text-amber-300 hover:underline font-semibold"
                  >
                    Open in Studio to Search &amp; Edit →
                  </Link>
                </div>

                {latestTranscript.isLoading ? (
                  <div className="py-21 text-center text-xs text-slate-400">
                    <div className="inline-block h-4 w-4 animate-spin rounded-full border border-amber-400 border-t-transparent mr-8" />
                    Fetching latest transcription...
                  </div>
                ) : latestTranscript.data?.full_text ? (
                  <div className="max-h-48 overflow-y-auto rounded-card bg-white/[0.02] p-13 text-xs text-slate-300 whitespace-pre-wrap leading-relaxed border border-white/5">
                    {latestTranscript.data.full_text}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 text-center py-13">
                    Transcription is currently being indexed by the engine or not yet available.
                  </p>
                )}
              </div>
            )}
          </section>
        )}
      </div>
    </GoldenShell>
  );
}
