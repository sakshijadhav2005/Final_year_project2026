import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

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
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10 font-sans">
      <div className="mx-auto max-w-7xl">
        {/* Top Navbar */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-white/10 pb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-600 font-black text-white shadow-lg shadow-orange-500/20">
              E
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-black text-white">EventAI Community</h1>
                <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-300 border border-emerald-500/30">
                  Attendee Portal
                </span>
              </div>
              <p className="text-xs text-slate-400">Welcome, {user?.email}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/community"
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-white/10"
            >
              <span>💬 Community Feed</span>
            </Link>

            <button
              type="button"
              onClick={() => setShowCreatePost((p) => !p)}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20 hover:scale-105 transition-all"
            >
              <span>{showCreatePost ? "✕ Close Form" : "✍️ Write Post"}</span>
            </button>

            <button
              type="button"
              onClick={handleLogout}
              className="rounded-xl border border-white/10 px-3 py-2 text-xs font-medium text-slate-400 hover:text-white"
            >
              Log out
            </button>
          </div>
        </div>

        {/* Catalog Navigation Options */}
        <CatalogNav />

        {/* Quick Post Creator */}
        {showCreatePost && (
          <div className="mb-8">
            <CreatePostForm
              events={events}
              onSuccess={() => setShowCreatePost(false)}
              onCancel={() => setShowCreatePost(false)}
            />
          </div>
        )}

        {/* Feature Highlights Grid */}
        <div className="mb-10 grid grid-cols-1 gap-5 sm:grid-cols-3">
          <Link
            to="/catalog/meetup"
            className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-emerald-950/40 via-slate-900/60 to-slate-900/60 p-5 backdrop-blur-xl transition-all hover:-translate-y-1 hover:border-emerald-500/40 hover:shadow-xl hover:shadow-emerald-500/10"
          >
            <div className="flex items-center justify-between">
              <span className="text-3xl">👥</span>
              <span className="text-xs font-bold text-emerald-400 group-hover:translate-x-1 transition-transform">
                Explore →
              </span>
            </div>
            <h3 className="mt-3 text-base font-bold text-white">Local Meetups</h3>
            <p className="mt-1 text-xs text-slate-400">
              Discover networking meetups and read discussion highlights from recent gatherings.
            </p>
          </Link>

          <Link
            to="/catalog/event"
            className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-purple-950/40 via-slate-900/60 to-slate-900/60 p-5 backdrop-blur-xl transition-all hover:-translate-y-1 hover:border-purple-500/40 hover:shadow-xl hover:shadow-purple-500/10"
          >
            <div className="flex items-center justify-between">
              <span className="text-3xl">🎪</span>
              <span className="text-xs font-bold text-purple-400 group-hover:translate-x-1 transition-transform">
                Explore →
              </span>
            </div>
            <h3 className="mt-3 text-base font-bold text-white">Conferences & Summits</h3>
            <p className="mt-1 text-xs text-slate-400">
              Access full keynote recaps, newsletters, and slides from headline tech conferences.
            </p>
          </Link>

          <Link
            to="/catalog/speech"
            className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-sky-950/40 via-slate-900/60 to-slate-900/60 p-5 backdrop-blur-xl transition-all hover:-translate-y-1 hover:border-sky-500/40 hover:shadow-xl hover:shadow-sky-500/10"
          >
            <div className="flex items-center justify-between">
              <span className="text-3xl">🎤</span>
              <span className="text-xs font-bold text-sky-400 group-hover:translate-x-1 transition-transform">
                Explore →
              </span>
            </div>
            <h3 className="mt-3 text-base font-bold text-white">Tech Talks & Speeches</h3>
            <p className="mt-1 text-xs text-slate-400">
              Deep-dive into individual speaker sessions, transcripts, and bite-sized takeaways.
            </p>
          </Link>
        </div>

        {/* Featured Events & Community Sections */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          {/* Recent Events (2 columns) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <span>📅</span> Featured Event Catalogs
              </h2>
              <Link to="/catalog/all" className="text-xs font-semibold text-amber-400 hover:underline">
                View All Catalogs ({events.length}) →
              </Link>
            </div>

            {eventsLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[1, 2].map((i) => (
                  <div key={i} className="h-44 rounded-2xl bg-white/5 animate-pulse" />
                ))}
              </div>
            ) : events.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-8 text-center text-sm text-slate-400">
                No events currently scheduled. Check back soon!
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {events.slice(0, 4).map((event) => (
                  <EventCard key={event.id} event={event} />
                ))}
              </div>
            )}
          </div>

          {/* User's Activity Sidebar (1 column) */}
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <span>👤</span> Your Contributions ({myPosts.length})
            </h2>

            {postsLoading ? (
              <div className="h-40 rounded-2xl bg-white/5 animate-pulse" />
            ) : myPosts.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-center">
                <span className="text-3xl">✍️</span>
                <p className="mt-2 text-xs text-slate-400">
                  You haven't posted in the community yet. Share key takeaways from a session!
                </p>
                <button
                  type="button"
                  onClick={() => setShowCreatePost(true)}
                  className="mt-4 inline-flex items-center gap-1 rounded-xl bg-amber-500/20 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/30"
                >
                  Write Your First Post
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {myPosts.slice(0, 3).map((p) => (
                  <div
                    key={p.id}
                    className="rounded-xl border border-white/10 bg-slate-900/50 p-4 backdrop-blur-md"
                  >
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-bold text-amber-300">
                        {p.type}
                      </span>
                      <span>{p.created_at ? new Date(p.created_at).toLocaleDateString() : ""}</span>
                    </div>
                    <h4 className="mt-2 text-sm font-bold text-white">{p.title}</h4>
                    <p className="mt-1 text-xs text-slate-300 line-clamp-2">{p.body}</p>
                  </div>
                ))}
                <Link
                  to="/community"
                  className="block text-center text-xs font-semibold text-amber-400 hover:underline pt-2"
                >
                  View all in Community Feed →
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
