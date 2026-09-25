import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { EventCard } from "@/components/dashboard/EventCard";
import { CreatePostForm } from "@/components/dashboard/CreatePostForm";
import { listEvents, listCommunityContent, listJobs, deleteJob } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function UserDashboard() {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clear);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [showCreatePost, setShowCreatePost] = useState(false);
  const [showPastSessions, setShowPastSessions] = useState(false);

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

  const { data: jobs = [] } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => (token ? listJobs(token) : Promise.resolve([])),
    enabled: !!token,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteJob(token as string, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["my_events"] });
    },
  });

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to permanently delete session ${id.slice(0, 8)}? All generated content and transcripts will be removed.`)) {
      deleteMutation.mutate(id);
    }
  };

  // Strict RBAC: only sessions belonging to this user
  const userSessions = jobs.filter((j) => {
    if (!user || user.role === "admin") return true;
    return j.user_id === user.id;
  });

  const myPosts = communityPosts.filter((p) => p.user_id === user?.id);

  return (
    <GoldenShell>
      <div className="space-y-34">
        {/* Top Header */}
        <div className="flex flex-wrap items-center justify-between gap-13">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gold">Community &amp; Attendee Portal</p>
            <h1 className="font-display text-3xl font-normal italic text-ink-light dark:text-ink-dark">
              Attendee <em className="not-italic text-gold-soft">Workspace</em>
            </h1>
            <p className="text-xs text-ink-dim mt-1">
              Welcome back, <strong className="text-gold-soft">{user?.email}</strong>
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/community"
              className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-4 py-2 text-xs font-semibold text-gold-soft hover:bg-gold/20 transition-all"
            >
              <span>💬 Community Feed</span>
            </Link>

            <button
              type="button"
              onClick={() => setShowCreatePost((p) => !p)}
              className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gradient-to-r from-gold/20 via-orange-500/20 to-teal/20 px-5 py-2 text-xs font-semibold text-gold-soft shadow-lg hover:scale-105 transition-all"
            >
              <span>{showCreatePost ? "✕ Close Form" : "✍️ Write Post / Upload Recording"}</span>
            </button>
          </div>
        </div>

        {/* Catalog Navigation Options */}
        <CatalogNav />

        {/* Past Recording Sessions Section (Above Highlights with RBAC) */}
        <div className="mb-8 rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-xl backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-500/10 border border-amber-500/20 text-lg">
                🎙️
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-white">Past Recording Sessions</h2>
                  <span className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
                    {userSessions.length} {userSessions.length === 1 ? "Session" : "Sessions"}
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  {user?.role === "admin"
                    ? "🛡️ Admin View: Showing all recording sessions across the platform"
                    : `👤 Isolated to: ${user?.email || "Attendee"} (${user?.role || "user"})`}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowPastSessions((prev) => !prev)}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-slate-200 hover:border-amber-500/40 hover:bg-amber-500/10 hover:text-amber-200 transition-all"
            >
              <span>{showPastSessions ? "▲ Hide Previous Sessions" : "▼ Show All Previous Sessions"}</span>
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold">
                {userSessions.length}
              </span>
            </button>
          </div>

          {/* Expanded Previous Sessions List */}
          {showPastSessions && (
            <div className="mt-5 space-y-3 animate-fadeIn">
              {userSessions.length === 0 ? (
                <div className="rounded-xl border border-white/5 bg-slate-950/40 p-6 text-center">
                  <span className="text-3xl">📭</span>
                  <p className="mt-2 text-xs font-semibold text-slate-300">No recording sessions found for your account</p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    When you or your team process an event recording, it will appear here for full transcript search and AI takeaways.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[360px] overflow-y-auto pr-1">
                  {userSessions.map((job) => {
                    const isReady = job.status === "ready_to_publish";
                    const isPending = job.status === "pending_review";
                    const isFailed = job.status === "failed";

                    return (
                      <Link
                        key={job.id}
                        to={`/jobs/${job.id}`}
                        className="group flex flex-col justify-between rounded-xl border border-white/10 bg-slate-950/60 p-4 transition-all hover:border-amber-500/40 hover:bg-slate-900/90"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2.5">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/5 border border-white/10 text-xs font-bold text-amber-300 group-hover:border-amber-500/40">
                              ⚡
                            </div>
                            <div>
                              <h4 className="text-xs font-bold text-white group-hover:text-amber-300 transition-colors">
                                Session {job.id.slice(0, 8)}
                              </h4>
                              <p className="text-[10px] text-slate-400">
                                {job.created_at ? new Date(job.created_at).toLocaleString() : "Recently"}
                              </p>
                            </div>
                          </div>

                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                              isReady
                                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                : isPending
                                ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                                : isFailed
                                ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                                : "bg-sky-500/15 text-sky-400 border border-sky-500/30"
                            }`}
                          >
                            {job.status.replace("_", " ")}
                          </span>
                        </div>

                        <div className="mt-3 flex items-center justify-between border-t border-white/5 pt-2 text-[11px]">
                          <span className="text-amber-400 font-semibold group-hover:underline">
                            View Session & Transcripts →
                          </span>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteSession(e, job.id)}
                            className="rounded-lg p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors z-10"
                            title="Delete session"
                          >
                            🗑️
                          </button>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Contributions & Post Creation Section (Prominently Above) */}
        <div className="mb-10 rounded-2xl border border-white/10 bg-slate-900/60 p-6 shadow-xl backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4 mb-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-600 font-bold text-white shadow-md shadow-orange-500/20 text-lg">
                ✍️
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-white">Your Contributions &amp; Content Hub</h2>
                  <span className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
                    {myPosts.length} {myPosts.length === 1 ? "Post" : "Posts"}
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  Generate multi-format content from session recordings, or write direct discussion takeaways for the community.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowCreatePost((p) => !p)}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20 hover:scale-105 transition-all"
            >
              <span>{showCreatePost ? "✕ Close Creator" : "✍️ Write Post / Upload Recording"}</span>
            </button>
          </div>

          {/* Quick Post Creator & Full AI Workflow */}
          {showCreatePost && (
            <div className="mb-6">
              <CreatePostForm
                events={events}
                onSuccess={() => setShowCreatePost(false)}
                onCancel={() => setShowCreatePost(false)}
              />
            </div>
          )}

          {/* User's Existing Posts or Empty State Callout */}
          {postsLoading ? (
            <div className="h-28 rounded-xl bg-white/5 animate-pulse" />
          ) : myPosts.length === 0 ? (
            <div className="rounded-2xl border border-white/5 bg-slate-950/40 p-8 text-center">
              <span className="text-4xl">✍️</span>
              <p className="mt-3 text-sm font-semibold text-slate-200">
                You haven't posted in the community yet. Share key takeaways from a session!
              </p>
              <p className="mt-1 text-xs text-slate-400 max-w-md mx-auto">
                Upload a recording to let our AI pipeline transcribe and draft blogs, newsletters, and social posts, or write a direct discussion note.
              </p>
              {!showCreatePost && (
                <button
                  type="button"
                  onClick={() => setShowCreatePost(true)}
                  className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-2.5 text-xs font-bold text-white shadow-lg shadow-orange-500/20 hover:scale-105 transition-all"
                >
                  Write Your First Post
                </button>
              )}
            </div>
          ) : (
            <div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {myPosts.slice(0, 3).map((p) => (
                  <div
                    key={p.id}
                    className="flex flex-col justify-between rounded-xl border border-white/10 bg-slate-950/60 p-4 transition-all hover:border-amber-500/30"
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] font-bold text-amber-300 uppercase">
                          {p.type}
                        </span>
                        <span className="text-[10px]">
                          {p.created_at ? new Date(p.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>
                      <h4 className="mt-2 text-xs font-bold text-white line-clamp-1">{p.title}</h4>
                      <p className="mt-1 text-[11px] text-slate-300 line-clamp-2">{p.body}</p>
                    </div>

                    <Link
                      to="/community"
                      className="mt-3 text-[11px] font-semibold text-amber-400 hover:underline pt-2 border-t border-white/5"
                    >
                      View in Community Feed →
                    </Link>
                  </div>
                ))}
              </div>

              {myPosts.length > 3 && (
                <div className="mt-3 text-right">
                  <Link
                    to="/community"
                    className="text-xs font-semibold text-amber-400 hover:underline"
                  >
                    View all {myPosts.length} posts in Community Feed →
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>

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
            <h3 className="mt-3 text-base font-bold text-white">Conferences &amp; Summits</h3>
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
            <h3 className="mt-3 text-base font-bold text-white">Tech Talks &amp; Speeches</h3>
            <p className="mt-1 text-xs text-slate-400">
              Deep-dive into individual speaker sessions, transcripts, and bite-sized takeaways.
            </p>
          </Link>
        </div>

        {/* Featured Events Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <span>📅</span> Featured Event Catalogs
            </h2>
            <Link to="/catalog/all" className="text-xs font-semibold text-amber-400 hover:underline">
              View All Catalogs ({events.length}) →
            </Link>
          </div>

          {eventsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-44 rounded-2xl bg-white/5 animate-pulse" />
              ))}
            </div>
          ) : events.length === 0 ? (
            <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-8 text-center text-sm text-slate-400">
              No events currently scheduled. Check back soon!
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              {events.slice(0, 4).map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          )}
        </div>
      </div>
    </GoldenShell>
  );
}
