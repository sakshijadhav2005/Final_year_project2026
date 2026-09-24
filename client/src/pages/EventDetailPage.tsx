import { useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { GoldenShell } from "@/layouts/GoldenShell";
import { getEvent, listCommunityContent, getTranscript, type ContentPublic } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { EventChatWidget } from "@/components/chat/EventChatWidget";
import { getEventCity, getCityBadge } from "@/lib/eventLocation";

function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function EventDetailPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);

  const [activeTab, setActiveTab] = useState<"content" | "transcript">("content");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [transcriptSearch, setTranscriptSearch] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isCopiedTranscript, setIsCopiedTranscript] = useState(false);

  // Fetch Event Details
  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => (token && eventId ? getEvent(token, eventId) : null),
    enabled: !!token && !!eventId,
  });

  // Fetch all community posts & generated posts for this event
  const contentQuery = useQuery({
    queryKey: ["event-content", eventId],
    queryFn: () => (token && eventId ? listCommunityContent(token, { event_id: eventId }) : []),
    enabled: !!token && !!eventId,
  });

  const event = eventQuery.data;
  const posts: ContentPublic[] = contentQuery.data || [];

  // Derive the exact job associated with this event from its generated content pieces
  const eventJobId = posts.find((post) => Boolean(post.job_id))?.job_id ?? undefined;

  // Fetch transcript ONLY if a valid job ID is linked to this event
  const transcriptQuery = useQuery({
    queryKey: ["transcript", eventJobId],
    queryFn: () => (token && eventJobId ? getTranscript(token, eventJobId) : null),
    enabled: !!token && !!eventJobId,
  });

  const detectedCity = event ? getEventCity(event) : null;
  const cityBadge = detectedCity ? getCityBadge(detectedCity) : null;

  const filteredPosts = selectedType === "all" ? posts : posts.filter((p) => p.type === selectedType);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const fullTranscriptText = transcriptQuery.data?.full_text || "";
  const hasTranscript = Boolean(transcriptQuery.data && fullTranscriptText.trim());

  const handleCopyTranscript = async () => {
    if (!fullTranscriptText) return;
    try {
      await navigator.clipboard.writeText(fullTranscriptText);
      setIsCopiedTranscript(true);
      setTimeout(() => setIsCopiedTranscript(false), 2000);
    } catch {
      // Do not crash page if clipboard access fails
    }
  };

  // Transcript statistics
  const wordCount = useMemo(() => {
    if (!fullTranscriptText.trim()) return 0;
    return fullTranscriptText.trim().split(/\s+/).length;
  }, [fullTranscriptText]);

  const avgConfidence = transcriptQuery.data?.avg_confidence;
  const confidencePercentage =
    avgConfidence !== null && avgConfidence !== undefined
      ? Math.round(avgConfidence * 100)
      : null;

  const confidenceLevel = transcriptQuery.data?.badge
    ? transcriptQuery.data.badge.charAt(0).toUpperCase() + transcriptQuery.data.badge.slice(1)
    : avgConfidence !== null && avgConfidence !== undefined
    ? avgConfidence >= 0.85
      ? "High"
      : avgConfidence >= 0.7
      ? "Medium"
      : "Low"
    : null;

  // Search highlighting & match count with regex escaping
  const { highlightedTranscript, matchCount } = useMemo(() => {
    const trimmedSearch = transcriptSearch.trim();
    if (!trimmedSearch || !fullTranscriptText) {
      return { highlightedTranscript: fullTranscriptText, matchCount: 0 };
    }

    const escaped = escapeRegExp(trimmedSearch);
    const regex = new RegExp(`(${escaped})`, "gi");
    const matches = fullTranscriptText.match(regex);
    const count = matches ? matches.length : 0;

    const parts = fullTranscriptText.split(regex);
    const highlighted = parts.map((part, i) =>
      part.toLowerCase() === trimmedSearch.toLowerCase() ? (
        <mark key={i} className="rounded bg-accent/40 text-inherit font-semibold px-1 py-0.5">
          {part}
        </mark>
      ) : (
        part
      ),
    );

    return { highlightedTranscript: highlighted, matchCount: count };
  }, [fullTranscriptText, transcriptSearch]);

  const TYPE_BADGES: Record<string, { label: string; icon: string; color: string }> = {
    linkedin: { label: "LinkedIn Post", icon: "💼", color: "border-blue-500/30 bg-blue-500/10 text-blue-400" },
    instagram: { label: "Instagram Carousel", icon: "📸", color: "border-pink-500/30 bg-pink-500/10 text-pink-400" },
    newsletter: { label: "Email Newsletter", icon: "📧", color: "border-purple-500/30 bg-purple-500/10 text-purple-400" },
    blog: { label: "Blog Article", icon: "📝", color: "border-teal/30 bg-teal/10 text-teal" },
    summary: { label: "Executive Summary", icon: "📊", color: "border-gold/30 bg-gold/10 text-gold dark:text-gold-soft" },
    flyer: { label: "Event Flyer", icon: "🎨", color: "border-orange-500/30 bg-orange-500/10 text-orange-400" },
  };

  return (
    <GoldenShell>
      <div className="space-y-34">
        {/* Navigation Breadcrumb */}
        <div className="flex flex-wrap items-center justify-between gap-13">
          <div className="flex items-center gap-13">
            <Link
              to="/catalog/all"
              className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-surface-light/80 dark:bg-white/[0.03] px-13 py-4 text-xs font-medium text-gold hover:border-gold transition-all dark:text-gold-soft"
            >
              ← All Catalogs
            </Link>
            <span className="text-ink-light/30 dark:text-white/20">/</span>
            <span className="text-xs text-gold dark:text-gold-soft font-semibold uppercase tracking-wider">
              {event?.type || "Event"} Hub
            </span>
          </div>

          <div className="flex items-center gap-13">
            <Link
              to="/community"
              className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-surface-light/80 dark:bg-white/[0.03] px-21 py-8 text-xs font-medium text-gold hover:border-gold transition-all dark:text-gold-soft"
            >
              <span>💬 Community Feed</span>
            </Link>
            <Link
              to={user?.role === "regular_user" ? "/user/dashboard" : "/organizer/dashboard"}
              className="rounded-full border border-black/10 dark:border-white/10 px-13 py-8 text-xs font-medium text-ink-light/70 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark transition-colors"
            >
              Dashboard
            </Link>
          </div>
        </div>

        {/* Hero Event Banner */}
        <div className="relative overflow-hidden rounded-card border border-gold/20 bg-surface-light p-21 sm:p-34 shadow-xl backdrop-blur-xl dark:border-gold/20 dark:bg-surface-dark">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-21">
            <div>
              <div className="flex flex-wrap items-center gap-8 mb-8">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-medium text-gold dark:text-gold-soft">
                  <span>{event?.type === "meetup" ? "👥" : event?.type === "speech" ? "🎤" : event?.type === "event" ? "🎪" : "📌"}</span>
                  <span className="capitalize">{event?.type === "other" ? "Session" : event?.type || "Event"}</span>
                </span>
                {cityBadge && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-medium text-gold dark:text-gold-soft">
                    <span>{cityBadge.icon}</span>
                    <span>{cityBadge.label}</span>
                  </span>
                )}
                <span className="text-xs text-ink-light/60 dark:text-ink-dim">
                  📅 {event?.date ? new Date(event.date).toLocaleDateString(undefined, { dateStyle: "full" }) : "Scheduled Date"}
                </span>
              </div>

              <h1 className="font-display text-2xl sm:text-4xl font-semibold text-ink-light dark:text-ink-dark tracking-tight">
                {event?.name || "Event Overview"}
              </h1>

              {event?.topic && (
                <p className="mt-8 text-xs sm:text-sm text-ink-light/80 dark:text-ink-dim flex items-center gap-2">
                  <span className="text-gold dark:text-gold-soft font-medium">💡 Theme:</span> {event.topic}
                </p>
              )}

              <div className="mt-13 flex items-center gap-8 text-xs text-ink-light/60 dark:text-ink-dim">
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-gold/30 bg-gold/10 font-bold text-gold dark:text-gold-soft text-xs">
                  {event?.organizer_name ? event.organizer_name[0].toUpperCase() : "O"}
                </span>
                <span>Organized by <strong className="text-ink-light dark:text-ink-dark font-semibold">{event?.organizer_name || "Community Organizer"}</strong></span>
              </div>
            </div>

            {/* Quick Stats */}
            <div className="flex flex-wrap md:flex-col gap-13">
              <div className="rounded-card border border-black/10 dark:border-white/10 bg-canvas-light/60 dark:bg-white/[0.02] p-13 text-center min-w-[120px]">
                <span className="block font-display text-2xl font-bold text-gold dark:text-gold-soft">{posts.length}</span>
                <span className="text-[10px] text-ink-light/60 dark:text-ink-dim uppercase tracking-wider font-semibold">AI Posts</span>
              </div>
              <div className="rounded-card border border-black/10 dark:border-white/10 bg-canvas-light/60 dark:bg-white/[0.02] p-13 text-center min-w-[120px]">
                <span className="block font-display text-2xl font-bold text-teal">
                  {confidencePercentage !== null ? `${confidencePercentage}%` : "—"}
                </span>
                <span className="text-[10px] text-ink-light/60 dark:text-ink-dim uppercase tracking-wider font-semibold">
                  {confidenceLevel ? `${confidenceLevel} Grounding` : "Transcript Grounding"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Switching: Generated Content vs Full Transcript */}
        <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between border-b border-black/10 dark:border-white/10 pb-13">
          <div className="flex flex-wrap items-center gap-8">
            <button
              type="button"
              onClick={() => setActiveTab("content")}
              className={`rounded-full px-21 py-8 text-xs font-semibold transition-all ${
                activeTab === "content"
                  ? "border border-gold/40 bg-gold/20 text-gold dark:text-gold-soft shadow-sm"
                  : "border border-black/10 dark:border-white/10 bg-surface-light/50 dark:bg-white/[0.02] text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
              }`}
            >
              📄 Generated Content Pieces ({posts.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("transcript")}
              className={`rounded-full px-21 py-8 text-xs font-semibold transition-all ${
                activeTab === "transcript"
                  ? "border border-gold/40 bg-gold/20 text-gold dark:text-gold-soft shadow-sm"
                  : "border border-black/10 dark:border-white/10 bg-surface-light/50 dark:bg-white/[0.02] text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
              }`}
            >
              🎙️ Full Searchable Transcript
            </button>
          </div>

          {activeTab === "content" && (
            <div className="flex items-center gap-8">
              <span className="text-xs text-ink-light/60 dark:text-ink-dim hidden sm:inline">Filter format:</span>
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-surface-dark px-13 py-4 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
              >
                <option value="all">All Formats</option>
                <option value="linkedin">💼 LinkedIn</option>
                <option value="instagram">📸 Instagram</option>
                <option value="newsletter">📧 Newsletter</option>
                <option value="blog">📝 Blog</option>
                <option value="summary">📊 Summary</option>
                <option value="flyer">🎨 Flyer</option>
              </select>
            </div>
          )}
        </div>

        {/* Tab 1: Generated Content Feed */}
        {activeTab === "content" && (
          <div className="space-y-21">
            {filteredPosts.length === 0 ? (
              <div className="rounded-card border border-dashed border-black/15 dark:border-white/15 bg-surface-light/40 dark:bg-surface-dark/40 p-34 text-center">
                <span className="text-4xl">📝</span>
                <h3 className="mt-13 font-display text-lg font-semibold text-ink-light dark:text-ink-dark">
                  No posts generated for this filter
                </h3>
                <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-sm mx-auto">
                  When the organizer processes an audio or video session, all 6 specialized creator agents generate publish-ready drafts automatically.
                </p>
                <Link
                  to="/community"
                  className="mt-21 inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-21 py-8 text-xs font-semibold text-gold hover:bg-gold/20 dark:text-gold-soft transition-all"
                >
                  Write Community Reflection
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-21">
                {filteredPosts.map((post) => {
                  const badge = TYPE_BADGES[post.type] || { label: post.type, icon: "📌", color: "border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.03] text-ink-light dark:text-ink-dark" };
                  const isCopied = copiedId === post.id;

                  return (
                    <div
                      key={post.id}
                      className="group flex flex-col justify-between rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none hover:border-gold/30 transition-all"
                    >
                      <div>
                        <div className="flex items-center justify-between border-b border-black/5 dark:border-white/5 pb-13 mb-13">
                          <span className={`inline-flex items-center gap-1.5 rounded-full border px-13 py-2 text-xs font-semibold ${badge.color}`}>
                            <span>{badge.icon}</span>
                            <span>{badge.label}</span>
                          </span>

                          <div className="flex items-center gap-8 text-xs text-ink-light/60 dark:text-ink-dim">
                            <span>Author: <strong className="text-ink-light dark:text-ink-dark font-medium">{post.author_name || "Speaker"}</strong></span>
                          </div>
                        </div>

                        {post.title && (
                          <h3 className="font-display text-base font-semibold text-ink-light dark:text-ink-dark group-hover:text-gold transition-colors">
                            {post.title}
                          </h3>
                        )}

                        <div className="mt-13 text-xs text-ink-light/80 dark:text-ink-dim whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto rounded-card bg-canvas-light dark:bg-canvas-dark/60 p-13 border border-black/5 dark:border-white/5 font-sans">
                          {post.body}
                        </div>
                      </div>

                      {/* Post Actions */}
                      <div className="mt-21 flex items-center justify-between pt-13 border-t border-black/5 dark:border-white/5">
                        <button
                          type="button"
                          onClick={() => handleCopy(`${post.title ? post.title + '\n\n' : ''}${post.body}`, post.id)}
                          className="inline-flex items-center gap-1.5 rounded-full border border-black/10 dark:border-white/10 bg-canvas-light/80 dark:bg-white/[0.03] px-13 py-4 text-xs font-medium text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark transition-colors"
                        >
                          {isCopied ? "✓ Copied!" : "📋 Copy Post"}
                        </button>

                        <Link
                          to={`/community?repurpose=${post.id}&event_id=${eventId}`}
                          className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                        >
                          <span>✍️ Repurpose Post</span>
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Searchable Full Audio Transcript */}
        {activeTab === "transcript" && (
          <div className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none space-y-13">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-13">
              <div>
                <h3 className="font-display text-base font-semibold text-ink-light dark:text-ink-dark flex items-center gap-2">
                  <span>🎙️</span> Grounded Speech-to-Text Transcription
                </h3>
                <p className="text-xs text-ink-light/60 dark:text-ink-dim mt-1">
                  Full text indexed by VideoDB and verified with confidence scoring.
                </p>
              </div>

              {hasTranscript && (
                <div className="flex flex-wrap items-center gap-8">
                  {/* Copy Full Transcript */}
                  <button
                    type="button"
                    onClick={handleCopyTranscript}
                    className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                    title="Copy full transcript to clipboard"
                  >
                    <span>{isCopiedTranscript ? "✓ Copied!" : "📋 Copy Full Transcript"}</span>
                  </button>

                  {/* Search Bar */}
                  <div className="relative max-w-xs w-full">
                    <span className="absolute inset-y-0 left-3 flex items-center text-xs text-ink-light/40 dark:text-ink-dim">
                      🔍
                    </span>
                    <input
                      type="text"
                      value={transcriptSearch}
                      onChange={(e) => setTranscriptSearch(e.target.value)}
                      placeholder="Search transcript text..."
                      className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] pl-34 pr-21 py-4 text-xs text-ink-light dark:text-ink-dark placeholder-ink-light/40 dark:placeholder-ink-dim/50 focus:border-gold focus:outline-none"
                    />
                    {transcriptSearch && (
                      <button
                        type="button"
                        onClick={() => setTranscriptSearch("")}
                        className="absolute inset-y-0 right-2 flex items-center text-xs text-ink-light/40 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark"
                        title="Clear search"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Transcript Statistics & Match Count */}
            {hasTranscript && (
              <div className="flex flex-wrap items-center justify-between gap-8 pt-8 border-t border-black/5 dark:border-white/5 text-xs text-ink-light/60 dark:text-ink-dim">
                <div className="flex items-center gap-13">
                  <span>
                    Words: <strong className="text-ink-light dark:text-ink-dark font-medium">{wordCount.toLocaleString()}</strong>
                  </span>
                  {confidencePercentage !== null && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-teal/30 bg-teal/10 px-8 py-2 text-[10px] font-semibold text-teal">
                      <span>🎯</span>
                      <span>{confidencePercentage}% Grounding ({confidenceLevel})</span>
                    </span>
                  )}
                </div>

                {transcriptSearch.trim() && (
                  <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-2 text-[11px] font-medium text-gold dark:text-gold-soft">
                    {matchCount} {matchCount === 1 ? "match found" : "matches found"}
                  </span>
                )}
              </div>
            )}

            {/* Content states */}
            {!eventJobId ? (
              <div className="rounded-card border border-dashed border-gold/20 bg-surface-light/40 dark:bg-surface-dark/40 p-34 text-center">
                <span className="text-3xl">🎙️</span>
                <h4 className="mt-8 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
                  No media recording or transcript has been linked to this event yet.
                </h4>
                <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-md mx-auto">
                  Once an organizer uploads and processes an audio or video session for this event, the grounded speech-to-text transcript and verified speaker takeaways will appear here.
                </p>
                <div className="mt-13">
                  <Link
                    to="/community"
                    className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                  >
                    <span>💬</span>
                    <span>Browse Community Discussion</span>
                  </Link>
                </div>
              </div>
            ) : transcriptQuery.isLoading ? (
              <div className="py-34 text-center">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gold border-t-transparent" />
                <p className="mt-8 text-xs text-ink-light/60 dark:text-ink-dim">
                  Fetching grounded transcript from speech-to-text engine...
                </p>
              </div>
            ) : transcriptQuery.error ? (
              <div className="rounded-card border border-danger/30 bg-danger/10 p-21 text-center">
                <p className="text-xs text-danger">
                  ⚠️ Unable to retrieve transcript for session {eventJobId.slice(0, 8)}: {(transcriptQuery.error as Error).message}
                </p>
              </div>
            ) : (
              <div className="max-h-[500px] overflow-y-auto rounded-card bg-canvas-light dark:bg-canvas-dark/70 p-21 font-mono text-xs text-ink-light dark:text-ink-dark leading-relaxed whitespace-pre-wrap border border-black/5 dark:border-white/5">
                {highlightedTranscript}
              </div>
            )}
          </div>
        )}

        {/* Member 4 Attendee Q&A Assistant */}
        <EventChatWidget eventId={eventId} jobId={eventJobId} eventName={event?.name} />
      </div>
    </GoldenShell>
  );
}
