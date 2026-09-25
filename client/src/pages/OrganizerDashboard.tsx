import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { GoldenShell } from "@/layouts/GoldenShell";
import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { DashboardUploadCard } from "@/components/dashboard/DashboardUploadCard";
import { EventCard } from "@/components/dashboard/EventCard";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { ChatDrawer } from "@/components/chat/ChatDrawer";
import {
  listEvents,
  createEvent,
  deleteEvent,
  listJobs,
  deleteJob,
  getTranscript,
  type EventPublic,
  type EventType,
} from "@/lib/api";
import { useAuthStore } from "@/store/auth";

const TERMINAL_JOB_STATUSES = new Set([
  "pending_review",
  "ready_to_publish",
  "needs_reupload",
  "needs_review",
  "failed",
  "cancelled",
]);

export function OrganizerDashboard() {
  const token = useAuthStore((s) => s.accessToken) as string;
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showTranscriptPreview, setShowTranscriptPreview] = useState(false);
  const [showChatDrawer, setShowChatDrawer] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedUploadEventId, setSelectedUploadEventId] = useState<string | undefined>(undefined);

  // Form state for Event Creation
  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [selectedType, setSelectedType] = useState<EventType>("event");
  const [topic, setTopic] = useState("");
  const [organizerName, setOrganizerName] = useState("");
  const [formErrors, setFormErrors] = useState<{
    name?: string;
    date?: string;
    topic?: string;
    organizerName?: string;
  }>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Queries
  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ["events"],
    queryFn: () => (token ? listEvents(token) : Promise.resolve([])),
    enabled: !!token,
  });

  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => (token ? listJobs(token) : Promise.resolve([])),
    refetchInterval: 3000,
    enabled: !!token,
  });

  // Event Mutations
  const createEventMutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("Not authenticated");
      const trimmedName = name.trim();
      const trimmedTopic = topic.trim();
      const trimmedOrg = organizerName.trim();

      const errors: { name?: string; date?: string; topic?: string; organizerName?: string } = {};
      if (!trimmedName) {
        errors.name = "Event name is required";
      } else if (trimmedName.length > 255) {
        errors.name = "Event name cannot exceed 255 characters";
      }

      if (!date) {
        errors.date = "Event date is required";
      }

      if (trimmedTopic.length > 255) {
        errors.topic = "Topic cannot exceed 255 characters";
      }

      if (trimmedOrg.length > 255) {
        errors.organizerName = "Organizer name cannot exceed 255 characters";
      }

      if (Object.keys(errors).length > 0) {
        setFormErrors(errors);
        throw new Error("Please correct the form validation errors before saving.");
      }

      return createEvent(token, {
        name: trimmedName,
        date,
        topic: trimmedTopic || undefined,
        organizer_name: trimmedOrg || undefined,
        type: selectedType,
      });
    },
    onSuccess: (newEvent) => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setShowCreateModal(false);
      setName("");
      setDate("");
      setTopic("");
      setOrganizerName("");
      setFormErrors({});
      setActionError(null);
      setSuccessMessage(`Event "${newEvent.name}" was created successfully!`);
      setTimeout(() => setSuccessMessage(null), 5000);
    },
    onError: (err: Error) => {
      setActionError(err.message || "Failed to create event");
    },
  });

  const deleteEventMutation = useMutation({
    mutationFn: (eventId: string) => deleteEvent(token, eventId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setActionError(null);
    },
    onError: (err: Error) => {
      setActionError(err.message || "Failed to delete event");
    },
  });

  // Job Delete Mutation
  const deleteJobMutation = useMutation({
    mutationFn: (jobId: string) => deleteJob(token, jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setActionError(null);
    },
    onError: (err: Error) => {
      setActionError(err.message || "Failed to delete session");
    },
  });

  const handleDeleteEvent = (e: React.MouseEvent, event: EventPublic) => {
    e.preventDefault();
    e.stopPropagation();
    if (
      window.confirm(
        `Are you sure you want to permanently delete event "${event.name}"? This action cannot be undone.`,
      )
    ) {
      deleteEventMutation.mutate(event.id);
    }
  };

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (
      window.confirm(
        `Are you sure you want to permanently delete session ${id.slice(0, 8)}? All generated content and transcripts will be removed.`,
      )
    ) {
      deleteJobMutation.mutate(id);
    }
  };

  // Derive Job Metrics
  const jobsList = jobs.data ?? [];
  const latest = jobsList[0];
  const activeJobs = jobsList.filter((j) => !TERMINAL_JOB_STATUSES.has(j.status));
  const activeProcessingCount = activeJobs.length;
  const isLatestActive = latest && !TERMINAL_JOB_STATUSES.has(latest.status);
  const pipelineStatus: "Active" | "Ready" = activeProcessingCount > 0 ? "Active" : "Ready";

  // Transcript query for latest job
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
      {/* Organizer Header */}
      <div className="mb-21 flex flex-wrap items-center justify-between gap-13">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-gold">
            Workspace Control
          </p>
          <h1 className="font-display text-3xl font-normal italic text-ink-light dark:text-ink-dark">
            Organizer <em className="not-italic text-gold-soft">Dashboard</em>
          </h1>
          <p className="mt-1 text-xs text-ink-light/70 dark:text-ink-dim">
            Manage your events, recordings, and AI-generated content.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-13">
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 transition-all shadow-sm"
          >
            <span>➕</span>
            <span>Create Event</span>
          </button>

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
      </div>

      <ChatDrawer
        isOpen={showChatDrawer}
        onClose={() => setShowChatDrawer(false)}
        jobId={latest?.id}
      />

      {/* Global Error Banner */}
      {actionError && (
        <div className="mb-21 rounded-card border border-danger/30 bg-danger/15 p-13 text-xs text-danger flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{actionError}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="text-danger hover:underline font-bold px-2 py-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Global Success Banner */}
      {successMessage && (
        <div className="mb-21 rounded-card border border-teal/40 bg-teal/15 p-13 text-xs text-teal flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>✅</span>
            <span>{successMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            className="text-teal hover:underline font-bold px-2 py-1"
          >
            ✕
          </button>
        </div>
      )}

      <div className="space-y-34">
        {/* Section 1: Stats Grid */}
        <section>
          <StatsGrid
            eventsCount={events.length}
            totalSessions={jobsList.length}
            activeProcessingCount={activeProcessingCount}
            pipelineStatus={pipelineStatus}
            isLoading={eventsLoading || jobs.isLoading}
          />
        </section>

        {/* Section 2: Catalog Navigation */}
        <section>
          <CatalogNav />
        </section>

        {/* Section 3: Managed Events */}
        <section className="space-y-13">
          <div className="flex flex-wrap items-center justify-between gap-13">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-gold">
                Catalog Administration
              </span>
              <div className="flex items-center gap-8">
                <h3 className="font-display text-xl text-ink-light dark:text-ink-dark">
                  Your Managed Events
                </h3>
                <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-1 text-xs font-medium text-gold dark:text-gold-soft">
                  {events.length} {events.length === 1 ? "Event" : "Events"}
                </span>
              </div>
              <p className="text-xs text-ink-dim mt-1">
                Events you coordinate, review recordings for, and publish AI content pieces from.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-medium text-gold-soft hover:bg-gold/20 transition-all"
            >
              <span>➕ New Event</span>
            </button>
          </div>

          {eventsLoading ? (
            <div className="glass p-34 text-center">
              <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gold border-t-transparent" />
              <p className="mt-8 text-xs text-ink-dim">Loading managed events...</p>
            </div>
          ) : events.length === 0 ? (
            <div className="glass p-34 text-center rounded-card border border-gold/20">
              <span className="text-3xl">🎪</span>
              <h4 className="mt-8 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
                No events yet
              </h4>
              <p className="mt-4 text-xs text-ink-dim max-w-md mx-auto">
                Create your first event to start organizing recordings and AI-generated content.
              </p>
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="mt-13 inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 transition-all"
              >
                <span>➕</span>
                <span>Create Event</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-21 md:grid-cols-2 lg:grid-cols-3">
              {events.map((event) => {
                const isOwner = user?.role === "admin" || event.organizer_id === user?.id;

                return (
                  <div key={event.id} className="flex flex-col group/item">
                    {/* Organizer Management Bar */}
                    <div className="flex items-center justify-between rounded-t-card border-x border-t border-gold/20 bg-surface-light/80 dark:bg-white/[0.03] px-13 py-4 text-[11px] text-ink-light/60 dark:text-ink-dim">
                      <span className="font-mono text-[10px] text-gold-soft">
                        ID: {event.id.slice(0, 8)}
                      </span>

                      <div className="flex items-center gap-8">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedUploadEventId(event.id);
                            document.getElementById("upload-section")?.scrollIntoView({ behavior: "smooth" });
                          }}
                          className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] transition-colors ${
                            selectedUploadEventId === event.id
                              ? "bg-teal/20 text-teal font-semibold"
                              : "text-gold hover:text-gold-soft hover:bg-gold/10"
                          }`}
                          title="Select this event for recording upload"
                        >
                          <span>🎙️</span>
                          <span>{selectedUploadEventId === event.id ? "Selected for Upload" : "Upload Recording"}</span>
                        </button>

                        {isOwner && (
                          <button
                            type="button"
                            onClick={(e) => handleDeleteEvent(e, event)}
                            disabled={deleteEventMutation.isPending}
                            className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-danger/80 hover:text-danger hover:bg-danger/10 transition-colors"
                            title="Delete Event"
                          >
                            <span>🗑️</span>
                            <span>Delete</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Shared EventCard */}
                    <div className="[&>div]:rounded-t-none [&>div]:border-t-0">
                      <EventCard event={event} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Section 4: Ingest Recording */}
        <section id="upload-section" className="space-y-13">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-gold">
              Media Ingestion
            </span>
            <h3 className="font-display text-xl text-ink-light dark:text-ink-dark">
              Ingest Recording
            </h3>
            <p className="text-xs text-ink-dim mt-1">
              Upload conference audio or keynote video to generate multi-format AI content.
            </p>
          </div>

          <DashboardUploadCard
            events={events}
            selectedEventId={selectedUploadEventId}
            onSelectEventId={setSelectedUploadEventId}
          />
        </section>

        {/* Section 5: Active Processing & Stepper */}
        {latest ? (
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
                  disabled={deleteJobMutation.isPending}
                  className="rounded-full border border-danger/40 bg-danger/10 px-13 py-4 text-xs font-medium text-danger hover:bg-danger/20 transition-all"
                  title="Delete this session"
                >
                  🗑️ Delete Session
                </button>
              </div>
            </div>

            <PipelineStepper
              progress={latest.progress ?? {}}
              jobStatus={latest.status}
              transcriptConfidence={latestTranscript.data?.badge}
              avgConfidence={latestTranscript.data?.avg_confidence}
            />

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
        ) : (
          <section className="space-y-13">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-gold">
                Pipeline Engine
              </span>
              <h3 className="font-display text-xl text-ink-light dark:text-ink-dark">
                Active Processing
              </h3>
            </div>
            <div className="glass p-21 text-center border-gold/15 rounded-card">
              <span className="text-2xl">⚡</span>
              <h4 className="mt-8 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
                No active pipeline jobs
              </h4>
              <p className="mt-4 text-xs text-ink-dim max-w-md mx-auto">
                Upload an audio or video recording above to trigger automated transcription and multi-channel AI content generation.
              </p>
            </div>
          </section>
        )}

        {/* Section 6: Recent Recording Sessions Archive */}
        <section>
          <div className="mb-13">
            <span className="text-xs font-semibold uppercase tracking-wider text-gold">
              Archive
            </span>
            <h3 className="font-display text-xl text-ink-light dark:text-ink-dark">
              Past Recording Sessions
            </h3>
            <p className="text-xs text-ink-dim">
              Click any previous session to review generated copy, edit drafts, or mark ready to publish.
            </p>
          </div>

          <div className="flex flex-col gap-13">
            {jobsList.map((job) => {
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
                        disabled={deleteJobMutation.isPending}
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

            {jobsList.length === 0 && (
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

      {/* Create Event Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md overflow-y-auto">
          <div className="w-full max-w-xl my-8 rounded-card border border-gold/40 bg-surface-light dark:bg-surface-dark p-21 sm:p-28 shadow-2xl backdrop-blur-2xl transition-all">
            <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-13">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-gold dark:text-gold-soft">
                  Organizer Administration
                </span>
                <h3 className="font-display text-xl font-semibold text-ink-light dark:text-ink-dark">
                  Create New Event
                </h3>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowCreateModal(false);
                  setFormErrors({});
                }}
                className="rounded-full p-2 text-ink-light/50 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                title="Close modal"
              >
                ✕
              </button>
            </div>

            {createEventMutation.error && (
              <div className="mt-13 rounded-card border border-danger/30 bg-danger/15 p-13 text-xs font-medium text-danger flex items-center gap-2">
                <span>⚠️</span>
                <span>{(createEventMutation.error as Error).message}</span>
              </div>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                setFormErrors({});
                createEventMutation.mutate();
              }}
              className="mt-21 space-y-16"
            >
              {/* Event Name */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <label className="text-xs font-semibold uppercase tracking-wider text-ink-light/80 dark:text-ink-dim">
                    Event Name <span className="text-danger">*</span>
                  </label>
                  <span className="text-[10px] text-ink-light/40 dark:text-ink-dim">
                    {name.length}/255
                  </span>
                </div>
                <input
                  type="text"
                  value={name}
                  maxLength={255}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (formErrors.name) setFormErrors((prev) => ({ ...prev, name: undefined }));
                  }}
                  placeholder="e.g., Pune AI Developer Summit 2026"
                  required
                  className={`w-full rounded-card border bg-canvas-light dark:bg-white/[0.04] px-13 py-10 text-xs text-ink-light dark:text-ink-dark focus:outline-none transition-colors ${
                    formErrors.name
                      ? "border-danger focus:border-danger ring-1 ring-danger/30"
                      : "border-black/10 dark:border-white/10 focus:border-gold"
                  }`}
                />
                {formErrors.name && (
                  <p className="mt-1 text-[11px] text-danger font-medium">{formErrors.name}</p>
                )}
              </div>

              {/* Date & Category Grid */}
              <div className="grid grid-cols-1 gap-13 sm:grid-cols-2">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <label className="text-xs font-semibold uppercase tracking-wider text-ink-light/80 dark:text-ink-dim">
                      Event Date <span className="text-danger">*</span>
                    </label>
                    <span className="text-[10px] text-gold dark:text-gold-soft font-medium">
                      Date only (YYYY-MM-DD)
                    </span>
                  </div>
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => {
                      setDate(e.target.value);
                      if (formErrors.date) setFormErrors((prev) => ({ ...prev, date: undefined }));
                    }}
                    required
                    className={`w-full rounded-card border bg-canvas-light dark:bg-white/[0.04] px-13 py-10 text-xs text-ink-light dark:text-ink-dark focus:outline-none transition-colors ${
                      formErrors.date
                        ? "border-danger focus:border-danger ring-1 ring-danger/30"
                        : "border-black/10 dark:border-white/10 focus:border-gold"
                    }`}
                  />
                  {formErrors.date && (
                    <p className="mt-1 text-[11px] text-danger font-medium">{formErrors.date}</p>
                  )}
                </div>

                <div>
                  <div className="flex items-center justify-between mb-4">
                    <label className="text-xs font-semibold uppercase tracking-wider text-ink-light/80 dark:text-ink-dim">
                      Category
                    </label>
                    <span className="text-[10px] text-ink-light/40 dark:text-ink-dim">
                      EventType
                    </span>
                  </div>
                  <select
                    value={selectedType}
                    onChange={(e) => setSelectedType(e.target.value as EventType)}
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-surface-dark px-13 py-10 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  >
                    <option value="meetup">👥 Meetup</option>
                    <option value="speech">🎤 Speech / Keynote</option>
                    <option value="event">🎪 Event / Conference</option>
                    <option value="other">📌 Workshop / Session</option>
                  </select>
                </div>
              </div>

              {/* Organizer Name & Topic */}
              <div className="grid grid-cols-1 gap-13 sm:grid-cols-2">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <label className="text-xs font-semibold uppercase tracking-wider text-ink-light/80 dark:text-ink-dim">
                      Organizer / Host Name
                    </label>
                    <span className="text-[10px] text-ink-light/40 dark:text-ink-dim">
                      Optional
                    </span>
                  </div>
                  <input
                    type="text"
                    value={organizerName}
                    maxLength={255}
                    onChange={(e) => {
                      setOrganizerName(e.target.value);
                      if (formErrors.organizerName) setFormErrors((prev) => ({ ...prev, organizerName: undefined }));
                    }}
                    placeholder={user?.email ? `${user.email.split("@")[0]} (default)` : "Organizer display name"}
                    className={`w-full rounded-card border bg-canvas-light dark:bg-white/[0.04] px-13 py-10 text-xs text-ink-light dark:text-ink-dark focus:outline-none transition-colors ${
                      formErrors.organizerName
                        ? "border-danger focus:border-danger ring-1 ring-danger/30"
                        : "border-black/10 dark:border-white/10 focus:border-gold"
                    }`}
                  />
                  {formErrors.organizerName && (
                    <p className="mt-1 text-[11px] text-danger font-medium">{formErrors.organizerName}</p>
                  )}
                  <p className="mt-1 text-[10px] text-ink-light/50 dark:text-ink-dim">
                    Persisted to event record; defaults to account handle if blank.
                  </p>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-4">
                    <label className="text-xs font-semibold uppercase tracking-wider text-ink-light/80 dark:text-ink-dim">
                      Topic / Theme
                    </label>
                    <span className="text-[10px] text-ink-light/40 dark:text-ink-dim">
                      {topic.length}/255
                    </span>
                  </div>
                  <input
                    type="text"
                    value={topic}
                    maxLength={255}
                    onChange={(e) => {
                      setTopic(e.target.value);
                      if (formErrors.topic) setFormErrors((prev) => ({ ...prev, topic: undefined }));
                    }}
                    placeholder="e.g., Generative AI in Production & Agents"
                    className={`w-full rounded-card border bg-canvas-light dark:bg-white/[0.04] px-13 py-10 text-xs text-ink-light dark:text-ink-dark focus:outline-none transition-colors ${
                      formErrors.topic
                        ? "border-danger focus:border-danger ring-1 ring-danger/30"
                        : "border-black/10 dark:border-white/10 focus:border-gold"
                    }`}
                  />
                  {formErrors.topic && (
                    <p className="mt-1 text-[11px] text-danger font-medium">{formErrors.topic}</p>
                  )}
                  <p className="mt-1 text-[10px] text-ink-light/50 dark:text-ink-dim">
                    Brief theme or focus areas (max 255 chars).
                  </p>
                </div>
              </div>

              {/* Backend Contract & Capabilities Note */}
              <div className="rounded-card border border-gold/20 bg-gold/5 dark:bg-gold/[0.03] p-13 text-[11px] text-ink-light/70 dark:text-ink-dim space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-gold dark:text-gold-soft">
                  <span>ℹ️</span>
                  <span>Backend Schema Contract &amp; Status</span>
                </div>
                <p>
                  • <strong>Persisted fields:</strong> Event Name, Category, Date, Topic, and Organizer Name.
                </p>
                <p className="text-[10px] opacity-80">
                  • <strong>Upcoming backend features:</strong> Time-of-day scheduling, physical venue coordinates, and banner image uploads are pending backend database schema migration v2. Location badges are detected from title/topic keywords (e.g. Pune).
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-13 pt-13 border-t border-black/10 dark:border-white/10">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setFormErrors({});
                  }}
                  className="rounded-full border border-black/10 dark:border-white/10 px-21 py-8 text-xs font-medium text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createEventMutation.isPending || !name.trim() || !date}
                  className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 disabled:opacity-50 transition-all shadow-sm"
                >
                  {createEventMutation.isPending ? (
                    <>
                      <div className="h-3 w-3 animate-spin rounded-full border border-gold border-t-transparent" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Create Event</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </GoldenShell>
  );
}
