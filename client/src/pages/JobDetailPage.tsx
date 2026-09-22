import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { ContentStudio } from "@/components/content/ContentStudio";
import { deleteJob, getJob, getJobContent, getTranscript, regenerateJob } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";
import { useJobEvents } from "@/hooks/useJobEvents";

export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.accessToken) as string;
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => deleteJob(token, jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate("/dashboard");
    },
  });

  const handleDeleteSession = () => {
    if (window.confirm(`Are you sure you want to permanently delete session ${jobId.slice(0, 8)}? All generated content and transcripts will be removed.`)) {
      deleteMutation.mutate();
    }
  };

  // Active View Tab: "studio" or "transcript"
  const [activeTab, setActiveTab] = useState<"studio" | "transcript">("studio");
  const [searchQuery, setSearchQuery] = useState("");

  // SSE Real-time Hook
  const { eventData, isConnected } = useJobEvents(jobId, token);

  // Queries
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(token, jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && ["pending_review", "ready_to_publish", "needs_review", "failed", "cancelled"].includes(status)) {
        return false;
      }
      return 3000;
    },
  });

  const transcript = useQuery({
    queryKey: ["transcript", jobId],
    queryFn: () => getTranscript(token, jobId),
    retry: (failureCount, error) => {
      if (error?.message?.includes("404") || error?.message?.includes("not ready")) {
        return failureCount < 5;
      }
      return false;
    },
    refetchInterval: (query) => {
      if (!query.state.data && job.data && !["failed", "cancelled"].includes(job.data.status)) {
        return 3000;
      }
      return false;
    },
    enabled: Boolean(job.data && !["queued", "validating"].includes(job.data.status)),
  });

  const content = useQuery({
    queryKey: ["content", jobId],
    queryFn: () => getJobContent(token, jobId),
    refetchInterval: (query) => {
      const items = query.state.data;
      if (items && items.length > 0) return false;
      return 2500;
    },
  });

  const regenMutation = useMutation({
    mutationFn: () => regenerateJob(token, jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["content", jobId] });
    },
  });

  // Merge SSE progress or query progress
  const progress = eventData?.progress || job.data?.progress || {};
  const currentStatus = eventData?.status || job.data?.status || "loading";
  const errorMessage = eventData?.error_message || job.data?.error_message;

  // Highlight search term in transcript
  const transcriptText = transcript.data?.full_text || "";
  const highlightedTranscript = useMemo(() => {
    if (!searchQuery.trim() || !transcriptText) return transcriptText;
    const parts = transcriptText.split(new RegExp(`(${searchQuery})`, "gi"));
    return parts.map((part, i) =>
      part.toLowerCase() === searchQuery.toLowerCase() ? (
        <mark key={i} className="rounded bg-accent/40 px-1 text-inherit">
          {part}
        </mark>
      ) : (
        part
      ),
    );
  }, [transcriptText, searchQuery]);

  return (
    <GoldenShell>
      {/* Top Breadcrumb & Actions */}
      <div className="mb-21 flex flex-wrap items-center justify-between gap-13">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-gold">Session Content Hub</p>
          <h1 className="font-display text-2xl font-bold md:text-3xl text-ink-light dark:text-ink-dark">
            Job <span className="text-gold-soft font-mono">{jobId.slice(0, 8)}</span>
          </h1>
        </div>
        <div className="flex items-center gap-13">
          <button
            type="button"
            onClick={handleDeleteSession}
            disabled={deleteMutation.isPending}
            className="rounded-full border border-danger/40 bg-danger/10 px-21 py-8 text-xs font-medium text-danger hover:bg-danger/20 transition-all"
            title="Permanently delete this session"
          >
            {deleteMutation.isPending ? "Deleting..." : "🗑️ Delete Session"}
          </button>
          <Link
            to="/dashboard"
            className="rounded-full border border-gold/30 bg-white/[0.03] px-21 py-8 text-xs font-medium text-gold-soft hover:border-gold transition-all"
          >
            ← Back to Dashboard
          </Link>
        </div>
      </div>

      {/* Pipeline Status & Stepper Progression */}
      <div className="mb-21 space-y-13">
        <div className="flex flex-wrap items-center justify-between gap-13">
          <div className="flex items-center gap-13">
            {isConnected && (
              <span className="flex items-center gap-4 text-xs font-semibold text-teal">
                <span className="h-2 w-2 rounded-full bg-teal animate-pulse"></span>
                LIVE SSE UPDATES ACTIVE
              </span>
            )}
          </div>
          {["pending_review", "ready_to_publish", "needs_review"].includes(currentStatus) && (
            <button
              type="button"
              onClick={() => regenMutation.mutate()}
              disabled={regenMutation.isPending}
              className="rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-medium text-gold-soft hover:bg-gold/20 transition-all"
            >
              {regenMutation.isPending ? "Re-queuing..." : "🔄 Regenerate Content Pack"}
            </button>
          )}
        </div>

        <PipelineStepper
          progress={progress}
          jobStatus={currentStatus}
          transcriptConfidence={transcript.data?.badge}
          avgConfidence={transcript.data?.avg_confidence}
        />
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="mb-21 rounded-card border border-danger/40 bg-danger/10 p-13 text-sm text-danger">
          ⚠️ {errorMessage}
        </div>
      )}

      {/* Main Switcher: Content Studio vs Source Transcript */}
      <div className="mb-21 flex border-b border-black/10 dark:border-white/10">
        <button
          type="button"
          onClick={() => setActiveTab("studio")}
          className={`flex items-center gap-8 border-b-2 px-21 py-13 text-sm font-semibold transition-all ${
            activeTab === "studio"
              ? "border-primary text-primary"
              : "border-transparent opacity-60 hover:opacity-100"
          }`}
        >
          <span>✨ Content Studio</span>
          {content.data && content.data.length > 0 && (
            <span className="rounded-full bg-primary/20 px-8 py-1 text-xs">{content.data.length}</span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("transcript")}
          className={`flex items-center gap-8 border-b-2 px-21 py-13 text-sm font-semibold transition-all ${
            activeTab === "transcript"
              ? "border-primary text-primary"
              : "border-transparent opacity-60 hover:opacity-100"
          }`}
        >
          <span>📜 Source Transcript</span>
          {transcript.data && <span className="text-xs opacity-60">({transcript.data.badge})</span>}
        </button>
      </div>

      {/* Tab 1: Rich Content Studio */}
      {activeTab === "studio" && (
        <section>
          {content.data && content.data.length > 0 ? (
            <ContentStudio token={token} jobId={jobId} pieces={content.data} />
          ) : (
            <div className="rounded-card border border-dashed border-primary/30 p-55 text-center">
              <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mb-13"></div>
              <p className="font-semibold">Agents are analyzing the recording...</p>
              <p className="mt-4 text-xs opacity-60">
                Topics, highlights, speakers, and generation will appear in real time.
              </p>
            </div>
          )}
        </section>
      )}

      {/* Tab 2: Transcript Viewer */}
      {activeTab === "transcript" && (
        <section className="flex flex-col gap-13">
          <div className="flex items-center justify-between">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search transcript..."
              className="w-full max-w-sm rounded-card border border-black/10 bg-canvas-light px-13 py-8 text-xs dark:border-white/10 dark:bg-canvas-dark"
            />
            <span className="text-xs opacity-60">
              Words: {transcriptText.trim() ? transcriptText.trim().split(/\s+/).length : 0}
            </span>
          </div>

          <div className="max-h-[65vh] overflow-auto rounded-card border border-black/10 bg-surface-light p-21 text-sm font-mono leading-relaxed dark:border-white/10 dark:bg-surface-dark">
            {transcript.data ? (
              <div className="whitespace-pre-wrap">{highlightedTranscript}</div>
            ) : (
              <p className="text-xs opacity-60">Waiting for transcription engine...</p>
            )}
          </div>
        </section>
      )}
    </GoldenShell>
  );
}
