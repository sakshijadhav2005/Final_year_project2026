import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { DashboardUploadCard } from "@/components/dashboard/DashboardUploadCard";
import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { ChatDrawer } from "@/components/chat/ChatDrawer";
import { deleteJob, getTranscript, listJobs } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

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

  // Strict RBAC filtering: Admin sees all, non-admins see only their jobs
  const userSessions = (jobs.data ?? []).filter((j) => {
    if (!user || user.role === "admin") return true;
    return j.user_id === user.id;
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteJob(token, id),
    onSuccess: (_, deletedId) => {
      queryClient.setQueryData(["jobs"], (old: any) =>
        Array.isArray(old) ? old.filter((j: any) => j.id !== deletedId) : []
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

  const latest = userSessions[0];
  const isLatestActive =
    latest && !["ready_to_publish", "rejected"].includes(latest.status);

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
      <div className="space-y-8">
        {/* Dashboard Top Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-amber-400">Workspace Control</p>
            <h1 className="font-display text-3xl font-bold text-white">
              Executive <em className="not-italic text-amber-300">Dashboard</em>
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Welcome back, <strong className="text-amber-300">{user?.email}</strong> ({user?.role || "organizer"})
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowChatDrawer(true)}
            className="inline-flex items-center gap-2 rounded-full border border-amber-500/40 bg-gradient-to-r from-amber-500/20 via-orange-500/20 to-teal-500/20 px-5 py-2 text-xs font-semibold text-amber-300 shadow-lg hover:scale-105 transition-all"
          >
            <span className="text-sm">🤖</span>
            <span>AI Co-Pilot Assistant</span>
            <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
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
        <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 shadow-xl backdrop-blur-xl transition-all">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-500/10 border border-amber-500/20 text-lg">
                🎙️
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-white">Past Recording Sessions</h2>
                  <span className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
                    {userSessions.length} {userSessions.length === 1 ? "Session" : "Sessions"}
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  {user?.role === "admin"
                    ? "🛡️ Admin View: Showing all system sessions across users"
                    : `👤 Isolated to account: ${user?.email || "Current User"} (${user?.role || "organizer"})`}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowPastSessions((prev) => !prev)}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-slate-200 hover:border-amber-500/40 hover:bg-amber-500/10 hover:text-amber-200 transition-all shadow-sm"
            >
              <span>{showPastSessions ? "▲ Hide Previous Sessions" : "▼ Show All Previous Sessions"}</span>
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold">
                {userSessions.length}
              </span>
            </button>
          </div>

          {/* Expanded Previous Sessions List */}
          {showPastSessions && (
            <div className="mt-5 space-y-3 animate-fadeIn">
              {userSessions.length === 0 ? (
                <div className="rounded-2xl border border-white/5 bg-slate-950/40 p-8 text-center">
                  <span className="text-3xl">📭</span>
                  <p className="mt-2 text-sm font-semibold text-slate-300">No past recording sessions found</p>
                  <p className="mt-1 text-xs text-slate-400">
                    Upload a recording below to automatically transcribe, index, and generate multi-format content.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[420px] overflow-y-auto pr-1">
                  {userSessions.map((job) => {
                    const isReady = job.status === "ready_to_publish";
                    const isPending = job.status === "pending_review";
                    const isFailed = job.status === "failed";

                    return (
                      <Link
                        key={job.id}
                        to={`/jobs/${job.id}`}
                        className="group flex flex-col justify-between rounded-2xl border border-white/10 bg-slate-950/60 p-4 transition-all hover:border-amber-500/40 hover:bg-slate-900/90 hover:shadow-lg hover:shadow-amber-500/5"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2.5">
                            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-amber-300 group-hover:border-amber-500/40">
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
                            className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                              isReady
                                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                : isPending
                                ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                                : isFailed
                                ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                                : "bg-sky-500/15 text-sky-400 border border-sky-500/30"
                            }`}
                          >
                            {job.status.replace("_", " ")}
                          </span>
                        </div>

                        {job.error_message && (
                          <p className="mt-2 text-[11px] text-rose-400 line-clamp-1">⚠️ {job.error_message}</p>
                        )}

                        <div className="mt-3 flex items-center justify-between border-t border-white/5 pt-2.5 text-[11px]">
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
          <section className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                  {isLatestActive ? "⚡ Active Pipeline Execution" : "✦ Most Recent Session"}
                </span>
                <h3 className="font-display text-xl text-white">
                  Session <span className="font-mono text-amber-300">{latest.id.slice(0, 8)}</span>
                </h3>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setShowTranscriptPreview(!showTranscriptPreview)}
                  className="rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 transition-all"
                >
                  {showTranscriptPreview ? "Hide Transcript ✕" : "📜 Show Transcription"}
                </button>
                <Link
                  to={`/jobs/${latest.id}`}
                  className="inline-flex items-center gap-2 rounded-full border border-amber-500/40 bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20 hover:scale-105 transition-all"
                >
                  Open Studio Hub →
                </Link>
                <button
                  type="button"
                  onClick={(e) => handleDeleteSession(e, latest.id)}
                  disabled={deleteMutation.isPending}
                  className="rounded-full border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-xs font-medium text-rose-300 hover:bg-rose-500/20 transition-all"
                  title="Delete this session"
                >
                  🗑️ Delete Session
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
              <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-xl backdrop-blur-xl animate-fadeIn">
                <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                    <span>🎙️ Source Transcription Text</span>
                    {latestTranscript.data?.badge && (
                      <span className="rounded-full bg-amber-500/20 border border-amber-500/30 px-2 py-0.5 text-[10px] uppercase font-bold text-amber-300">
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
                  <div className="py-6 text-center text-xs text-slate-400">
                    <div className="inline-block h-4 w-4 animate-spin rounded-full border border-amber-400 border-t-transparent mr-2" />
                    Fetching latest transcription...
                  </div>
                ) : latestTranscript.data?.full_text ? (
                  <div className="max-h-48 overflow-y-auto rounded-xl bg-slate-950/80 p-4 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed border border-white/5">
                    {latestTranscript.data.full_text}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 text-center py-4">
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
