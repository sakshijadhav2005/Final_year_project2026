import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { ContentStudio } from "@/components/content/ContentStudio";
import { deleteJob, getJob, getJobContent, getTranscript, regenerateJob, type JobPublic } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";
import { useJobEvents } from "@/hooks/useJobEvents";

export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.accessToken) as string;
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const targetDashboard = user?.role === "regular_user" ? "/user/dashboard" : "/organizer/dashboard";

  const deleteMutation = useMutation({
    mutationFn: () => deleteJob(token, jobId),
    onSuccess: () => {
      queryClient.setQueryData(["jobs"], (old: JobPublic[] | undefined) =>
        Array.isArray(old) ? old.filter((j) => j.id !== jobId) : []
      );
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["my_events"] });
      navigate(targetDashboard);
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
      if (status && ["pending_review", "ready_to_publish", "needs_review", "needs_reupload", "failed", "cancelled"].includes(status)) {
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

  if (job.isError) {
    return (
      <GoldenShell>
        <div className="flex flex-col items-center justify-center py-48 text-center">
          <span className="text-5xl mb-13">🔍</span>
          <h2 className="font-display text-h2 font-semibold mb-8">Job Not Found</h2>
          <p className="text-sm opacity-60 max-w-md mb-21">
            Job <span className=" text-gold-soft">{jobId}</span> does not exist in the current database. This happens if the database was reset or you visited an old session link.
          </p>
          <div className="flex gap-13">
            <Link
              to="/dashboard"
              className="btn-ghost"
            >
              Go to Dashboard
            </Link>
            <Link
              to="/"
              className="rounded-full bg-white/[0.05] border border-white/[0.08] px-21 py-8 text-sm font-medium hover:bg-white/[0.1] transition-all"
            >
              Upload New Recording
            </Link>
          </div>
        </div>
      </GoldenShell>
    );
  }

  return (
    <GoldenShell>
      {/* Header: title on the left, every page action in one row on the right */}
      <div className="mb-34 flex flex-wrap items-end justify-between gap-21">
        <div>
          <Link to="/dashboard" className="text-sm text-ink-dim transition-colors hover:text-ink">
            ← Dashboard
          </Link>
          <h1 className="mt-8 font-display text-h1 font-semibold text-ink">Session {jobId.slice(0, 8)}</h1>
          {isConnected && (
            <p className="mt-8 flex items-center gap-8 text-xs text-teal">
              <span className="live-bars" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              Live updates on
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-8">
          {job.data?.event_id && (
            <Link
              to={`/events/${job.data.event_id}`}
              className="rounded-full border border-white/[0.12] px-21 py-8 text-sm text-ink transition-colors hover:border-amber-400/50"
            >
              Open event
            </Link>
          )}
          {["pending_review", "ready_to_publish", "needs_review", "failed"].includes(currentStatus) && (
            <button
              type="button"
              onClick={() => regenMutation.mutate()}
              disabled={regenMutation.isPending}
              className="rounded-full border border-white/[0.12] px-21 py-8 text-sm text-ink transition-colors hover:border-amber-400/50"
            >
              {regenMutation.isPending ? "Regenerating…" : "Regenerate"}
            </button>
          )}
          <button
            type="button"
            onClick={handleDeleteSession}
            disabled={deleteMutation.isPending}
            className="btn-danger"
            title="Permanently delete this session"
          >
            {deleteMutation.isPending ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>

      {/* Pipeline progress */}
      <div className="mb-34">
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
      <div className="mb-21 flex border-b border-white/[0.08]">
        <button
          type="button"
          onClick={() => setActiveTab("studio")}
          className={`flex items-center gap-8 border-b-2 px-21 py-13 text-sm font-semibold transition-all ${
            activeTab === "studio"
              ? "border-amber-400 text-ink"
              : "border-transparent text-ink-dim hover:text-ink"
          }`}
        >
          <span>Drafts</span>
          {content.data && content.data.length > 0 && (
            <span className="rounded-full bg-white/[0.08] px-8 py-[2px] text-xs text-ink-dim">{content.data.length}</span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("transcript")}
          className={`flex items-center gap-8 border-b-2 px-21 py-13 text-sm font-semibold transition-all ${
            activeTab === "transcript"
              ? "border-amber-400 text-ink"
              : "border-transparent text-ink-dim hover:text-ink"
          }`}
        >
          <span>Transcript</span>
          {transcript.data && <span className="text-xs font-normal text-ink-dim">{transcript.data.badge} confidence</span>}
        </button>
      </div>

      {/* Tab 1: Rich Content Studio */}
      {activeTab === "studio" && (
        <section>
          {content.data && content.data.length > 0 ? (
            <ContentStudio token={token} jobId={jobId} pieces={content.data} />
          ) : (
            <div className="rounded-card border border-dashed border-white/20 p-55 text-center">
              <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-amber-400 border-t-transparent mb-13"></div>
              <p className="font-semibold">Agents are analyzing the recording...</p>
              <p className="mt-[4px] text-xs opacity-60">
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
              className="w-full max-w-sm rounded-card border border-black/10 bg-canvas-light px-13 py-8 text-xs dark:border-white/[0.08] dark:bg-canvas-dark"
            />
            <span className="text-xs opacity-60">
              Words: {transcriptText.trim() ? transcriptText.trim().split(/\s+/).length : 0}
            </span>
          </div>

          <div className="max-h-[65vh] overflow-auto rounded-card border border-black/10 bg-surface-light p-21 text-sm leading-relaxed dark:border-white/[0.08] dark:bg-surface-dark">
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
