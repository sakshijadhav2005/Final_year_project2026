import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { GoldenShell } from "@/layouts/GoldenShell";
import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { EventCard } from "@/components/dashboard/EventCard";
import { listEvents, createEvent, type EventType } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { getEventCity } from "@/lib/eventLocation";

export function CatalogPage() {
  const { type } = useParams<{ type: string }>();
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [locationFilter, setLocationFilter] = useState<"all" | "Pune">("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [topic, setTopic] = useState("");
  const [organizerName, setOrganizerName] = useState("");
  const [formErrors, setFormErrors] = useState<{
    name?: string;
    date?: string;
    topic?: string;
    organizerName?: string;
  }>({});
  const [selectedType, setSelectedType] = useState<EventType>(
    type && type !== "all" ? (type as EventType) : "event",
  );

  const filterType = type && type !== "all" ? (type as EventType) : undefined;

  const { data: events = [], isLoading, error } = useQuery({
    queryKey: ["events", filterType],
    queryFn: () => (token ? listEvents(token, filterType) : Promise.resolve([])),
    enabled: !!token,
  });

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
        throw new Error("Please correct the form errors before submitting.");
      }

      return createEvent(token, {
        name: trimmedName,
        date,
        topic: trimmedTopic || undefined,
        organizer_name: trimmedOrg || undefined,
        type: selectedType,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setShowCreateModal(false);
      setName("");
      setDate("");
      setTopic("");
      setOrganizerName("");
      setFormErrors({});
    },
  });

  const puneEventsCount = events.filter((e) => getEventCity(e) === "Pune").length;

  const filteredEvents = events.filter((e) => {
    const matchesSearch =
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      (e.topic && e.topic.toLowerCase().includes(search.toLowerCase())) ||
      (e.organizer_name && e.organizer_name.toLowerCase().includes(search.toLowerCase()));

    if (!matchesSearch) return false;

    if (locationFilter === "Pune") {
      return getEventCity(e) === "Pune";
    }

    return true;
  });

  const isOrganizer = user?.role === "event_organizer" || user?.role === "admin";

  return (
    <GoldenShell>
      <div className="space-y-34">
        {/* Header navigation bar */}
        <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between border-b border-black/10 dark:border-white/10 pb-21">
          <div>
            <div className="flex items-center gap-13">
              <Link
                to={isOrganizer ? "/organizer/dashboard" : "/user/dashboard"}
                className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-surface-light/80 dark:bg-white/[0.03] px-13 py-4 text-xs font-medium text-gold hover:border-gold transition-all dark:text-gold-soft"
              >
                ← Back to Dashboard
              </Link>
              <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-2 text-[11px] font-semibold text-gold dark:text-gold-soft">
                Catalog Mode
              </span>
            </div>
            <h1 className="mt-8 font-display text-2xl sm:text-3xl font-semibold tracking-tight text-ink-light dark:text-ink-dark">
              {type === "meetup" && "👥 Community Meetups"}
              {type === "event" && "🎪 Conferences & Keynote Events"}
              {type === "speech" && "🎤 Speeches, Panels & Tech Talks"}
              {(!type || type === "all") && "🌐 All Event Catalogs"}
            </h1>
            <p className="mt-4 text-xs sm:text-sm text-ink-light/60 dark:text-ink-dim">
              Browse organized sessions and access AI-generated blogs, newsletters, and social summaries.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-13">
            <Link
              to="/community"
              className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-surface-light/80 dark:bg-white/[0.03] px-21 py-8 text-xs font-medium text-gold hover:border-gold transition-all dark:text-gold-soft"
            >
              <span>💬 Community Feed</span>
            </Link>

            {isOrganizer && (
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 transition-all"
              >
                <span>➕ Create New Event</span>
              </button>
            )}
          </div>
        </div>

        {/* Catalog Navigation Tabs */}
        <section>
          <CatalogNav />
        </section>

        {/* Discover by Location Toolbar */}
        <div className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
          <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-8">
                <span className="text-sm">📍</span>
                <h3 className="font-display text-sm font-semibold text-ink-light dark:text-ink-dark">
                  Discover by Location
                </h3>
                <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-2 text-[10px] font-semibold text-gold dark:text-gold-soft">
                  Pune Focus
                </span>
              </div>
              <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim">
                Explore events around Pune and beyond.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-8">
              <button
                type="button"
                onClick={() => setLocationFilter("all")}
                className={`inline-flex items-center gap-1.5 rounded-full px-21 py-8 text-xs font-semibold transition-all ${
                  locationFilter === "all"
                    ? "border border-gold/40 bg-gold/20 text-gold dark:text-gold-soft shadow-sm"
                    : "border border-black/10 dark:border-white/10 bg-surface-light/50 dark:bg-white/[0.02] text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                }`}
              >
                <span>🌐 All Locations</span>
                <span className="rounded-full bg-black/5 dark:bg-white/10 px-6 py-1 text-[10px]">
                  {events.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setLocationFilter("Pune")}
                className={`inline-flex items-center gap-1.5 rounded-full px-21 py-8 text-xs font-semibold transition-all ${
                  locationFilter === "Pune"
                    ? "border border-teal/40 bg-teal/20 text-teal shadow-sm ring-1 ring-teal/30"
                    : "border border-gold/40 bg-gold/10 text-gold dark:text-gold-soft hover:bg-gold/20"
                }`}
              >
                <span>📍 Pune</span>
                <span className="rounded-full bg-black/5 dark:bg-white/10 px-6 py-1 text-[10px]">
                  {puneEventsCount}
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Search & Stats Bar */}
        <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <span className="absolute inset-y-0 left-3 flex items-center text-xs text-ink-light/40 dark:text-ink-dim">
              🔍
            </span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by event name, topic, or speaker..."
              className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] pl-34 pr-13 py-8 text-xs text-ink-light dark:text-ink-dark placeholder-ink-light/40 dark:placeholder-ink-dim/50 focus:border-gold focus:outline-none backdrop-blur-md"
            />
          </div>

          <div className="flex items-center gap-8 text-xs text-ink-light/60 dark:text-ink-dim">
            <span>Showing <strong className="text-ink-light dark:text-ink-dark">{filteredEvents.length}</strong> events</span>
            <span>•</span>
            <span className="text-teal font-medium">● Live Catalogs</span>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="grid grid-cols-1 gap-21 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div
                key={i}
                className="h-56 animate-pulse rounded-card border border-black/5 dark:border-white/5 bg-black/[0.03] dark:bg-white/[0.03] p-21"
              />
            ))}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="rounded-card border border-danger/30 bg-danger/20 p-21 text-center text-xs font-medium text-danger">
            Failed to load events. {(error as Error).message}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && filteredEvents.length === 0 && (
          <div className="rounded-card border border-dashed border-black/15 dark:border-white/15 bg-surface-light/40 dark:bg-surface-dark/40 p-34 text-center">
            <span className="text-4xl">📂</span>
            <h3 className="mt-13 font-display text-lg font-semibold text-ink-light dark:text-ink-dark">
              No events found in this catalog
            </h3>
            <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-md mx-auto">
              {search
                ? `No events matching "${search}". Try adjusting your keywords.`
                : locationFilter === "Pune"
                ? "No Pune events currently found. Switch to 'All Locations' or check back soon."
                : "No events have been scheduled under this category yet."}
            </p>
            {locationFilter === "Pune" && (
              <button
                type="button"
                onClick={() => setLocationFilter("all")}
                className="mt-13 inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-21 py-8 text-xs font-semibold text-gold hover:bg-gold/20 dark:text-gold-soft transition-all"
              >
                <span>View All Locations</span>
              </button>
            )}
            {isOrganizer && (
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="mt-21 inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-21 py-8 text-xs font-semibold text-gold hover:bg-gold/20 dark:text-gold-soft transition-all"
              >
                <span>➕ Create First Event</span>
              </button>
            )}
          </div>
        )}

        {/* Events Grid */}
        {!isLoading && !error && filteredEvents.length > 0 && (
          <div className="grid grid-cols-1 gap-21 sm:grid-cols-2 lg:grid-cols-3">
            {filteredEvents.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>
        )}

        {/* Create Event Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md overflow-y-auto">
            <div className="w-full max-w-xl my-8 rounded-card border border-gold/40 bg-surface-light dark:bg-surface-dark p-21 sm:p-28 shadow-2xl backdrop-blur-2xl transition-all">
              <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-13">
                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-gold dark:text-gold-soft">
                    Catalog Management
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
                    placeholder="e.g., Annual Tech Summit 2026"
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
                        Catalog Category
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
                      placeholder="e.g., Generative AI in Production"
                      className={`w-full rounded-card border bg-canvas-light dark:bg-white/[0.04] px-13 py-10 text-xs text-ink-light dark:text-ink-dark focus:outline-none transition-colors ${
                        formErrors.topic
                          ? "border-danger focus:border-danger ring-1 ring-danger/30"
                          : "border-black/10 dark:border-white/10 focus:border-gold"
                      }`}
                    />
                    {formErrors.topic && (
                      <p className="mt-1 text-[11px] text-danger font-medium">{formErrors.topic}</p>
                    )}
                  </div>
                </div>

                {/* Schema status note */}
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

                <div className="flex justify-end gap-13 pt-13 border-t border-black/10 dark:border-white/10">
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateModal(false);
                      setFormErrors({});
                    }}
                    className="rounded-full border border-black/10 dark:border-white/10 px-21 py-8 text-xs font-medium text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createEventMutation.isPending || !name.trim() || !date}
                    className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 disabled:opacity-50 transition-all"
                  >
                    {createEventMutation.isPending ? "Creating..." : "Save Event"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </GoldenShell>
  );
}
