import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { CreatePostForm } from "@/components/dashboard/CreatePostForm";
import { listCommunityContent, listEvents } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function CommunityPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const eventIdFilter = searchParams.get("event_id") || undefined;

  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);

  const [activeTab, setActiveTab] = useState<string>("all");
  const [showCreatePost, setShowCreatePost] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  const { data: events = [] } = useQuery({
    queryKey: ["events"],
    queryFn: () => (token ? listEvents(token) : Promise.resolve([])),
    enabled: !!token,
  });

  const { data: posts = [], isLoading, error } = useQuery({
    queryKey: ["community-content", eventIdFilter],
    queryFn: () => (token ? listCommunityContent(token, { event_id: eventIdFilter }) : Promise.resolve([])),
    enabled: !!token,
  });

  const selectedEvent = events.find((e) => e.id === eventIdFilter);

  const filteredPosts = posts.filter((p) => {
    if (activeTab !== "all" && p.type !== activeTab) return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const matchTitle = p.title?.toLowerCase().includes(term);
      const matchBody = p.body?.toLowerCase().includes(term);
      const matchAuthor = p.author_name?.toLowerCase().includes(term);
      return matchTitle || matchBody || matchAuthor;
    }
    return true;
  });

  const isOrganizer = user?.role === "event_organizer" || user?.role === "admin";

  return (
    <GoldenShell>
      <div className="space-y-34">
        {/* Navigation & Header */}
        <div className="flex flex-wrap items-center justify-between gap-13">
          <div>
            <div className="flex items-center gap-3">
              <Link
                to={isOrganizer ? "/organizer/dashboard" : "/user/dashboard"}
                className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-3.5 py-1.5 text-xs font-semibold text-gold-soft transition-all hover:bg-gold/20"
              >
                ← Back to Dashboard
              </Link>
              <span className="rounded-full bg-gold/20 px-2.5 py-0.5 text-[10px] font-bold text-gold-soft border border-gold/30">
                Community Hub
              </span>
            </div>
            <h1 className="mt-2 font-display text-3xl font-normal italic text-ink-light dark:text-ink-dark">
              Community <em className="not-italic text-gold-soft">Feed &amp; Takeaways</em>
            </h1>
            <p className="text-xs text-ink-dim mt-1">
              Read session blogs, newsletters, keynotes, and member discussions from events across the platform.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowCreatePost((prev) => !prev)}
              className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gradient-to-r from-gold/20 via-orange-500/20 to-teal/20 px-5 py-2 text-xs font-semibold text-gold-soft shadow-lg hover:scale-105 transition-all"
            >
              <span>{showCreatePost ? "✕ Close Form" : "✍️ Write Post / Upload Recording"}</span>
            </button>
          </div>
        </div>

        {/* Catalog Navigation */}
        <CatalogNav />

        {/* Create Post Accordion/Card */}
        {showCreatePost && (
          <div className="mb-8">
            <CreatePostForm
              events={events}
              defaultEventId={eventIdFilter}
              onSuccess={() => setShowCreatePost(false)}
              onCancel={() => setShowCreatePost(false)}
            />
          </div>
        )}

        {/* Event Filter Banner (if filtered by event) */}
        {selectedEvent && (
          <div className="mb-6 flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🎯</span>
              <div>
                <span className="text-xs font-semibold text-amber-300 uppercase tracking-wider">
                  Filtering by Event
                </span>
                <h4 className="text-sm font-bold text-white">{selectedEvent.name}</h4>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                searchParams.delete("event_id");
                setSearchParams(searchParams);
              }}
              className="rounded-lg bg-white/10 px-3 py-1 text-xs font-semibold text-slate-200 hover:bg-white/20"
            >
              Clear Filter ✕
            </button>
          </div>
        )}

        {/* Feed Controls: Search & Category Tabs */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          {/* Tabs */}
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: "all", label: "All Posts", icon: "✨" },
              { id: "discussion", label: "Discussions", icon: "💬" },
              { id: "blog", label: "AI Blogs", icon: "📄" },
              { id: "linkedin", label: "LinkedIn Posts", icon: "💼" },
              { id: "newsletter", label: "Newsletters", icon: "✉️" },
              { id: "summary", label: "Summaries", icon: "📌" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition-all ${
                  activeTab === tab.id
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                    : "border border-white/5 bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white"
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Search bar */}
          <div className="relative w-full sm:w-64">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search feed..."
              className="w-full rounded-xl border border-white/10 bg-slate-900/60 pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
            />
            <span className="absolute left-2.5 top-2 text-xs text-slate-400">🔍</span>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-40 animate-pulse rounded-2xl border border-white/5 bg-slate-900/40 p-6"
              />
            ))}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-center text-sm text-rose-300">
            Failed to load community feed. {(error as Error).message}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && filteredPosts.length === 0 && (
          <div className="rounded-3xl border border-dashed border-white/10 bg-slate-900/30 p-12 text-center">
            <span className="text-4xl">💭</span>
            <h3 className="mt-3 text-lg font-bold text-white">No posts to display</h3>
            <p className="mt-1 text-sm text-slate-400 max-w-md mx-auto">
              Be the first to share your notes or spark a conversation with attendees!
            </p>
            <button
              type="button"
              onClick={() => setShowCreatePost(true)}
              className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20"
            >
              ✍️ Write a Post
            </button>
          </div>
        )}

        {/* Feed Posts List */}
        {!isLoading && !error && filteredPosts.length > 0 && (
          <div className="space-y-5">
            {filteredPosts.map((post) => {
              const matchedEvent = events.find((e) => e.id === post.event_id);
              const author = post.author_name || "Community Member";

              return (
                <div
                  key={post.id}
                  className="group relative overflow-hidden rounded-2xl border border-white/10 bg-slate-900/60 p-6 shadow-xl backdrop-blur-xl transition-all hover:border-white/20 hover:shadow-2xl"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-amber-500/30 to-purple-500/30 text-sm font-bold text-white shadow-inner">
                        {author[0].toUpperCase()}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-white">{author}</span>
                          <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
                            {post.type.replace("_", " ").toUpperCase()}
                          </span>
                        </div>
                        <span className="text-xs text-slate-400">
                          {post.created_at ? new Date(post.created_at).toLocaleString() : "Recently shared"}
                        </span>
                      </div>
                    </div>

                    {matchedEvent && (
                      <Link
                        to={`/community?event_id=${matchedEvent.id}`}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-xs font-semibold text-amber-300 hover:bg-amber-500/20"
                      >
                        <span>🎪 {matchedEvent.name}</span>
                      </Link>
                    )}
                  </div>

                  {post.title && (
                    <h3 className="mt-4 text-lg font-bold text-white group-hover:text-amber-300 transition-colors">
                      {post.title}
                    </h3>
                  )}

                  <div className="mt-3 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                    {post.body}
                  </div>

                  <div className="mt-5 flex items-center justify-between border-t border-white/5 pt-3 text-xs text-slate-400">
                    <div className="flex items-center gap-4">
                      <button
                        type="button"
                        onClick={(e) => {
                          const target = e.currentTarget;
                          target.classList.add("text-rose-400", "scale-110");
                          setTimeout(() => target.classList.remove("scale-110"), 200);
                        }}
                        className="flex items-center gap-1 transition-transform hover:text-rose-400"
                      >
                        <span>❤️</span> Helpful
                      </button>
                      <button
                        type="button"
                        className="flex items-center gap-1 hover:text-amber-300"
                      >
                        <span>💡</span> Insightful
                      </button>
                    </div>

                    <span className="text-[11px] text-slate-500">
                      Status: <strong className="text-emerald-400 font-medium">{post.status}</strong>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </GoldenShell>
  );
}
