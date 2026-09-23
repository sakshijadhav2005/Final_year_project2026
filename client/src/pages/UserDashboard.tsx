import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { GoldenShell } from "@/layouts/GoldenShell";
import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { EventCard } from "@/components/dashboard/EventCard";
import { CreatePostForm } from "@/components/dashboard/CreatePostForm";
import { listEvents, listCommunityContent } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export function UserDashboard() {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);
  const navigate = useNavigate();

  const [showCreatePost, setShowCreatePost] = useState(false);

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

  const handleLogout = () => {
    clearAuth();
    navigate("/login");
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
              <span>{showCreatePost ? "✕ Close Form" : "✍️ Write Post"}</span>
            </button>

            <button
              type="button"
              onClick={handleLogout}
              className="rounded-full border border-black/10 dark:border-white/10 px-13 py-8 text-xs font-medium text-ink-light/60 hover:text-danger dark:text-ink-dim dark:hover:text-danger transition-colors"
            >
              Log out
            </button>
          </div>
        </div>

        {/* Catalog Navigation Options */}
        <section>
          <CatalogNav />
        </section>

        {/* Quick Post Creator */}
        {showCreatePost && (
          <section className="rounded-card border border-gold/30 bg-surface-light p-21 shadow-sm dark:border-gold/20 dark:bg-surface-dark">
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

        {/* Featured Events & Community Sections */}
        <div className="grid grid-cols-1 gap-34 lg:grid-cols-3">
          {/* Recent Events (2 columns) */}
          <div className="lg:col-span-2 space-y-21">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-ink-light dark:text-ink-dark flex items-center gap-8">
                <span>📅</span> Featured Event Catalogs
              </h2>
              <Link to="/catalog/all" className="text-xs font-semibold text-gold hover:underline dark:text-gold-soft">
                View All Catalogs ({events.length}) →
              </Link>
            </div>

            {eventsLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-21">
                {[1, 2].map((i) => (
                  <div key={i} className="h-44 rounded-card border border-black/5 dark:border-white/5 bg-black/[0.03] dark:bg-white/[0.03] animate-pulse" />
                ))}
              </div>
            ) : events.length === 0 ? (
              <div className="rounded-card border border-black/10 dark:border-white/10 bg-surface-light/40 dark:bg-surface-dark/40 p-34 text-center text-xs text-ink-light/60 dark:text-ink-dim">
                No events currently scheduled. Check back soon!
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-21">
                {events.slice(0, 4).map((event) => (
                  <EventCard key={event.id} event={event} />
                ))}
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
