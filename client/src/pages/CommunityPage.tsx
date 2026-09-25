import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { GoldenShell } from "@/layouts/GoldenShell";
import { CatalogNav } from "@/components/dashboard/CatalogNav";
import { CreatePostForm } from "@/components/dashboard/CreatePostForm";
import { listCommunityContent, listEvents, type ContentPublic } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export function CommunityPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const eventIdFilter = searchParams.get("event_id") || undefined;
  const repurposeId = searchParams.get("repurpose") || undefined;

  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);

  const [activeTab, setActiveTab] = useState<string>("all");
  const [showCreatePost, setShowCreatePost] = useState(Boolean(repurposeId));
  const [searchTerm, setSearchTerm] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const [prefillTitle, setPrefillTitle] = useState("");
  const [prefillBody, setPrefillBody] = useState("");
  const [prefillEventId, setPrefillEventId] = useState(eventIdFilter || "");

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
  const selectedRepurposePost = posts.find((p) => p.id === repurposeId);

  const handleCopy = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Graceful fallback
    }
  };

  const handleStartRepurpose = (post: ContentPublic) => {
    setPrefillTitle(post.title ? `Reflection on: ${post.title}` : `Reflection on ${post.type}`);
    setPrefillBody(`"${post.body.slice(0, 200)}..."\n\nKey takeaways and reflection:\n`);
    setPrefillEventId(post.event_id || eventIdFilter || "");
    setShowCreatePost(true);
    window.scrollTo({ top: 180, behavior: "smooth" });
  };

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

  const TYPE_BADGES: Record<string, { label: string; icon: string; badgeClass: string }> = {
    discussion: { label: "Discussion", icon: "💬", badgeClass: "bg-teal/15 text-teal border-teal/30" },
    blog: { label: "Blog Article", icon: "📄", badgeClass: "bg-blue-500/15 text-blue-400 border-blue-500/30" },
    linkedin: { label: "LinkedIn Post", icon: "💼", badgeClass: "bg-purple-500/15 text-purple-400 border-purple-500/30" },
    newsletter: { label: "Newsletter", icon: "✉️", badgeClass: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
    summary: { label: "Summary", icon: "📊", badgeClass: "bg-gold/15 text-gold-soft border-gold/30" },
    flyer: { label: "Flyer", icon: "📢", badgeClass: "bg-orange-500/15 text-orange-400 border-orange-500/30" },
    question: { label: "Question", icon: "❓", badgeClass: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
    announcement: { label: "Announcement", icon: "📣", badgeClass: "bg-rose-500/15 text-rose-400 border-rose-500/30" },
  };

  return (
    <GoldenShell>
      <div className="space-y-34">
        {/* Navigation & Header */}
        <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between border-b border-black/10 dark:border-white/10 pb-21">
          <div>
            <div className="flex items-center gap-13">
              <Link
                to={isOrganizer ? "/organizer/dashboard" : "/user/dashboard"}
                className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-surface-light/80 dark:bg-white/[0.03] px-13 py-4 text-xs font-medium text-gold hover:border-gold transition-all dark:text-gold-soft"
              >
                ← Back to Dashboard
              </Link>
              <span className="rounded-full border border-teal/30 bg-teal/10 px-8 py-2 text-[11px] font-semibold text-teal">
                Community Hub
              </span>
            </div>
            <h1 className="mt-8 font-display text-2xl sm:text-3xl font-semibold tracking-tight text-ink-light dark:text-ink-dark">
              🌐 EventAI Community Feed
            </h1>
            <p className="mt-4 text-xs sm:text-sm text-ink-light/60 dark:text-ink-dim">
              Explore session blogs, keynotes, newsletters, and attendee takeaways across the platform.
            </p>
          </div>

          <div className="flex items-center gap-13">
            <button
              type="button"
              onClick={() => setShowCreatePost((prev) => !prev)}
              className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 transition-all shadow-sm"
            >
              <span>{showCreatePost ? "✕ Close Form" : "✍️ Write Reflection"}</span>
            </button>
          </div>
        </div>

        {/* Catalog Navigation */}
        <section>
          <CatalogNav />
        </section>

        {/* Repurpose Notice Banner */}
        {selectedRepurposePost && (
          <div className="flex items-center justify-between rounded-card border border-gold/30 bg-gold/10 p-13 text-xs">
            <div className="flex items-center gap-8 text-ink-light dark:text-ink-dark">
              <span className="text-base">✍️</span>
              <span>
                Repurposing piece: <strong className="text-gold dark:text-gold-soft">"{selectedRepurposePost.title || selectedRepurposePost.type}"</strong> by {selectedRepurposePost.author_name || "Speaker"}
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                searchParams.delete("repurpose");
                setSearchParams(searchParams);
              }}
              className="text-xs text-ink-light/60 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark"
            >
              Dismiss ✕
            </button>
          </div>
        )}

        {/* Create Post Accordion/Card */}
        {showCreatePost && (
          <section>
            <CreatePostForm
              events={events}
              defaultEventId={prefillEventId || eventIdFilter || ""}
              defaultTitle={prefillTitle}
              defaultBody={prefillBody}
              onSuccess={() => {
                setShowCreatePost(false);
                setPrefillTitle("");
                setPrefillBody("");
                if (repurposeId) {
                  searchParams.delete("repurpose");
                  setSearchParams(searchParams);
                }
              }}
              onCancel={() => {
                setShowCreatePost(false);
                setPrefillTitle("");
                setPrefillBody("");
                if (repurposeId) {
                  searchParams.delete("repurpose");
                  setSearchParams(searchParams);
                }
              }}
            />
          </section>
        )}

        {/* Event Filter Banner (if filtered by event) */}
        {selectedEvent && (
          <div className="flex items-center justify-between rounded-card border border-gold/30 bg-gold/10 p-13">
            <div className="flex items-center gap-13">
              <span className="text-2xl">🎪</span>
              <div>
                <span className="text-[10px] font-semibold text-gold dark:text-gold-soft uppercase tracking-wider">
                  Filtering by Event
                </span>
                <div className="flex items-center gap-8">
                  <h4 className="font-display text-sm font-semibold text-ink-light dark:text-ink-dark">
                    {selectedEvent.name}
                  </h4>
                  <Link
                    to={`/events/${selectedEvent.id}`}
                    className="text-xs text-gold-soft underline hover:text-gold"
                  >
                    Open Event Hub →
                  </Link>
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                searchParams.delete("event_id");
                setSearchParams(searchParams);
              }}
              className="rounded-full border border-black/10 dark:border-white/10 bg-surface-light/80 dark:bg-white/[0.05] px-13 py-4 text-xs font-semibold text-ink-light dark:text-ink-dark hover:border-gold transition-colors"
            >
              Clear Filter ✕
            </button>
          </div>
        )}

        {/* Feed Controls: Search & Category Tabs */}
        <div className="flex flex-col gap-13 sm:flex-row sm:items-center sm:justify-between">
          {/* Tabs */}
          <div className="flex flex-wrap items-center gap-8">
            {[
              { id: "all", label: "All Posts", icon: "✨" },
              { id: "discussion", label: "Discussions", icon: "💬" },
              { id: "blog", label: "AI Blogs", icon: "📄" },
              { id: "linkedin", label: "LinkedIn Posts", icon: "💼" },
              { id: "newsletter", label: "Newsletters", icon: "✉️" },
              { id: "summary", label: "Summaries", icon: "📊" },
              { id: "flyer", label: "Flyers", icon: "📢" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-1.5 rounded-full px-13 py-4 text-xs font-semibold transition-all ${
                  activeTab === tab.id
                    ? "border border-gold/40 bg-gold/20 text-gold dark:text-gold-soft shadow-sm"
                    : "border border-black/10 dark:border-white/10 bg-surface-light/50 dark:bg-white/[0.02] text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark"
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Search bar */}
          <div className="relative w-full sm:w-64">
            <span className="absolute inset-y-0 left-3 flex items-center text-xs text-ink-light/40 dark:text-ink-dim">
              🔍
            </span>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search feed..."
              className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] pl-34 pr-13 py-4 text-xs text-ink-light dark:text-ink-dark placeholder-ink-light/40 dark:placeholder-ink-dim/50 focus:border-gold focus:outline-none"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm("")}
                className="absolute inset-y-0 right-2 flex items-center text-xs text-ink-light/40 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="space-y-13">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-40 animate-pulse rounded-card border border-black/5 dark:border-white/5 bg-black/[0.03] dark:bg-white/[0.03] p-21"
              />
            ))}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="rounded-card border border-danger/30 bg-danger/20 p-21 text-center text-xs font-medium text-danger">
            Failed to load community feed. {(error as Error).message}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && filteredPosts.length === 0 && (
          <div className="rounded-card border border-dashed border-gold/20 bg-surface-light/40 dark:bg-surface-dark/40 p-34 text-center">
            <span className="text-4xl">💭</span>
            <h3 className="mt-13 font-display text-lg font-semibold text-ink-light dark:text-ink-dark">
              No posts to display
            </h3>
            <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim max-w-md mx-auto">
              Be the first to share your notes or spark a conversation with attendees!
            </p>
            <button
              type="button"
              onClick={() => setShowCreatePost(true)}
              className="mt-21 inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 transition-all shadow-sm"
            >
              ✍️ Write a Post
            </button>
          </div>
        )}

        {/* Feed Posts List */}
        {!isLoading && !error && filteredPosts.length > 0 && (
          <div className="space-y-21">
            {filteredPosts.map((post) => {
              const matchedEvent = events.find((e) => e.id === post.event_id);
              const author = post.author_name || "Community Member";
              const typeConfig = TYPE_BADGES[post.type] || {
                label: post.type,
                icon: "📌",
                badgeClass: "bg-white/[0.05] text-ink-light dark:text-ink-dark border-white/10",
              };
              const isCopied = copiedId === post.id;

              return (
                <div
                  key={post.id}
                  className="group rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none hover:border-gold/30 transition-all"
                >
                  <div className="flex flex-wrap items-start justify-between gap-13">
                    <div className="flex items-center gap-13">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full border border-gold/30 bg-gold/10 font-display text-sm font-bold text-gold dark:text-gold-soft shadow-inner">
                        {author[0].toUpperCase()}
                      </div>
                      <div>
                        <div className="flex items-center gap-8">
                          <span className="text-sm font-semibold text-ink-light dark:text-ink-dark">{author}</span>
                          <span className={`inline-flex items-center gap-1 rounded-full border px-8 py-1 text-[10px] font-semibold ${typeConfig.badgeClass}`}>
                            <span>{typeConfig.icon}</span>
                            <span>{typeConfig.label}</span>
                          </span>
                        </div>
                        <span className="text-xs text-ink-light/50 dark:text-ink-dim">
                          {post.created_at ? new Date(post.created_at).toLocaleString() : "Recently shared"}
                        </span>
                      </div>
                    </div>

                    {matchedEvent && (
                      <div className="flex items-center gap-8">
                        <Link
                          to={`/events/${matchedEvent.id}`}
                          className="inline-flex items-center gap-1.5 rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-medium text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                          title="Open Event Hub & Transcript"
                        >
                          <span>🎪 {matchedEvent.name}</span>
                        </Link>

                        {eventIdFilter !== matchedEvent.id && (
                          <button
                            type="button"
                            onClick={() => {
                              searchParams.set("event_id", matchedEvent.id);
                              setSearchParams(searchParams);
                            }}
                            className="rounded-full border border-black/10 dark:border-white/10 px-8 py-2 text-[10px] text-ink-light/60 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark"
                            title="Filter feed by this event"
                          >
                            Filter
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {post.title && (
                    <h3 className="mt-13 font-display text-base sm:text-lg font-semibold text-ink-light dark:text-ink-dark group-hover:text-gold transition-colors">
                      {post.title}
                    </h3>
                  )}

                  <div className="mt-8 text-xs sm:text-sm text-ink-light/80 dark:text-ink-dim whitespace-pre-wrap leading-relaxed">
                    {post.body}
                  </div>

                  {/* Truthful Functional Actions Footer (No fake likes/engagement!) */}
                  <div className="mt-21 flex flex-wrap items-center justify-between gap-13 border-t border-black/5 dark:border-white/5 pt-13 text-xs text-ink-light/60 dark:text-ink-dim">
                    <div className="flex items-center gap-13">
                      <button
                        type="button"
                        onClick={() => handleCopy(`${post.title ? post.title + '\n\n' : ''}${post.body}`, post.id)}
                        className="inline-flex items-center gap-1 rounded-full border border-black/10 dark:border-white/10 bg-canvas-light/80 dark:bg-white/[0.03] px-13 py-4 text-xs font-medium text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark transition-colors"
                      >
                        <span>{isCopied ? "✓ Copied!" : "📋 Copy Text"}</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleStartRepurpose(post)}
                        className="inline-flex items-center gap-1 rounded-full border border-gold/30 bg-gold/10 px-13 py-4 text-xs font-medium text-gold dark:text-gold-soft hover:bg-gold/20 transition-all"
                      >
                        <span>✍️ Repurpose</span>
                      </button>

                      {post.event_id && (
                        <Link
                          to={`/events/${post.event_id}`}
                          className="inline-flex items-center gap-1 text-xs text-gold-soft hover:underline hidden sm:inline-flex"
                        >
                          <span>🎙️ View Event Hub</span>
                        </Link>
                      )}
                    </div>

                    <span className="text-[11px] text-ink-light/50 dark:text-ink-dim">
                      Status: <strong className="text-teal font-medium capitalize">{post.status.replace("_", " ")}</strong>
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
