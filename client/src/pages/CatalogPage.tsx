import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { GoldenShell } from "@/layouts/GoldenShell";
import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { EventCard } from "@/components/dashboard/EventCard";
import { listEvents, createEvent, type EventType } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export function CatalogPage() {
  const { type } = useParams<{ type: string }>();
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [topic, setTopic] = useState("");
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
      return createEvent(token, {
        name,
        date,
        topic: topic || undefined,
        type: selectedType,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setShowCreateModal(false);
      setName("");
      setDate("");
      setTopic("");
    },
  });

  const filteredEvents = events.filter((e) => {
    const matchesSearch =
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      (e.topic && e.topic.toLowerCase().includes(search.toLowerCase())) ||
      (e.organizer_name && e.organizer_name.toLowerCase().includes(search.toLowerCase()));
    return matchesSearch;
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
                : "No events have been scheduled under this category yet."}
            </p>
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
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-card border border-gold/30 bg-surface-light dark:bg-surface-dark p-21 shadow-2xl backdrop-blur-xl">
              <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-13">
                <h3 className="font-display text-lg font-semibold text-ink-light dark:text-ink-dark">
                  Create New Event
                </h3>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="text-ink-light/50 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark transition-colors"
                >
                  ✕
                </button>
              </div>

              {createEventMutation.error && (
                <div className="mt-13 rounded-card border border-danger/30 bg-danger/20 p-13 text-xs font-medium text-danger">
                  {(createEventMutation.error as Error).message}
                </div>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  createEventMutation.mutate();
                }}
                className="mt-21 space-y-13"
              >
                <div>
                  <label className="mb-4 block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                    Event Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Annual Tech Summit 2026"
                    required
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-1 gap-13 sm:grid-cols-2">
                  <div>
                    <label className="mb-4 block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                      Event Date
                    </label>
                    <input
                      type="date"
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      required
                      className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="mb-4 block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                      Catalog Category
                    </label>
                    <select
                      value={selectedType}
                      onChange={(e) => setSelectedType(e.target.value as EventType)}
                      className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-surface-dark px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                    >
                      <option value="meetup">👥 Meetup</option>
                      <option value="event">🎪 Conference / Event</option>
                      <option value="speech">🎤 Speech / Talk</option>
                      <option value="other">📌 Other Session</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="mb-4 block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                    Topic / Theme
                  </label>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="e.g., Generative AI in Production"
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>

                <div className="flex justify-end gap-13 pt-13 border-t border-black/10 dark:border-white/10">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
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
