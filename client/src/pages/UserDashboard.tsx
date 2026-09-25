import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { GoldenShell } from "@/layouts/GoldenShell";
import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { EventCard } from "@/components/dashboard/EventCard";
import { CreatePostForm } from "@/components/dashboard/CreatePostForm";
import { listEvents, listCommunityContent } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { getEventCity } from "@/lib/eventLocation";

export function UserDashboard() {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);
  const navigate = useNavigate();

  const [showCreatePost, setShowCreatePost] = useState(false);
  const [eventFilter, setEventFilter] = useState<"all" | "upcoming" | "past" | "pune">("all");
  const [copiedPostId, setCopiedPostId] = useState<string | null>(null);

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

  const myPosts = communityPosts.filter((p) => p.user_id === user?.id);

  // Date-based timeline filtering
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const upcomingEvents = events.filter((e) => new Date(e.date) >= today);
  const pastEvents = events.filter((e) => new Date(e.date) < today);
  const puneEvents = events.filter((e) => getEventCity(e) === "Pune");

  const displayedEvents =
    eventFilter === "upcoming"
      ? upcomingEvents
      : eventFilter === "past"
      ? pastEvents
      : eventFilter === "pune"
      ? puneEvents
      : events;

  const handleLogout = () => {
    clearAuth();
    navigate("/login");
  };

  const handleCopyPost = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedPostId(id);
      setTimeout(() => setCopiedPostId(null), 2000);
    } catch {
      // Graceful fallback
    }
  };

  return (
    <GoldenShell>
      <div className="space-y-34">
        {/* Top Header Banner */}
        <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between border-b border-black/10 dark:border-white/10 pb-21">
          <div className="flex items-center gap-13">
            <div className="flex h-11 w-11 items-center justify-center rounded-card border border-gold/30 bg-gold/10 font-display text-lg font-bold text-gold dark:text-gold-soft shadow-inner">
              E
            </div>
            <div>
              <div className="flex items-center gap-8">
                <h1 className="font-display text-2xl font-semibold text-ink-light dark:text-ink-dark">
                  EventAI <em className="not-italic text-gold dark:text-gold-soft">Community</em>
                </h1>
                <span className="rounded-full border border-teal/30 bg-teal/10 px-8 py-2 text-[10px] font-semibold text-teal">
                  Attendee Portal
                </span>
              </div>
              <p className="text-xs text-ink-light/60 dark:text-ink-dim">
                Welcome back, <span className="font-medium text-ink-light dark:text-ink-dark">{user?.email || "Attendee"}</span>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-13">
            <Link
              to="/community"
              className="inline-flex items-center gap-2 rounded-full border border-gold/30 bg-surface-light/80 dark:bg-white/[0.03] px-21 py-8 text-xs font-medium text-gold hover:border-gold transition-all dark:text-gold-soft"
            >
              <span>💬 Community Feed</span>
            </Link>

            <button
              type="button"
              onClick={() => setShowCreatePost((p) => !p)}
              className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 transition-all"
            >
              <span>{showCreatePost ? "✕ Close Form" : "✍️ Share Takeaway"}</span>
            </button>

            <Link
              to="/settings"
              className="rounded-full border border-black/10 dark:border-white/10 px-13 py-8 text-xs font-medium text-ink-light/70 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark transition-colors"
            >
              ⚙️ Profile
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
                Catalog Events
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
                {eventsLoading ? "—" : upcomingEvents.length}
              </span>
              {upcomingEvents.length > 0 && (
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
                Your Contributions
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
              Shared takeaways &amp; session notes
            </p>
          </div>

          <div className="rounded-card border border-gold/20 bg-surface-light p-21 shadow-sm backdrop-blur-xl dark:border-gold/20 dark:bg-surface-dark transition-all hover:border-gold/40">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
                Attendance Mode
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal/10 border border-teal/20 text-sm">
                🎟️
              </span>
            </div>
            <div className="mt-13 flex items-baseline gap-2">
              <span className="font-display text-2xl font-semibold text-teal">
                Open
              </span>
              <span className="rounded-full border border-teal/30 bg-teal/15 px-2 py-0.5 text-[10px] font-semibold text-teal">
                Discovery
              </span>
            </div>
            <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim">
              Explore catalogs &amp; read transcripts freely
            </p>
          </div>
        </section>

        {/* Catalog Navigation Options */}
        <section>
          <CatalogNav />
        </section>

        {/* Quick Post Creator */}
        {showCreatePost && (
          <section>
            <CreatePostForm
              events={events}
              onSuccess={() => setShowCreatePost(false)}
              onCancel={() => setShowCreatePost(false)}
            />
          </section>
        )}

        {/* Feature Highlights Grid */}
        <div className="grid grid-cols-1 gap-21 sm:grid-cols-3">
          <Link
            to="/catalog/meetup"
            className="group rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark transition-all hover:-translate-y-1 hover:border-teal/40 hover:shadow-lg dark:hover:border-teal/40"
          >
            <div className="flex items-center justify-between">
              <span className="text-2xl">👥</span>
              <span className="text-xs font-semibold text-teal group-hover:translate-x-1 transition-transform">
                Explore →
              </span>
            </div>
            <h3 className="mt-13 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
              Local Meetups
            </h3>
            <p className="mt-4 text-xs text-ink-light/70 dark:text-ink-dim">
              Discover networking meetups and read discussion highlights from recent gatherings.
            </p>
          </Link>

          <Link
            to="/catalog/event"
            className="group rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark transition-all hover:-translate-y-1 hover:border-lavender/40 hover:shadow-lg dark:hover:border-lavender/40"
          >
            <div className="flex items-center justify-between">
              <span className="text-2xl">🎪</span>
              <span className="text-xs font-semibold text-lavender group-hover:translate-x-1 transition-transform">
                Explore →
              </span>
            </div>
            <h3 className="mt-13 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
              Conferences &amp; Summits
            </h3>
            <p className="mt-4 text-xs text-ink-light/70 dark:text-ink-dim">
              Access full keynote recaps, newsletters, and slides from headline tech conferences.
            </p>
          </Link>

          <Link
            to="/catalog/speech"
            className="group rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark transition-all hover:-translate-y-1 hover:border-gold/40 hover:shadow-lg dark:hover:border-gold/40"
          >
            <div className="flex items-center justify-between">
              <span className="text-2xl">🎤</span>
              <span className="text-xs font-semibold text-gold dark:text-gold-soft group-hover:translate-x-1 transition-transform">
                Explore →
              </span>
            </div>
            <h3 className="mt-13 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
              Tech Talks &amp; Speeches
            </h3>
            <p className="mt-4 text-xs text-ink-light/70 dark:text-ink-dim">
              Deep-dive into individual speaker sessions, transcripts, and bite-sized takeaways.
            </p>
          </Link>
        </div>

        {/* Discover Events with Timeline & Location Filtering */}
        <section className="space-y-13">
          <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between border-b border-black/10 dark:border-white/10 pb-13">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-gold">
                Event Exploration
              </span>
              <h2 className="font-display text-xl font-semibold text-ink-light dark:text-ink-dark">
                Discover Sessions &amp; Keynotes
              </h2>
            </div>

            {/* Filter Pills */}
            <div className="flex flex-wrap items-center gap-8">
              {[
                { id: "all", label: `All Events (${events.length})` },
                { id: "upcoming", label: `Upcoming (${upcomingEvents.length})` },
                { id: "past", label: `Past Recaps (${pastEvents.length})` },
                { id: "pune", label: `📍 Pune Hub (${puneEvents.length})` },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setEventFilter(tab.id as typeof eventFilter)}
                  className={`rounded-full px-13 py-4 text-xs font-semibold transition-all ${
                    eventFilter === tab.id
                      ? "border border-gold/40 bg-gold/20 text-gold dark:text-gold-soft shadow-sm"
                      : "border border-black/10 dark:border-white/10 bg-surface-light/50 dark:bg-white/[0.02] text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {eventsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-21">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-48 rounded-card border border-black/5 dark:border-white/5 bg-black/[0.03] dark:bg-white/[0.03] animate-pulse"
                />
              ))}
            </div>
          ) : displayedEvents.length === 0 ? (
            <div className="rounded-card border border-dashed border-gold/20 bg-surface-light/40 dark:bg-surface-dark/40 p-34 text-center">
              <span className="text-3xl">📅</span>
              <h4 className="mt-8 font-display text-base font-semibold text-ink-light dark:text-ink-dark">
                {eventFilter === "upcoming"
                  ? "No upcoming events scheduled right now."
                  : eventFilter === "past"
                  ? "No past event recaps recorded yet."
                  : eventFilter === "pune"
                  ? "No events currently tagged for Pune."
                  : "No events available in the catalog."}
              </h4>
              <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-sm mx-auto">
                Explore all catalogs or check back later as organizers schedule new sessions.
              </p>
              {eventFilter !== "all" && (
                <button
                  type="button"
                  onClick={() => setEventFilter("all")}
                  className="mt-13 inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                >
                  View All Events
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-21">
              {displayedEvents.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          )}
        </section>

        {/* Featured Events & Community Sections */}
        <div className="grid grid-cols-1 gap-34 lg:grid-cols-3">
          {/* Latest Community Reflections (2 columns) */}
          <div className="lg:col-span-2 space-y-21">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-ink-light dark:text-ink-dark flex items-center gap-8">
                <span>💬</span> Recent Community Takeaways
              </h2>
              <Link to="/community" className="text-xs font-semibold text-gold hover:underline dark:text-gold-soft">
                View Community Feed ({communityPosts.length}) →
              </Link>
            </div>

            {postsLoading ? (
              <div className="space-y-13">
                {[1, 2].map((i) => (
                  <div key={i} className="h-28 rounded-card border border-black/5 dark:border-white/5 bg-black/[0.03] dark:bg-white/[0.03] animate-pulse" />
                ))}
              </div>
            ) : communityPosts.length === 0 ? (
              <div className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light/40 dark:bg-surface-dark/40 p-34 text-center text-xs text-ink-light/60 dark:text-ink-dim">
                No posts shared in the community yet. Be the first to publish your notes!
              </div>
            ) : (
              <div className="space-y-13">
                {communityPosts.slice(0, 4).map((post) => {
                  const matchedEvent = events.find((e) => e.id === post.event_id);
                  const isCopied = copiedPostId === post.id;

                  return (
                    <div
                      key={post.id}
                      className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light p-21 shadow-sm dark:bg-surface-dark dark:shadow-none hover:border-gold/30 transition-all"
                    >
                      <div className="flex items-start justify-between gap-13">
                        <div className="flex items-center gap-8 text-xs text-ink-light/60 dark:text-ink-dim">
                          <span className="font-semibold text-ink-light dark:text-ink-dark">
                            {post.author_name || "Community Member"}
                          </span>
                          <span className="rounded-full border border-gold/20 bg-gold/10 px-8 py-1 text-[10px] font-semibold text-gold dark:text-gold-soft">
                            {post.type.replace("_", " ").toUpperCase()}
                          </span>
                          <span>•</span>
                          <span>{post.created_at ? new Date(post.created_at).toLocaleDateString() : "Recent"}</span>
                        </div>

                        {matchedEvent && (
                          <Link
                            to={`/events/${matchedEvent.id}`}
                            className="inline-flex items-center gap-1 rounded-full border border-gold/30 bg-gold/10 px-8 py-1 text-[10px] font-medium text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                          >
                            <span>🎪 {matchedEvent.name}</span>
                          </Link>
                        )}
                      </div>

                      {post.title && (
                        <h4 className="mt-8 font-display text-sm font-semibold text-ink-light dark:text-ink-dark">
                          {post.title}
                        </h4>
                      )}

                      <p className="mt-4 text-xs text-ink-light/70 dark:text-ink-dim line-clamp-2 leading-relaxed">
                        {post.body}
                      </p>

                      <div className="mt-13 flex items-center justify-between border-t border-black/5 dark:border-white/5 pt-8 text-xs">
                        <button
                          type="button"
                          onClick={() => handleCopyPost(`${post.title ? post.title + '\n\n' : ''}${post.body}`, post.id)}
                          className="inline-flex items-center gap-1 text-ink-light/60 hover:text-gold dark:text-ink-dim dark:hover:text-gold-soft transition-colors"
                        >
                          <span>{isCopied ? "✓ Copied" : "📋 Copy"}</span>
                        </button>

                        {matchedEvent && (
                          <Link
                            to={`/events/${matchedEvent.id}`}
                            className="text-xs font-semibold text-gold hover:underline dark:text-gold-soft"
                          >
                            Event Hub &amp; Transcript →
                          </Link>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* User's Activity Sidebar (1 column) */}
          <div className="space-y-21">
            <h2 className="font-display text-lg font-semibold text-ink-light dark:text-ink-dark flex items-center gap-8">
              <span>👤</span> Your Contributions ({myPosts.length})
            </h2>

            {postsLoading ? (
              <div className="h-40 rounded-card border border-black/5 dark:border-white/5 bg-black/[0.03] dark:bg-white/[0.03] animate-pulse" />
            ) : myPosts.length === 0 ? (
              <div className="rounded-card border border-black/10 bg-surface-light p-21 text-center shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
                <span className="text-3xl">✍️</span>
                <p className="mt-8 text-xs text-ink-light/60 dark:text-ink-dim">
                  You haven't posted in the community yet. Share key takeaways from a session!
                </p>
                <button
                  type="button"
                  onClick={() => setShowCreatePost(true)}
                  className="mt-13 inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-21 py-8 text-xs font-semibold text-gold hover:bg-gold/20 dark:text-gold-soft transition-all"
                >
                  Write Your First Post
                </button>
              </div>
            ) : (
              <div className="space-y-13">
                {myPosts.slice(0, 3).map((p) => (
                  <div
                    key={p.id}
                    className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light p-13 shadow-sm dark:bg-surface-dark dark:shadow-none"
                  >
                    <div className="flex items-center justify-between text-xs text-ink-light/60 dark:text-ink-dim">
                      <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-2 text-[10px] font-semibold text-gold dark:text-gold-soft">
                        {p.type}
                      </span>
                      <span>{p.created_at ? new Date(p.created_at).toLocaleDateString() : ""}</span>
                    </div>
                    <h4 className="mt-8 font-medium text-sm text-ink-light dark:text-ink-dark">{p.title}</h4>
                    <p className="mt-4 text-xs text-ink-light/70 dark:text-ink-dim line-clamp-2">{p.body}</p>
                  </div>
                ))}
                <Link
                  to="/community"
                  className="block text-center text-xs font-semibold text-gold hover:underline dark:text-gold-soft pt-8"
                >
                  View all in Community Feed →
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </GoldenShell>
  );
}
