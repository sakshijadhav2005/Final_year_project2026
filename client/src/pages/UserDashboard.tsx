import { useState } from "react";
import { Link } from "react-router-dom";
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
            <h1 className="font-display text-h1 font-semibold text-ink-light dark:text-ink-dark">
              Attendee Workspace
            </h1>
            <p className="text-xs text-ink-dim mt-1">
              Welcome back, <strong className="text-gold-soft">{user?.email}</strong>
            </p>
          </div>

          <div className="flex items-center gap-13">
            <Link
              to="/community"
              className="btn-ghost btn-sm"
            >
              <span>💬 Community Feed</span>
            </Link>

            <button
              type="button"
              onClick={() => setShowCreatePost((p) => !p)}
              className="inline-flex items-center gap-8 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold-soft transition-all"
            >
              <span>{showCreatePost ? "✕ Close Form" : "✍️ Write Post / Upload Recording"}</span>
            </button>
          </div>
        </div>

        {/* Catalog Navigation Options */}
        <CatalogNav />

        {/* Past Recording Sessions Section (Above Highlights with RBAC) */}
        <div className="mb-34 rounded-panel border border-white/[0.08] bg-surface p-21">
          <div className="flex flex-wrap items-center justify-between gap-13">
            <div className="flex items-center gap-13">
              <div className="flex h-10 w-10 items-center justify-center rounded-panel bg-amber-500/10 border border-amber-500/20 text-lg">
                🎙️
              </div>
              <div>
                <div className="flex items-center gap-8">
                  <h2 className="text-h2 font-semibold text-white">Past Recording Sessions</h2>
                  <span className="rounded-full bg-amber-500/20 px-8 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
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
              className="inline-flex items-center gap-8 rounded-card border border-white/[0.08] bg-white/5 px-13 py-8 text-xs font-semibold text-slate-200 hover:border-amber-500/40 hover:bg-amber-500/10 hover:text-amber-200 transition-all"
            >
              <span>{showPastSessions ? "▲ Hide Previous Sessions" : "▼ Show All Previous Sessions"}</span>
              <span className="rounded-full bg-white/10 px-8 py-0.5 text-[10px] font-bold">
                {userSessions.length}
              </span>
            </button>
          </div>

          {/* Expanded Previous Sessions List */}
          {showPastSessions && (
            <div className="mt-21 space-y-13 border-t border-white/[0.08] pt-21">
              {userSessions.length === 0 ? (
                <div className="rounded-card border border-white/5 bg-white/[0.02] p-21 text-center">
                  <span className="text-3xl">📭</span>
                  <p className="mt-8 text-xs font-semibold text-slate-300">No recording sessions found for your account</p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    When you or your team process an event recording, it will appear here for full transcript search and AI takeaways.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-13 max-h-[360px] overflow-y-auto pr-1">
                  {userSessions.map((job) => {
                    const isReady = job.status === "ready_to_publish";
                    const isPending = job.status === "pending_review";
                    const isFailed = job.status === "failed";

                    return (
                      <Link
                        key={job.id}
                        to={`/jobs/${job.id}`}
                        className="glass-interactive neu-raised group flex flex-col justify-between rounded-card border border-white/[0.08] bg-white/[0.02] p-13"
                      >
                        <div className="flex items-start justify-between gap-13">
                          <div className="flex items-center gap-8">
                            <div className="flex h-[32px] w-[32px] items-center justify-center rounded-lg bg-white/5 border border-white/[0.08] text-xs font-bold text-amber-300 group-hover:border-amber-500/40">
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
                            className={`rounded-full px-8 py-0.5 text-[10px] font-bold ${
                              isReady
                                ? "bg-emerald-500/15 text-emerald-400 border border-white/[0.08]"
                                : isPending
                                ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                                : isFailed
                                ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                                : "bg-sky-500/15 text-sky-400 border border-white/[0.08]"
                            }`}
                          >
                            {job.status.replace("_", " ")}
                          </span>
                        </div>

                        <div className="mt-13 flex items-center justify-between border-t border-white/5 pt-8 text-[11px]">
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
        <div className="mb-34 rounded-panel border border-white/[0.08] bg-surface p-21">
          <div className="flex flex-wrap items-center justify-between gap-13 border-b border-white/[0.08] pb-13 mb-21">
            <div className="flex items-center gap-13">
              <div className="flex h-10 w-10 items-center justify-center rounded-panel bg-amber-400 font-bold text-on-accent text-lg">
                ✍️
              </div>
              <div>
                <div className="flex items-center gap-8">
                  <h2 className="text-h2 font-semibold text-white">Your Contributions &amp; Content Hub</h2>
                  <span className="rounded-full bg-amber-500/20 px-8 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
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
              className="inline-flex items-center gap-[2px] rounded-card bg-amber-400 px-[4px] py-[2px] text-xs font-bold text-on-accent transition-all"
            >
              <span>{showCreatePost ? "✕ Close Creator" : "✍️ Write Post / Upload Recording"}</span>
            </button>
          </div>

          {/* Quick Post Creator & Full AI Workflow */}
          {showCreatePost && (
            <div className="mb-21">
              <CreatePostForm
                events={events}
                onSuccess={() => setShowCreatePost(false)}
                onCancel={() => setShowCreatePost(false)}
              />
            </div>
          )}

          {/* User's Existing Posts or Empty State Callout */}
          {postsLoading ? (
            <div className="h-28 rounded-card bg-white/5 animate-pulse" />
          ) : myPosts.length === 0 ? (
            <div className="rounded-panel border border-white/5 bg-white/[0.02] p-34 text-center">
              <span className="text-4xl">✍️</span>
              <p className="mt-13 text-sm font-semibold text-slate-200">
                You haven't posted in the community yet. Share key takeaways from a session!
              </p>
              <p className="mt-1 text-xs text-slate-400 max-w-md mx-auto">
                Upload a recording to let our AI pipeline transcribe and draft blogs, newsletters, and social posts, or write a direct discussion note.
              </p>
              {!showCreatePost && (
                <button
                  type="button"
                  onClick={() => setShowCreatePost(true)}
                  className="mt-5 inline-flex items-center gap-[2px] rounded-card bg-amber-400 px-5 py-2.5 text-xs font-bold text-on-accent transition-all"
                >
                  Write Your First Post
                </button>
              )}
            </div>
          ) : (
            <div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-13">
                {myPosts.slice(0, 3).map((p) => (
                  <div
                    key={p.id}
                    className="flex flex-col justify-between rounded-card border border-white/[0.08] bg-white/[0.02] p-13 transition-all hover:border-amber-500/30"
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span className="rounded bg-white/10 px-8 py-0.5 text-[10px] font-bold text-amber-300">
                          {p.type}
                        </span>
                        <span className="text-[10px]">
                          {p.created_at ? new Date(p.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>
                      <h4 className="mt-8 text-xs font-bold text-white line-clamp-1">{p.title}</h4>
                      <p className="mt-1 text-[11px] text-slate-300 line-clamp-2">{p.body}</p>
                    </div>

                    <Link
                      to="/community"
                      className="mt-13 text-[11px] font-semibold text-amber-400 hover:underline pt-8 border-t border-white/5"
                    >
                      View in Community Feed →
                    </Link>
                  </div>
                ))}
              </div>

              {myPosts.length > 3 && (
                <div className="mt-13 text-right">
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
        <div className="mb-34 grid grid-cols-1 gap-21 sm:grid-cols-3">
          <Link
            to="/catalog/meetup"
            className="glass-interactive group relative overflow-hidden rounded-panel border border-white/[0.08] bg-surface p-21"
          >
            <div className="flex items-center justify-between">
              <span className="text-3xl">👥</span>
              <span className="text-xs font-semibold text-amber-300">
                Explore →
              </span>
            </div>
            <h3 className="mt-13 text-base font-bold text-white">Local Meetups</h3>
            <p className="mt-1 text-xs text-slate-400">
              Discover networking meetups and read discussion highlights from recent gatherings.
            </p>
          </Link>

          <Link
            to="/catalog/event"
            className="glass-interactive group relative overflow-hidden rounded-panel border border-white/[0.08] bg-surface p-21"
          >
            <div className="flex items-center justify-between">
              <span className="text-3xl">🎪</span>
              <span className="text-xs font-semibold text-amber-300">
                Explore →
              </span>
            </div>
            <h3 className="mt-13 text-base font-bold text-white">Conferences &amp; Summits</h3>
            <p className="mt-1 text-xs text-slate-400">
              Access full keynote recaps, newsletters, and slides from headline tech conferences.
            </p>
          </Link>

          <Link
            to="/catalog/speech"
            className="glass-interactive group relative overflow-hidden rounded-panel border border-white/[0.08] bg-surface p-21"
          >
            <div className="flex items-center justify-between">
              <span className="text-3xl">🎤</span>
              <span className="text-xs font-semibold text-amber-300">
                Explore →
              </span>
            </div>
            <h3 className="mt-13 text-base font-bold text-white">Tech Talks &amp; Speeches</h3>
            <p className="mt-1 text-xs text-slate-400">
              Deep-dive into individual speaker sessions, transcripts, and bite-sized takeaways.
            </p>
          </Link>
        </div>

        {/* Featured Events Section */}
        <div className="space-y-13">
          <div className="flex items-center justify-between">
            <h2 className="text-h2 font-semibold text-white flex items-center gap-8">
              <span>📅</span> Featured Event Catalogs
            </h2>
            <Link to="/catalog/all" className="text-xs font-semibold text-amber-400 hover:underline">
              View All Catalogs ({events.length}) →
            </Link>
          </div>

          {eventsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-13">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-44 rounded-panel bg-white/5 animate-pulse" />
              ))}
            </div>
          ) : events.length === 0 ? (
            <div className="rounded-panel border border-white/[0.08] bg-surface p-34 text-center text-sm text-slate-400">
              No events currently scheduled. Check back soon!
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-13">
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
