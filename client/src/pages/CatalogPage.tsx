import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

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
  const [location, setLocation] = useState("");
  const [bannerImage, setBannerImage] = useState("");
  const [description, setDescription] = useState("");
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
        location: location || undefined,
        banner_image: bannerImage || undefined,
        description: description || undefined,
        type: selectedType,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setShowCreateModal(false);
      setName("");
      setDate("");
      setTopic("");
      setLocation("");
      setBannerImage("");
      setDescription("");
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
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10 font-sans">
      <div className="mx-auto max-w-7xl">
        {/* Header navigation bar */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Link
                to={isOrganizer ? "/organizer/dashboard" : "/user/dashboard"}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-300 transition-all hover:bg-white/10 hover:text-white"
              >
                ← Back to Dashboard
              </Link>
              <span className="rounded-md bg-amber-500/20 px-2 py-0.5 text-[11px] font-bold text-amber-300 border border-amber-500/30">
                Catalog Mode
              </span>
            </div>
            <h1 className="mt-2 text-2xl font-black tracking-tight text-white md:text-3xl">
              {type === "meetup" && "👥 Community Meetups"}
              {type === "event" && "🎪 Conferences & Keynote Events"}
              {type === "speech" && "🎤 Speeches, Panels & Tech Talks"}
              {(!type || type === "all") && "🌐 All Event Catalogs"}
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Browse organized sessions and access AI-generated blogs, newsletters, and social summaries.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/community"
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-slate-200 transition-all hover:border-amber-500/30 hover:bg-amber-500/10 hover:text-amber-300"
            >
              <span>💬 Community Feed</span>
            </Link>

            {isOrganizer && (
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-orange-500/20 transition-all hover:scale-105 hover:from-amber-400 hover:to-orange-500"
              >
                <span>➕ Create New Event</span>
              </button>
            )}
          </div>
        </div>

        {/* Catalog Navigation Tabs */}
        <CatalogNav />

        {/* Search & Stats Bar */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <span className="absolute inset-y-0 left-3 flex items-center text-slate-400 text-sm">
              🔍
            </span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by event name, topic, or speaker..."
              className="w-full rounded-xl border border-white/10 bg-slate-900/60 pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/20 backdrop-blur-xl"
            />
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>Showing <strong className="text-white">{filteredEvents.length}</strong> events</span>
            <span>•</span>
            <span className="text-emerald-400">● Live Catalogs</span>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div
                key={i}
                className="h-56 animate-pulse rounded-2xl border border-white/5 bg-slate-900/40 p-6"
              />
            ))}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-center text-sm text-rose-300">
            Failed to load events. {(error as Error).message}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && filteredEvents.length === 0 && (
          <div className="rounded-3xl border border-dashed border-white/10 bg-slate-900/30 p-12 text-center">
            <span className="text-4xl">📂</span>
            <h3 className="mt-3 text-lg font-bold text-white">No events found in this catalog</h3>
            <p className="mt-1 text-sm text-slate-400 max-w-md mx-auto">
              {search
                ? `No events matching "${search}". Try adjusting your keywords.`
                : "No events have been scheduled under this category yet."}
            </p>
            {isOrganizer && (
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="mt-5 inline-flex items-center gap-2 rounded-xl bg-amber-500/20 px-4 py-2 text-xs font-semibold text-amber-300 transition-all hover:bg-amber-500/30"
              >
                <span>➕ Create First Event</span>
              </button>
            )}
          </div>
        )}

        {/* Events Grid */}
        {!isLoading && !error && filteredEvents.length > 0 && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {filteredEvents.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>
        )}

        {/* Create Event Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-slate-900 p-6 shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <h3 className="text-lg font-bold text-white">Create New Event</h3>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="text-slate-400 hover:text-white"
                >
                  ✕
                </button>
              </div>

              {createEventMutation.error && (
                <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
                  {(createEventMutation.error as Error).message}
                </div>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  createEventMutation.mutate();
                }}
                className="mt-4 space-y-4"
              >
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-300">Event Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Annual Tech Summit 2026"
                    required
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-slate-300">Event Date</label>
                    <input
                      type="date"
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      required
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-amber-500/50 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-semibold text-slate-300">Catalog Category</label>
                    <select
                      value={selectedType}
                      onChange={(e) => setSelectedType(e.target.value as EventType)}
                      className="w-full rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-amber-500/50 focus:outline-none"
                    >
                      <option value="meetup">👥 Meetup</option>
                      <option value="event">🎪 Conference / Event</option>
                      <option value="speech">🎤 Speech / Talk</option>
                      <option value="other">📌 Other Session</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-slate-300">Topic / Theme</label>
                    <input
                      type="text"
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder="e.g., Generative AI in Production"
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-semibold text-slate-300">Location / City</label>
                    <input
                      type="text"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="e.g., San Francisco, CA or Virtual"
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-300">Banner Image URL</label>
                  <input
                    type="url"
                    value={bannerImage}
                    onChange={(e) => setBannerImage(e.target.value)}
                    placeholder="https://example.com/banner.jpg"
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-300">Description</label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description of the event..."
                    rows={3}
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-3 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-white/5"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createEventMutation.isPending || !name.trim() || !date}
                    className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20 transition-all hover:scale-105 disabled:opacity-50"
                  >
                    {createEventMutation.isPending ? "Creating..." : "Save Event"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
