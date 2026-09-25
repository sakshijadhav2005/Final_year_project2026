import { useState, useMemo, useRef, type ChangeEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { GoldenShell } from "@/layouts/GoldenShell";
import { EventCard } from "@/components/dashboard/EventCard";
import { CreatePostForm } from "@/components/dashboard/CreatePostForm";
import {
  listEvents,
  listCommunityContent,
  getEventTranscript,
  getSavedContent,
  saveContent,
  unsaveContent,
  uploadRecording,
  listJobs,
  type ContentPublic,
  type TranscriptPublic,
} from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { getEventCity } from "@/lib/eventLocation";

const ORGANIZER_CONTENT_TYPES = [
  { id: "all", label: "All Formats", icon: "🌐" },
  { id: "linkedin", label: "LinkedIn", icon: "💼" },
  { id: "instagram", label: "Instagram", icon: "📸" },
  { id: "blog", label: "Blog", icon: "📄" },
  { id: "newsletter", label: "Newsletter", icon: "✉️" },
  { id: "summary", label: "Executive Summary", icon: "📅" },
  { id: "flyer", label: "Flyer", icon: "📢" },
];

export function UserDashboard() {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [locationFilter, setLocationFilter] = useState<string>("all");
  const [timelineFilter, setTimelineFilter] = useState<"all" | "upcoming" | "past">("all");

  // Selected Event State
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [activeEventTab, setActiveEventTab] = useState<"content" | "transcript" | "community">("content");
  const [selectedContentType, setSelectedContentType] = useState<string>("all");

  // Personal Workspace State
  const [personalTab, setPersonalTab] = useState<"my_posts" | "saved_posts" | "jobs">("my_posts");

  // Modals & UI Helpers
  const [showCreatePost, setShowCreatePost] = useState(false);
  const [showPersonalUploadModal, setShowPersonalUploadModal] = useState(false);
  const [viewingPiece, setViewingPiece] = useState<ContentPublic | null>(null);
  const [customizingPiece, setCustomizingPiece] = useState<ContentPublic | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Personal Upload State
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Queries
  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ["events"],
    queryFn: () => (token ? listEvents(token) : Promise.resolve([])),
    enabled: !!token,
  });

  const { data: communityPosts = [], isLoading: postsLoading } = useQuery({
    queryKey: ["community-content"],
    queryFn: () => (token ? listCommunityContent(token) : Promise.resolve([])),
    enabled: !!token,
  });

  const { data: savedContent = [], isLoading: savedLoading } = useQuery({
    queryKey: ["saved-content"],
    queryFn: () => (token ? getSavedContent(token) : Promise.resolve([])),
    enabled: !!token,
  });

  const { data: personalJobs = [] } = useQuery({
    queryKey: ["personal-jobs"],
    queryFn: () => (token ? listJobs(token) : Promise.resolve([])),
    enabled: !!token,
  });

  // Selected Event Queries
  const selectedEvent = useMemo(() => {
    if (!selectedEventId) return events[0] || null;
    return events.find((e) => e.id === selectedEventId) || events[0] || null;
  }, [events, selectedEventId]);

  const activeEventId = selectedEvent?.id;

  const { data: selectedEventContent = [], isLoading: eventContentLoading } = useQuery({
    queryKey: ["event-content", activeEventId],
    queryFn: () => (token && activeEventId ? listCommunityContent(token, { event_id: activeEventId }) : Promise.resolve([])),
    enabled: !!token && !!activeEventId,
  });

  const { data: eventTranscript, isLoading: transcriptLoading } = useQuery<TranscriptPublic | null>({
    queryKey: ["event-transcript", activeEventId],
    queryFn: () => (token && activeEventId ? getEventTranscript(token, activeEventId) : Promise.resolve(null)),
    enabled: !!token && !!activeEventId,
    retry: false,
  });

  // Save / Unsave Mutation
  const saveMutation = useMutation({
    mutationFn: async ({ contentId, isSaved }: { contentId: string; isSaved: boolean }) => {
      if (!token) throw new Error("Not authenticated");
      if (isSaved) {
        return unsaveContent(token, contentId);
      }
      return saveContent(token, contentId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-content"] });
    },
  });

  // Personal Upload Mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!token) throw new Error("Not authenticated");
      return uploadRecording(token, file, {
        consent: true,
        languages: "en",
        types: "summary,linkedin,blog",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["personal-jobs"] });
      setUploadFile(null);
      setShowPersonalUploadModal(false);
      setUploadError(null);
    },
    onError: (err: Error) => {
      setUploadError(err.message || "Failed to upload recording.");
    },
  });

  // Timeline Filtering
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      // Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = event.name.toLowerCase().includes(q);
        const matchTopic = event.topic?.toLowerCase().includes(q);
        const matchOrg = event.organizer_name?.toLowerCase().includes(q);
        if (!matchName && !matchTopic && !matchOrg) return false;
      }

      // Category / Type
      if (categoryFilter !== "all" && event.type !== categoryFilter) {
        return false;
      }

      // Location
      if (locationFilter === "pune" && getEventCity(event) !== "Pune") {
        return false;
      }
      if (locationFilter === "virtual" && getEventCity(event) !== "Virtual") {
        return false;
      }
      if (locationFilter === "in_person" && getEventCity(event) === "Virtual") {
        return false;
      }

      // Timeline
      const eventDate = new Date(event.date);
      if (timelineFilter === "upcoming" && eventDate < today) {
        return false;
      }
      if (timelineFilter === "past" && eventDate >= today) {
        return false;
      }

      return true;
    });
  }, [events, searchQuery, categoryFilter, locationFilter, timelineFilter, today]);

  // Separate Organizer Content from Attendee Content
  const { organizerPieces, attendeePieces } = useMemo(() => {
    const orgTypes = new Set(["linkedin", "instagram", "ig_caption", "blog", "newsletter", "summary", "flyer"]);
    const org: ContentPublic[] = [];
    const att: ContentPublic[] = [];

    selectedEventContent.forEach((piece) => {
      const isOfficialType = orgTypes.has(piece.type);
      const isCustomized = Boolean(piece.parent_id);
      const isAuthoredByCurrentUser = piece.user_id === user?.id;

      if (isCustomized || !isOfficialType || isAuthoredByCurrentUser) {
        att.push(piece);
      } else {
        org.push(piece);
      }
    });

    return { organizerPieces: org, attendeePieces: att };
  }, [selectedEventContent, user?.id]);

  // Filtered Organizer Pieces by Content Type
  const displayedOrganizerPieces = useMemo(() => {
    if (selectedContentType === "all") return organizerPieces;
    if (selectedContentType === "instagram") {
      return organizerPieces.filter((p) => p.type === "instagram" || p.type === "ig_caption");
    }
    return organizerPieces.filter((p) => p.type === selectedContentType);
  }, [organizerPieces, selectedContentType]);

  // Saved Content Set for Instant Lookup
  const savedContentIds = useMemo(() => {
    return new Set(savedContent.map((s) => s.id));
  }, [savedContent]);

  // User's Own Posts
  const myPosts = useMemo(() => {
    return communityPosts.filter((p) => p.user_id === user?.id);
  }, [communityPosts, user?.id]);

  const upcomingCount = useMemo(() => {
    return events.filter((e) => new Date(e.date) >= today).length;
  }, [events, today]);

  const handleCopy = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Ignore clipboard fallback
    }
  };

  const handleLogout = () => {
    clearAuth();
    navigate("/login");
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setUploadFile(e.target.files[0]);
      setUploadError(null);
    }
  };

  return (
    <GoldenShell>
      <div className="space-y-34">
        {/* Top Header Banner */}
        <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between border-b border-black/10 dark:border-white/10 pb-21">
          <div className="flex items-center gap-13">
            <div className="flex h-11 w-11 items-center justify-center rounded-card border border-gold/30 bg-gold/10 font-display text-lg font-bold text-gold dark:text-gold-soft shadow-inner">
              A
            </div>
            <div>
              <div className="flex items-center gap-8">
                <h1 className="font-display text-2xl font-semibold text-ink-light dark:text-ink-dark">
                  Attendee <em className="not-italic text-gold dark:text-gold-soft">Workspace</em>
                </h1>
                <span className="rounded-full border border-teal/30 bg-teal/10 px-8 py-2 text-[10px] font-semibold text-teal">
                  Session Intelligence
                </span>
              </div>
              <p className="text-xs text-ink-light/60 dark:text-ink-dim">
                Explore sessions, read transcripts, customize organizer content, and share your takeaways.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-13">
            <button
              type="button"
              onClick={() => setShowCreatePost(true)}
              className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 transition-all shadow-sm"
            >
              <span>✍️ Write Takeaway</span>
            </button>

            <button
              type="button"
              onClick={() => setShowPersonalUploadModal(true)}
              className="inline-flex items-center gap-2 rounded-full border border-teal/30 bg-teal/10 px-21 py-8 text-xs font-medium text-teal hover:bg-teal/20 transition-all"
            >
              <span>🎙️ Personal Audio Note</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setPersonalTab("saved_posts");
                const el = document.getElementById("personal-workspace");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
              className="inline-flex items-center gap-2 rounded-full border border-black/10 dark:border-white/10 bg-surface-light px-13 py-8 text-xs font-medium text-ink-light/80 dark:text-ink-dim hover:text-gold transition-colors dark:bg-white/[0.03]"
            >
              <span>🔖 Saved ({savedContent.length})</span>
            </button>

            <Link
              to="/settings"
              className="rounded-full border border-black/10 dark:border-white/10 px-13 py-8 text-xs font-medium text-ink-light/70 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark transition-colors"
            >
              ⚙️ Settings
            </Link>

            <button
              type="button"
              onClick={handleLogout}
              className="rounded-full border border-black/10 dark:border-white/10 px-13 py-8 text-xs font-medium text-ink-light/60 hover:text-danger dark:text-ink-dim dark:hover:text-danger transition-colors"
            >
              Log out
            </button>
          </div>
        </div>

        {/* Truthful Attendee Metrics Cards */}
        <section className="grid grid-cols-1 gap-13 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-card border border-gold/20 bg-surface-light p-21 shadow-sm backdrop-blur-xl dark:border-gold/20 dark:bg-surface-dark transition-all hover:border-gold/40">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                Catalog Sessions
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gold/10 border border-gold/20 text-sm">
                🎪
              </span>
            </div>
            <div className="mt-13 flex items-baseline gap-2">
              <span className="font-display text-2xl font-semibold text-ink-light dark:text-ink-dark">
                {eventsLoading ? "—" : events.length}
              </span>
            </div>
            <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim">
              Conferences, meetups &amp; tech talks
            </p>
          </div>

          <div className="rounded-card border border-gold/20 bg-surface-light p-21 shadow-sm backdrop-blur-xl dark:border-gold/20 dark:bg-surface-dark transition-all hover:border-gold/40">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                Upcoming Sessions
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gold/10 border border-gold/20 text-sm">
                📅
              </span>
            </div>
            <div className="mt-13 flex items-baseline gap-2">
              <span className="font-display text-2xl font-semibold text-ink-light dark:text-ink-dark">
                {eventsLoading ? "—" : upcomingCount}
              </span>
              {upcomingCount > 0 && (
                <span className="rounded-full border border-teal/30 bg-teal/15 px-2 py-0.5 text-[10px] font-semibold text-teal">
                  Active
                </span>
              )}
            </div>
            <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim">
              Scheduled ahead on calendar
            </p>
          </div>

          <div className="rounded-card border border-gold/20 bg-surface-light p-21 shadow-sm backdrop-blur-xl dark:border-gold/20 dark:bg-surface-dark transition-all hover:border-gold/40">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                My Takeaways &amp; Posts
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gold/10 border border-gold/20 text-sm">
                ✍️
              </span>
            </div>
            <div className="mt-13 flex items-baseline gap-2">
              <span className="font-display text-2xl font-semibold text-ink-light dark:text-ink-dark">
                {postsLoading ? "—" : myPosts.length}
              </span>
            </div>
            <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim">
              Original &amp; customized posts
            </p>
          </div>

          <div className="rounded-card border border-gold/20 bg-surface-light p-21 shadow-sm backdrop-blur-xl dark:border-gold/20 dark:bg-surface-dark transition-all hover:border-gold/40">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                Saved for Later
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal/10 border border-teal/20 text-sm">
                🔖
              </span>
            </div>
            <div className="mt-13 flex items-baseline gap-2">
              <span className="font-display text-2xl font-semibold text-teal">
                {savedLoading ? "—" : savedContent.length}
              </span>
            </div>
            <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim">
              Bookmarks stored on your account
            </p>
          </div>
        </section>

        {/* ======================================================== */}
        {/* ALL EVENTS: Search, Filter & Event Cards                 */}
        {/* ======================================================== */}
        <section className="space-y-13">
          <div className="flex flex-col gap-13 border-b border-black/10 dark:border-white/10 pb-13">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-13">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-gold">
                  Session Catalog
                </span>
                <h2 className="font-display text-xl font-semibold text-ink-light dark:text-ink-dark">
                  All Events &amp; Keynotes
                </h2>
              </div>

              {/* Search Bar */}
              <div className="relative min-w-[260px] sm:w-72">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search events, topics, speakers..."
                  className="w-full rounded-full border border-black/10 dark:border-white/10 bg-surface-light/60 dark:bg-white/[0.04] px-13 py-6 pl-9 text-xs text-ink-light dark:text-ink-dark placeholder:text-ink-light/40 dark:placeholder:text-ink-dim focus:border-gold focus:outline-none"
                />
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-ink-light/40 dark:text-ink-dim">
                  🔍
                </span>
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-ink-light/40 hover:text-ink-light dark:text-ink-dim"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* Filter Pills Row */}
            <div className="flex flex-wrap items-center justify-between gap-13 pt-4">
              {/* Timeline Filters */}
              <div className="flex flex-wrap items-center gap-8">
                {[
                  { id: "all", label: `All (${events.length})` },
                  { id: "upcoming", label: `Upcoming (${upcomingCount})` },
                  { id: "past", label: `Past Sessions` },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setTimelineFilter(tab.id as typeof timelineFilter)}
                    className={`rounded-full px-13 py-4 text-xs font-semibold transition-all ${
                      timelineFilter === tab.id
                        ? "border border-gold/40 bg-gold/20 text-gold dark:text-gold-soft shadow-sm"
                        : "border border-black/10 dark:border-white/10 bg-surface-light/50 dark:bg-white/[0.02] text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Category & Location Filters */}
              <div className="flex flex-wrap items-center gap-8">
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="rounded-full border border-black/10 dark:border-white/10 bg-surface-light px-13 py-4 text-xs font-medium text-ink-light dark:text-ink-dark dark:bg-surface-dark focus:border-gold focus:outline-none"
                >
                  <option value="all">All Categories</option>
                  <option value="event">🎪 Conferences</option>
                  <option value="meetup">👥 Meetups</option>
                  <option value="speech">🎤 Speeches</option>
                  <option value="other">📌 Sessions</option>
                </select>

                <select
                  value={locationFilter}
                  onChange={(e) => setLocationFilter(e.target.value)}
                  className="rounded-full border border-black/10 dark:border-white/10 bg-surface-light px-13 py-4 text-xs font-medium text-ink-light dark:text-ink-dark dark:bg-surface-dark focus:border-gold focus:outline-none"
                >
                  <option value="all">All Locations</option>
                  <option value="pune">📍 Pune Hub</option>
                  <option value="in_person">🏢 In-Person</option>
                  <option value="virtual">💻 Virtual / Online</option>
                </select>
              </div>
            </div>
          </div>

          {/* Events Grid */}
          {eventsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-21">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-48 rounded-card border border-black/5 dark:border-white/5 bg-black/[0.03] dark:bg-white/[0.03] animate-pulse"
                />
              ))}
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="rounded-card border border-dashed border-gold/20 bg-surface-light/40 dark:bg-surface-dark/40 p-34 text-center">
              <span className="text-3xl">🔍</span>
              <h4 className="mt-8 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
                No events matched your search or filters.
              </h4>
              <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-sm mx-auto">
                Try resetting your filters or clearing the search query to explore all sessions.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setCategoryFilter("all");
                  setLocationFilter("all");
                  setTimelineFilter("all");
                }}
                className="mt-13 inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
              >
                Reset All Filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-21">
              {filteredEvents.map((event) => (
                <EventCard
                  key={event.id}
                  event={event}
                  selected={selectedEvent?.id === event.id}
                  onSelect={(ev) => {
                    setSelectedEventId(ev.id);
                    const hub = document.getElementById("selected-event-hub");
                    hub?.scrollIntoView({ behavior: "smooth" });
                  }}
                />
              ))}
            </div>
          )}
        </section>

        {/* ======================================================== */}
        {/* SELECTED EVENT CONTENT HUB                               */}
        {/* ======================================================== */}
        {selectedEvent && (
          <section
            id="selected-event-hub"
            className="space-y-21 rounded-card border border-gold/30 bg-surface-light/90 dark:bg-surface-dark/90 p-21 shadow-lg backdrop-blur-xl"
          >
            {/* Event Header Banner */}
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-13 border-b border-black/10 dark:border-white/10 pb-13">
              <div>
                <div className="flex flex-wrap items-center gap-8 text-xs">
                  <span className="rounded-full border border-gold/40 bg-gold/15 px-8 py-2 font-bold text-gold dark:text-gold-soft">
                    SELECTED SESSION
                  </span>
                  <span className="text-ink-light/60 dark:text-ink-dim">
                    📅 {new Date(selectedEvent.date).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </span>
                  {selectedEvent.organizer_name && (
                    <span className="text-ink-light/60 dark:text-ink-dim">
                      • Host: <strong className="text-ink-light dark:text-ink-dark">{selectedEvent.organizer_name}</strong>
                    </span>
                  )}
                </div>

                <h2 className="mt-8 font-display text-2xl font-bold text-ink-light dark:text-ink-dark">
                  {selectedEvent.name}
                </h2>

                {selectedEvent.topic && (
                  <p className="mt-4 text-xs font-medium text-ink-light/70 dark:text-ink-dim">
                    💡 Topic: {selectedEvent.topic}
                  </p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-8">
                <Link
                  to={`/events/${selectedEvent.id}`}
                  className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-13 py-6 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                >
                  <span>🎙️ Open Full Event Hub →</span>
                </Link>

                <button
                  type="button"
                  onClick={() => setShowCreatePost(true)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-black/10 dark:border-white/10 bg-surface-light px-13 py-6 text-xs font-medium text-ink-light dark:text-ink-dark hover:border-gold transition-all"
                >
                  <span>✍️ Add Note</span>
                </button>
              </div>
            </div>

            {/* Hub Tabs: Organizer Content vs Transcript */}
            <div className="flex items-center gap-13 border-b border-black/10 dark:border-white/10 pb-8">
              <button
                type="button"
                onClick={() => setActiveEventTab("content")}
                className={`pb-4 text-xs font-semibold transition-all ${
                  activeEventTab === "content"
                    ? "border-b-2 border-gold text-gold dark:text-gold-soft"
                    : "text-ink-light/60 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                }`}
              >
                ✨ Organizer Content ({organizerPieces.length})
              </button>

              <button
                type="button"
                onClick={() => setActiveEventTab("transcript")}
                className={`pb-4 text-xs font-semibold transition-all ${
                  activeEventTab === "transcript"
                    ? "border-b-2 border-gold text-gold dark:text-gold-soft"
                    : "text-ink-light/60 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                }`}
              >
                🎙️ Session Transcript {eventTranscript ? "✓" : ""}
              </button>

              <button
                type="button"
                onClick={() => setActiveEventTab("community")}
                className={`pb-4 text-xs font-semibold transition-all ${
                  activeEventTab === "community"
                    ? "border-b-2 border-gold text-gold dark:text-gold-soft"
                    : "text-ink-light/60 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                }`}
              >
                👥 Community Notes ({attendeePieces.length})
              </button>
            </div>

            {/* TAB 1: ORGANIZER GENERATED CONTENT */}
            {activeEventTab === "content" && (
              <div className="space-y-13">
                {/* Content Type Filter Pills */}
                <div className="flex flex-wrap items-center gap-8">
                  {ORGANIZER_CONTENT_TYPES.map((type) => {
                    const count =
                      type.id === "all"
                        ? organizerPieces.length
                        : organizerPieces.filter((p) => p.type === type.id || (type.id === "instagram" && p.type === "ig_caption")).length;

                    return (
                      <button
                        key={type.id}
                        type="button"
                        onClick={() => setSelectedContentType(type.id)}
                        className={`inline-flex items-center gap-1.5 rounded-full px-13 py-4 text-xs font-semibold transition-all ${
                          selectedContentType === type.id
                            ? "border border-gold/40 bg-gold/20 text-gold dark:text-gold-soft shadow-sm"
                            : "border border-black/10 dark:border-white/10 bg-surface-light/40 dark:bg-white/[0.02] text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                        }`}
                      >
                        <span>{type.icon}</span>
                        <span>{type.label}</span>
                        <span className="opacity-70 text-[10px]">({count})</span>
                      </button>
                    );
                  })}
                </div>

                {/* Organizer Pieces Grid */}
                {eventContentLoading ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-13">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-40 rounded-card border border-black/5 bg-black/[0.02] dark:bg-white/[0.02] animate-pulse" />
                    ))}
                  </div>
                ) : displayedOrganizerPieces.length === 0 ? (
                  <div className="rounded-card border border-dashed border-black/10 dark:border-white/10 p-21 text-center text-xs text-ink-light/60 dark:text-ink-dim">
                    <p className="text-sm">📝 No organizer-generated {selectedContentType === "all" ? "posts" : selectedContentType} for this session yet.</p>
                    <p className="mt-2 text-[11px]">You can still write your own takeaway or check the transcript tab.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-13">
                    {displayedOrganizerPieces.map((piece) => {
                      const isSaved = savedContentIds.has(piece.id);
                      const isCopied = copiedId === piece.id;

                      return (
                        <div
                          key={piece.id}
                          className="flex flex-col justify-between rounded-card border border-black/10 dark:border-white/10 bg-surface-light p-13 shadow-sm dark:bg-surface-dark hover:border-gold/30 transition-all"
                        >
                          <div>
                            <div className="flex items-center justify-between text-[11px] text-ink-light/60 dark:text-ink-dim mb-8">
                              <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-1 font-bold text-gold dark:text-gold-soft uppercase tracking-wider text-[9px]">
                                {piece.type.replace("_", " ")}
                              </span>
                              <span>Author: {piece.author_name || "Organizer"}</span>
                            </div>

                            {piece.title && (
                              <h4 className="font-display text-sm font-semibold text-ink-light dark:text-ink-dark line-clamp-1 mb-4">
                                {piece.title}
                              </h4>
                            )}

                            <p className="text-xs text-ink-light/70 dark:text-ink-dim line-clamp-3 leading-relaxed">
                              {piece.body}
                            </p>
                          </div>

                          {/* Action Buttons: View, Copy, Customize, Save */}
                          <div className="mt-13 flex items-center justify-between border-t border-black/5 dark:border-white/5 pt-8 text-xs">
                            <div className="flex items-center gap-6">
                              <button
                                type="button"
                                onClick={() => setViewingPiece(piece)}
                                className="rounded-full border border-black/10 dark:border-white/10 px-8 py-2 text-[11px] font-medium text-ink-light/70 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark transition-colors"
                              >
                                👁️ View
                              </button>

                              <button
                                type="button"
                                onClick={() => handleCopy(`${piece.title ? piece.title + "\n\n" : ""}${piece.body}`, piece.id)}
                                className="rounded-full border border-black/10 dark:border-white/10 px-8 py-2 text-[11px] font-medium text-ink-light/70 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark transition-colors"
                              >
                                {isCopied ? "✓ Copied" : "📋 Copy"}
                              </button>

                              <button
                                type="button"
                                onClick={() => setCustomizingPiece(piece)}
                                className="rounded-full border border-gold/40 bg-gold/10 px-8 py-2 text-[11px] font-semibold text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                                title="Customize into your personal posts"
                              >
                                ✨ Customize
                              </button>
                            </div>

                            <button
                              type="button"
                              onClick={() => saveMutation.mutate({ contentId: piece.id, isSaved })}
                              className={`rounded-full p-2 text-sm transition-all ${
                                isSaved
                                  ? "text-gold dark:text-gold-soft"
                                  : "text-ink-light/40 dark:text-ink-dim hover:text-gold"
                              }`}
                              title={isSaved ? "Remove from Saved" : "Save for Later"}
                            >
                              {isSaved ? "🔖" : "📑"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: SESSION TRANSCRIPT */}
            {activeEventTab === "transcript" && (
              <div className="space-y-13">
                {transcriptLoading ? (
                  <div className="h-32 rounded-card border border-black/5 bg-black/[0.02] dark:bg-white/[0.02] animate-pulse" />
                ) : !eventTranscript ? (
                  <div className="rounded-card border border-dashed border-black/10 dark:border-white/10 p-21 text-center text-xs text-ink-light/60 dark:text-ink-dim">
                    <p className="text-sm">🎙️ No transcript processed for this session yet.</p>
                    <p className="mt-2 text-[11px]">Transcripts become available once the session recording finishes processing.</p>
                  </div>
                ) : (
                  <div className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light p-21 dark:bg-surface-dark space-y-13">
                    <div className="flex flex-wrap items-center justify-between gap-13 border-b border-black/5 dark:border-white/5 pb-8 text-xs">
                      <div className="flex items-center gap-8">
                        <span className="font-semibold text-ink-light dark:text-ink-dark">
                          Language: {eventTranscript.language.toUpperCase()}
                        </span>
                        <span className="rounded-full border border-teal/30 bg-teal/10 px-8 py-1 text-[10px] font-semibold text-teal">
                          {eventTranscript.badge.toUpperCase()} QUALITY
                        </span>
                      </div>

                      <div className="flex items-center gap-8">
                        <button
                          type="button"
                          onClick={() => handleCopy(eventTranscript.full_text, "transcript-copy")}
                          className="rounded-full border border-black/10 dark:border-white/10 px-13 py-4 text-xs font-medium text-ink-light/70 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark"
                        >
                          {copiedId === "transcript-copy" ? "✓ Copied Transcript" : "📋 Copy Full Transcript"}
                        </button>

                        <Link
                          to={`/events/${selectedEvent.id}`}
                          className="text-xs font-semibold text-gold hover:underline dark:text-gold-soft"
                        >
                          Open Dialogue View →
                        </Link>
                      </div>
                    </div>

                    <p className="text-xs text-ink-light/80 dark:text-ink-dim leading-relaxed max-h-60 overflow-y-auto whitespace-pre-wrap font-mono p-13 rounded-card bg-black/[0.02] dark:bg-white/[0.02] border border-black/5 dark:border-white/5">
                      {eventTranscript.full_text}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: COMMUNITY NOTES FOR THIS EVENT */}
            {activeEventTab === "community" && (
              <div className="space-y-13">
                {attendeePieces.length === 0 ? (
                  <div className="rounded-card border border-dashed border-black/10 dark:border-white/10 p-21 text-center text-xs text-ink-light/60 dark:text-ink-dim">
                    <p className="text-sm">👥 No community notes or customized posts shared for this session yet.</p>
                    <p className="mt-2 text-[11px]">Be the first attendee to customize an organizer post or share your notes!</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-13">
                    {attendeePieces.map((piece) => (
                      <div
                        key={piece.id}
                        className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light p-13 shadow-sm dark:bg-surface-dark space-y-4"
                      >
                        <div className="flex items-center justify-between text-[11px] text-ink-light/60 dark:text-ink-dim">
                          <span className="font-semibold text-ink-light dark:text-ink-dark">
                            {piece.author_name || "Community Member"}
                          </span>
                          <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-1 text-[9px] font-bold text-gold uppercase">
                            {piece.type.replace("_", " ")}
                          </span>
                        </div>
                        {piece.title && (
                          <h4 className="font-display text-sm font-semibold text-ink-light dark:text-ink-dark">
                            {piece.title}
                          </h4>
                        )}
                        <p className="text-xs text-ink-light/70 dark:text-ink-dim line-clamp-3">
                          {piece.body}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* ======================================================== */}
        {/* PERSONAL CONTENT WORKSPACE: My Posts & Saved Posts        */}
        {/* ======================================================== */}
        <section id="personal-workspace" className="space-y-13">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-13 border-b border-black/10 dark:border-white/10 pb-8">
            <div className="flex items-center gap-13">
              <button
                type="button"
                onClick={() => setPersonalTab("my_posts")}
                className={`pb-4 font-display text-base font-semibold transition-all ${
                  personalTab === "my_posts"
                    ? "border-b-2 border-gold text-ink-light dark:text-ink-dark"
                    : "text-ink-light/50 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                }`}
              >
                ✍️ My Posts ({myPosts.length})
              </button>

              <button
                type="button"
                onClick={() => setPersonalTab("saved_posts")}
                className={`pb-4 font-display text-base font-semibold transition-all ${
                  personalTab === "saved_posts"
                    ? "border-b-2 border-gold text-ink-light dark:text-ink-dark"
                    : "text-ink-light/50 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                }`}
              >
                🔖 Saved Posts ({savedContent.length})
              </button>

              <button
                type="button"
                onClick={() => setPersonalTab("jobs")}
                className={`pb-4 font-display text-base font-semibold transition-all ${
                  personalTab === "jobs"
                    ? "border-b-2 border-gold text-ink-light dark:text-ink-dark"
                    : "text-ink-light/50 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                }`}
              >
                🎙️ Personal Jobs ({personalJobs.length})
              </button>
            </div>

            <div className="flex items-center gap-8">
              <button
                type="button"
                onClick={() => setShowCreatePost(true)}
                className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
              >
                <span>+ Write New Post</span>
              </button>
            </div>
          </div>

          {/* TAB: MY POSTS */}
          {personalTab === "my_posts" && (
            <div>
              {postsLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-13">
                  {[1, 2].map((i) => (
                    <div key={i} className="h-32 rounded-card border border-black/5 bg-black/[0.02] dark:bg-white/[0.02] animate-pulse" />
                  ))}
                </div>
              ) : myPosts.length === 0 ? (
                <div className="rounded-card border border-black/10 bg-surface-light p-34 text-center shadow-sm dark:border-white/10 dark:bg-surface-dark">
                  <span className="text-3xl">✍️</span>
                  <h4 className="mt-8 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
                    You haven't created any posts or takeaways yet.
                  </h4>
                  <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-sm mx-auto">
                    Share your reflections from a session, or customize an organizer's post to make it your own!
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowCreatePost(true)}
                    className="mt-13 inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 transition-all"
                  >
                    Write Your First Post
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-13">
                  {myPosts.map((post) => {
                    const matchedEvent = events.find((e) => e.id === post.event_id);
                    const isCustomized = Boolean(post.parent_id);

                    return (
                      <div
                        key={post.id}
                        className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light p-21 shadow-sm dark:bg-surface-dark space-y-8 hover:border-gold/30 transition-all"
                      >
                        <div className="flex items-center justify-between text-xs text-ink-light/60 dark:text-ink-dim">
                          <div className="flex items-center gap-8">
                            <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-1 text-[10px] font-semibold text-gold dark:text-gold-soft uppercase">
                              {post.type.replace("_", " ")}
                            </span>
                            {isCustomized ? (
                              <span className="rounded-full border border-lavender/30 bg-lavender/10 px-8 py-1 text-[10px] font-medium text-lavender">
                                ✨ Customized
                              </span>
                            ) : (
                              <span className="text-[10px] text-ink-light/50 dark:text-ink-dim">
                                ✍️ Original
                              </span>
                            )}
                          </div>

                          {matchedEvent && (
                            <Link
                              to={`/events/${matchedEvent.id}`}
                              className="text-xs font-medium text-gold dark:text-gold-soft hover:underline"
                            >
                              🎪 {matchedEvent.name}
                            </Link>
                          )}
                        </div>

                        {post.title && (
                          <h4 className="font-display text-sm font-semibold text-ink-light dark:text-ink-dark">
                            {post.title}
                          </h4>
                        )}

                        <p className="text-xs text-ink-light/70 dark:text-ink-dim line-clamp-3 leading-relaxed">
                          {post.body}
                        </p>

                        <div className="flex items-center justify-between border-t border-black/5 dark:border-white/5 pt-8 text-xs">
                          <button
                            type="button"
                            onClick={() => handleCopy(`${post.title ? post.title + "\n\n" : ""}${post.body}`, post.id)}
                            className="inline-flex items-center gap-1 text-ink-light/60 hover:text-gold dark:text-ink-dim dark:hover:text-gold-soft transition-colors"
                          >
                            <span>{copiedId === post.id ? "✓ Copied" : "📋 Copy"}</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => setViewingPiece(post)}
                            className="text-xs font-medium text-ink-light/70 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark"
                          >
                            Full View →
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB: SAVED POSTS */}
          {personalTab === "saved_posts" && (
            <div>
              {savedLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-13">
                  {[1, 2].map((i) => (
                    <div key={i} className="h-32 rounded-card border border-black/5 bg-black/[0.02] dark:bg-white/[0.02] animate-pulse" />
                  ))}
                </div>
              ) : savedContent.length === 0 ? (
                <div className="rounded-card border border-black/10 bg-surface-light p-34 text-center shadow-sm dark:border-white/10 dark:bg-surface-dark">
                  <span className="text-3xl">🔖</span>
                  <h4 className="mt-8 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
                    No saved posts yet.
                  </h4>
                  <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-sm mx-auto">
                    Click the 📑 bookmark icon on any organizer post or community takeaway to save it here for quick reference.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-13">
                  {savedContent.map((post) => {
                    const matchedEvent = events.find((e) => e.id === post.event_id);

                    return (
                      <div
                        key={post.id}
                        className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light p-21 shadow-sm dark:bg-surface-dark space-y-8 hover:border-gold/30 transition-all"
                      >
                        <div className="flex items-center justify-between text-xs text-ink-light/60 dark:text-ink-dim">
                          <div className="flex items-center gap-8">
                            <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-1 text-[10px] font-semibold text-gold dark:text-gold-soft uppercase">
                              {post.type.replace("_", " ")}
                            </span>
                            <span>By: {post.author_name || "Organizer"}</span>
                          </div>

                          <button
                            type="button"
                            onClick={() => saveMutation.mutate({ contentId: post.id, isSaved: true })}
                            className="text-xs text-ink-light/50 hover:text-danger dark:text-ink-dim transition-colors"
                            title="Remove from saved"
                          >
                            ✕ Remove
                          </button>
                        </div>

                        {post.title && (
                          <h4 className="font-display text-sm font-semibold text-ink-light dark:text-ink-dark">
                            {post.title}
                          </h4>
                        )}

                        <p className="text-xs text-ink-light/70 dark:text-ink-dim line-clamp-3 leading-relaxed">
                          {post.body}
                        </p>

                        <div className="flex items-center justify-between border-t border-black/5 dark:border-white/5 pt-8 text-xs">
                          <div className="flex items-center gap-8">
                            <button
                              type="button"
                              onClick={() => handleCopy(`${post.title ? post.title + "\n\n" : ""}${post.body}`, post.id)}
                              className="inline-flex items-center gap-1 text-ink-light/60 hover:text-gold dark:text-ink-dim dark:hover:text-gold-soft transition-colors"
                            >
                              <span>{copiedId === post.id ? "✓ Copied" : "📋 Copy"}</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => setCustomizingPiece(post)}
                              className="text-gold dark:text-gold-soft hover:underline font-medium"
                            >
                              ✨ Customize
                            </button>
                          </div>

                          {matchedEvent && (
                            <Link
                              to={`/events/${matchedEvent.id}`}
                              className="text-xs font-medium text-ink-light/70 hover:text-ink-light dark:text-ink-dim"
                            >
                              🎪 {matchedEvent.name}
                            </Link>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB: PERSONAL JOBS */}
          {personalTab === "jobs" && (
            <div>
              {personalJobs.length === 0 ? (
                <div className="rounded-card border border-black/10 bg-surface-light p-34 text-center shadow-sm dark:border-white/10 dark:bg-surface-dark">
                  <span className="text-3xl">🎙️</span>
                  <h4 className="mt-8 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
                    No personal audio processing jobs yet.
                  </h4>
                  <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-sm mx-auto">
                    Upload voice memos or audio recordings to run your private AI transcription and content pipeline.
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowPersonalUploadModal(true)}
                    className="mt-13 inline-flex items-center gap-2 rounded-full border border-teal/40 bg-teal/20 px-21 py-8 text-xs font-semibold text-teal hover:bg-teal/30 transition-all"
                  >
                    Upload Audio Note
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-13">
                  {personalJobs.map((job) => (
                    <div
                      key={job.id}
                      className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light p-21 shadow-sm dark:bg-surface-dark space-y-8"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono text-[10px] text-ink-light/60 dark:text-ink-dim">
                          Job #{job.id.slice(0, 8)}
                        </span>
                        <span
                          className={`rounded-full px-8 py-1 text-[10px] font-bold uppercase ${
                            job.status === "completed" || job.status === "ready_to_publish"
                              ? "border border-teal/30 bg-teal/10 text-teal"
                              : job.status === "failed"
                              ? "border border-danger/30 bg-danger/10 text-danger"
                              : "border border-gold/30 bg-gold/10 text-gold"
                          }`}
                        >
                          {job.status}
                        </span>
                      </div>
                      <p className="text-xs text-ink-light/70 dark:text-ink-dim">
                        Requested Formats: {job.requested_types?.join(", ") || "Standard Formats"}
                      </p>
                      {job.created_at && (
                        <p className="text-[10px] text-ink-light/50 dark:text-ink-dim">
                          Started: {new Date(job.created_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>

        {/* ======================================================== */}
        {/* MODAL: VIEW CONTENT                                      */}
        {/* ======================================================== */}
        {viewingPiece && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-13 backdrop-blur-sm">
            <div className="w-full max-w-2xl rounded-card border border-gold/30 bg-surface-light p-21 shadow-2xl dark:border-gold/20 dark:bg-surface-dark space-y-13 max-h-[85vh] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-8">
                <div className="flex items-center gap-8">
                  <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-1 text-[10px] font-bold text-gold dark:text-gold-soft uppercase tracking-wider">
                    {viewingPiece.type.replace("_", " ")}
                  </span>
                  <span className="text-xs text-ink-light/60 dark:text-ink-dim">
                    Author: {viewingPiece.author_name || "Organizer"}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => setViewingPiece(null)}
                  className="text-xs text-ink-light/50 hover:text-ink-light dark:text-ink-dim"
                >
                  ✕ Close
                </button>
              </div>

              {viewingPiece.title && (
                <h3 className="font-display text-lg font-bold text-ink-light dark:text-ink-dark">
                  {viewingPiece.title}
                </h3>
              )}

              <div className="rounded-card border border-black/5 dark:border-white/5 bg-canvas-light/50 dark:bg-white/[0.02] p-13 text-xs text-ink-light/90 dark:text-ink-dim whitespace-pre-wrap leading-relaxed font-sans">
                {viewingPiece.body}
              </div>

              <div className="flex items-center justify-between border-t border-black/10 dark:border-white/10 pt-8 text-xs">
                <button
                  type="button"
                  onClick={() => handleCopy(`${viewingPiece.title ? viewingPiece.title + "\n\n" : ""}${viewingPiece.body}`, viewingPiece.id)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-black/10 dark:border-white/10 px-13 py-6 text-xs font-semibold text-ink-light dark:text-ink-dark hover:border-gold"
                >
                  <span>{copiedId === viewingPiece.id ? "✓ Copied!" : "📋 Copy Content"}</span>
                </button>

                <div className="flex items-center gap-8">
                  <button
                    type="button"
                    onClick={() => {
                      const p = viewingPiece;
                      setViewingPiece(null);
                      setCustomizingPiece(p);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-full border border-gold/40 bg-gold/20 px-13 py-6 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30"
                  >
                    <span>✨ Customize into My Posts</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* MODAL: CUSTOMIZE ORGANIZER CONTENT                       */}
        {/* ======================================================== */}
        {customizingPiece && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-13 backdrop-blur-sm">
            <div className="w-full max-w-2xl">
              <CreatePostForm
                events={events}
                defaultEventId={customizingPiece.event_id || selectedEvent?.id || ""}
                defaultTitle={customizingPiece.title || `My Takeaway on ${selectedEvent?.name || "Session"}`}
                defaultBody={customizingPiece.body}
                defaultType={customizingPiece.type}
                parentId={customizingPiece.id}
                isCustomization={true}
                sourceAuthor={customizingPiece.author_name || "Organizer"}
                onSuccess={() => {
                  setCustomizingPiece(null);
                  setPersonalTab("my_posts");
                }}
                onCancel={() => setCustomizingPiece(null)}
              />
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* MODAL: WRITE NEW POST                                    */}
        {/* ======================================================== */}
        {showCreatePost && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-13 backdrop-blur-sm">
            <div className="w-full max-w-2xl">
              <CreatePostForm
                events={events}
                defaultEventId={selectedEvent?.id || ""}
                onSuccess={() => {
                  setShowCreatePost(false);
                  setPersonalTab("my_posts");
                }}
                onCancel={() => setShowCreatePost(false)}
              />
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* MODAL: PERSONAL AUDIO RECORDING UPLOAD                   */}
        {/* ======================================================== */}
        {showPersonalUploadModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-13 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-card border border-teal/30 bg-surface-light p-21 shadow-2xl dark:border-teal/30 dark:bg-surface-dark space-y-13">
              <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-8">
                <div>
                  <h3 className="font-display text-base font-semibold text-ink-light dark:text-ink-dark flex items-center gap-2">
                    <span>🎙️</span> Personal Audio Note Upload
                  </h3>
                  <p className="text-xs text-ink-light/60 dark:text-ink-dim mt-1">
                    Process private voice memos into AI-generated session takeaways
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setShowPersonalUploadModal(false)}
                  className="text-xs text-ink-light/50 hover:text-ink-light dark:text-ink-dim"
                >
                  ✕ Close
                </button>
              </div>

              {/* Informative RBAC Banner */}
              <div className="rounded-card border border-teal/30 bg-teal/10 p-13 text-xs text-teal leading-relaxed">
                ℹ️ <strong>Attendee Permission Notice:</strong> Personal recordings run through your private AI pipeline to generate personal notes.
                Official session recordings for catalog events are managed by verified event organizers.
              </div>

              {uploadError && (
                <div className="rounded-card border border-danger/30 bg-danger/15 p-13 text-xs text-danger">
                  {uploadError}
                </div>
              )}

              {/* File Drop Area */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className="cursor-pointer rounded-card border-2 border-dashed border-teal/30 bg-teal/5 p-21 text-center hover:border-teal transition-all"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="audio/*,video/*,.txt"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <span className="text-3xl">🎙️</span>
                <p className="mt-8 text-xs font-semibold text-ink-light dark:text-ink-dark">
                  {uploadFile ? uploadFile.name : "Click to select voice memo / audio note"}
                </p>
                <p className="mt-2 text-[11px] text-ink-light/50 dark:text-ink-dim">
                  Supported: MP3, WAV, M4A, MP4 (Max 500 MB)
                </p>
              </div>

              {uploadFile && (
                <div className="flex items-center justify-between text-xs text-ink-light/70 dark:text-ink-dim">
                  <span>Selected size: {(uploadFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                  <button
                    type="button"
                    onClick={() => setUploadFile(null)}
                    className="text-danger hover:underline"
                  >
                    Remove
                  </button>
                </div>
              )}

              <div className="flex items-center justify-between border-t border-black/10 dark:border-white/10 pt-8">
                <button
                  type="button"
                  onClick={() => setShowPersonalUploadModal(false)}
                  className="rounded-full border border-black/10 dark:border-white/10 px-13 py-6 text-xs font-medium text-ink-light/70 dark:text-ink-dim"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  disabled={!uploadFile || uploadMutation.isPending}
                  onClick={() => {
                    if (uploadFile) uploadMutation.mutate(uploadFile);
                  }}
                  className="inline-flex items-center gap-2 rounded-full border border-teal/40 bg-teal/20 px-21 py-6 text-xs font-semibold text-teal hover:bg-teal/30 disabled:opacity-50 transition-all"
                >
                  {uploadMutation.isPending ? "Uploading & Enqueueing..." : "Start Processing 🚀"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </GoldenShell>
  );
}
