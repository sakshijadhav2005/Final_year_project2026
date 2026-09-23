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
  const queryClient = useQueryClient();
  const [showTranscriptPreview, setShowTranscriptPreview] = useState(false);
  const [showChatDrawer, setShowChatDrawer] = useState(false);

  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => listJobs(token),
    refetchInterval: 3000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteJob(token, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to permanently delete session ${id.slice(0, 8)}? All generated content and transcripts will be removed.`)) {
      deleteMutation.mutate(id);
    }
  };

  const latest = jobs.data?.[0];
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
      {/* Dashboard Top Header */}
      <div className="mb-21 flex flex-wrap items-center justify-between gap-13">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-gold">Workspace Control</p>
          <h1 className="font-display text-3xl font-normal italic text-ink-light dark:text-ink-dark">
            Executive <em className="not-italic text-gold-soft">Dashboard</em>
          </h1>
        </div>

        <button
          type="button"
          onClick={() => setShowChatDrawer(true)}
          className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gradient-to-r from-gold/20 via-orange-500/20 to-teal/20 px-21 py-8 text-xs font-semibold text-gold-soft shadow-lg hover:scale-105 transition-all"
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


      <div className="space-y-34">
        {/* Step 1: Upload Options Card */}
        <section className="mb-6">
          <CatalogNav />
        </section>
        <section>
          <DashboardUploadCard />
        </section>

        {/* Step 2 & 3: Active Session Progression & Transcription */}
        {latest && (
          <section className="space-y-13">
            <div className="flex flex-wrap items-center justify-between gap-13">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-gold">
                  {isLatestActive ? "⚡ Active Pipeline Execution" : "✦ Most Recent Session"}
                </span>
                <h3 className="font-display text-xl text-ink-light dark:text-ink-dark">
                  Session <span className="font-mono text-gold-soft">{latest.id.slice(0, 8)}</span>
                </h3>
              </div>

              <div className="flex items-center gap-13">
                <button
                  type="button"
                  onClick={() => setShowTranscriptPreview(!showTranscriptPreview)}
                  className="rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-medium text-gold-soft hover:bg-gold/20 transition-all"
                >
                  {showTranscriptPreview ? "Hide Transcript ✕" : "📜 Show Transcription"}
                </button>
                <Link
                  to={`/jobs/${latest.id}`}
                  className="inline-flex items-center gap-8 rounded-full border border-gold/40 bg-gradient-to-r from-gold/20 to-teal/15 px-21 py-4 text-xs font-medium text-gold-soft hover:scale-105 transition-all"
                >
                  Open Studio Hub →
                </Link>
                <button
                  type="button"
                  onClick={(e) => handleDeleteSession(e, latest.id)}
                  disabled={deleteMutation.isPending}
                  className="rounded-full border border-danger/40 bg-danger/10 px-13 py-4 text-xs font-medium text-danger hover:bg-danger/20 transition-all"
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
              <div className="glass p-21 border-gold/20 animate-fadeIn">
                <div className="flex items-center justify-between border-b border-[#D8B478]/15 pb-8 mb-13">
                  <div className="flex items-center gap-8 text-xs font-semibold text-gold">
                    <span>🎙️ Source Transcription Text</span>
                    {latestTranscript.data?.badge && (
                      <span className="rounded-full bg-gold/20 px-8 py-1 text-[10px] uppercase">
                        {latestTranscript.data.badge} confidence
                      </span>
                    )}
                  </div>
                  <Link
                    to={`/jobs/${latest.id}`}
                    className="text-xs text-gold-soft hover:underline"
                  >
                    Open in Studio to Search &amp; Edit →
                  </Link>
                </div>

                {latestTranscript.isLoading ? (
                  <div className="py-21 text-center text-xs opacity-60">
                    <div className="inline-block h-4 w-4 animate-spin rounded-full border border-gold border-t-transparent mr-8" />
                    Fetching latest transcription...
                  </div>
                ) : latestTranscript.data?.full_text ? (
                  <div className="max-h-48 overflow-y-auto rounded bg-black/20 p-13 font-mono text-xs text-ink-dim whitespace-pre-wrap leading-relaxed">
                    {latestTranscript.data.full_text}
                  </div>
                ) : (
                  <p className="text-xs opacity-60 text-center py-13">
                    Transcription is currently being indexed by the engine or not yet available.
                  </p>
                )}
              </div>
            )}
          </section>
        )}

        {/* Step 4: Session History List */}
        <section>
          <div className="mb-13">
            <span className="text-xs font-semibold uppercase tracking-wider text-gold">Archive</span>
            <h3 className="font-display text-xl text-ink-light dark:text-ink-dark">
              Past Recording Sessions
            </h3>
            <p className="text-xs text-ink-dim">
              Click any previous session to review generated copy, edit drafts, or mark ready to publish.
            </p>
          </div>

          <div className="flex flex-col gap-13">
            {(jobs.data ?? []).map((job) => {
              const isReady = job.status === "ready_to_publish";
              const isPending = job.status === "pending_review";
              const isFailed = job.status === "failed";

              return (
                <Link
                  key={job.id}
                  to={`/jobs/${job.id}`}
                  className="glass group p-21 transition-all hover:scale-[1.01] hover:border-gold/50"
                >
                  <div className="flex flex-wrap items-center justify-between gap-13">
                    <div className="flex items-center gap-13">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.04] border border-white/10 font-display font-semibold text-gold-soft group-hover:border-gold transition-colors">
                        ✦
                      </div>
                      <div>
                        <h4 className="font-display text-base font-medium capitalize text-ink-light dark:text-ink-dark">
                          Session {job.id.slice(0, 8)}
                        </h4>
                        <p className="text-xs text-ink-dim">
                          {job.created_at ? new Date(job.created_at).toLocaleString() : "Just now"}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-13">
                      <span
                        className={`rounded-full px-13 py-4 text-xs font-semibold uppercase tracking-wider ${
                          isReady
                            ? "bg-success/15 text-success border border-success/30"
                            : isPending
                            ? "bg-gold/15 text-gold-soft border border-gold/30"
                            : isFailed
                            ? "bg-danger/15 text-danger border border-danger/30"
                            : "bg-teal/15 text-teal border border-teal/30"
                        }`}
                      >
                        {job.status.replace("_", " ")}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteSession(e, job.id)}
                        className="rounded-lg p-2 text-xs text-ink-dim hover:text-danger hover:bg-danger/10 transition-colors z-10"
                        title="Delete Session"
                      >
                        🗑️
                      </button>
                      <span className="text-sm text-gold-soft opacity-0 transition-opacity group-hover:opacity-100">
                        →
                      </span>
                    </div>
                  </div>

                  {job.error_message && (
                    <p className="mt-13 text-xs text-danger">⚠️ {job.error_message}</p>
                  )}
                </Link>
              );
            })}

            {jobs.data?.length === 0 && (
              <div className="glass p-34 text-center">
                <p className="text-sm opacity-60">No recording sessions found yet.</p>
                <p className="text-xs text-ink-dim mt-4">
                  Use the upload section above to submit your first audio or video file.
                </p>
              </div>
            )}
          </div>
        </section>
      </div>
    </GoldenShell>
  );
}
