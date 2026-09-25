import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  getEvent,
  listCommunityContent,
  listJobs,
  getTranscript,
  patchContent,
  type ContentPublic,
} from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { EventChatWidget } from "@/components/chat/EventChatWidget";
import { GoldenShell } from "@/layouts/GoldenShell";

export function EventDetailPage() {
  const { eventId = "" } = useParams<{ eventId: string }>();
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"content" | "transcript">("content");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [transcriptSearch, setTranscriptSearch] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Modals
  const [viewingPost, setViewingPost] = useState<ContentPublic | null>(null);
  const [editingPost, setEditingPost] = useState<ContentPublic | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");

  // Fetch Event Details
  const eventQuery = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => (token && eventId ? getEvent(token, eventId) : null),
    enabled: !!token && !!eventId,
  });

  // Fetch all community posts & generated posts for this event
  const contentQuery = useQuery({
    queryKey: ["event-content", eventId],
    queryFn: () => (token && eventId ? listCommunityContent(token, { event_id: eventId }) : []),
    enabled: !!token && !!eventId,
  });

  // Also fetch any jobs associated or latest job transcript for rich transcript view
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => (token ? listJobs(token) : []),
    enabled: !!token,
  });

  // Find associated job for this event (or fallback to latest)
  const associatedJob =
    jobsQuery.data?.find((j) => j.event_id === eventId) || jobsQuery.data?.[0];

  const transcriptQuery = useQuery({
    queryKey: ["transcript", associatedJob?.id],
    queryFn: () => (token && associatedJob?.id ? getTranscript(token, associatedJob.id) : null),
    enabled: !!token && !!associatedJob?.id,
  });

  // Mutation to update/edit post
  const updatePostMutation = useMutation({
    mutationFn: async ({ id, title, body }: { id: string; title: string; body: string }) => {
      if (!token) throw new Error("Not authenticated");
      return patchContent(token, id, { title, body });
    },
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["event-content", eventId] });
      setEditingPost(null);
      if (viewingPost && viewingPost.id === updated.id) {
        setViewingPost(updated);
      }
      showToast("✓ Post updated successfully!");
    },
  });

  const event = eventQuery.data;
  const posts: ContentPublic[] = contentQuery.data || [];

  const filteredPosts =
    selectedType === "all" ? posts : posts.filter((p) => p.type === selectedType);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    showToast("✓ Copied to clipboard!");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const startEditing = (post: ContentPublic) => {
    setEditingPost(post);
    setEditTitle(post.title || "");
    setEditBody(post.body || "");
  };

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPost) return;
    updatePostMutation.mutate({
      id: editingPost.id,
      title: editTitle,
      body: editBody,
    });
  };

  const TYPE_BADGES: Record<string, { label: string; icon: string; color: string }> = {
    linkedin: {
      label: "LinkedIn Post",
      icon: "💼",
      color: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    },
    instagram: {
      label: "Instagram Carousel",
      icon: "📸",
      color: "bg-pink-500/20 text-pink-300 border-pink-500/30",
    },
    newsletter: {
      label: "Email Newsletter",
      icon: "📧",
      color: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    },
    blog: {
      label: "Blog Article",
      icon: "📝",
      color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    },
    summary: {
      label: "Executive Summary",
      icon: "📊",
      color: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    },
    flyer: {
      label: "Event Flyer",
      icon: "🎨",
      color: "bg-orange-500/20 text-orange-300 border-orange-500/30",
    },
  };

  const fullTranscriptText =
    transcriptQuery.data?.full_text ||
    "No audio transcript recorded for this session yet. Upload a media recording in the Dashboard to index speech-to-text.";

  return (
    <GoldenShell>
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Toast Notification */}
        {toastMessage && (
          <div className="fixed bottom-6 right-6 z-50 rounded-2xl border border-emerald-500/40 bg-slate-900/90 px-5 py-3 text-xs font-bold text-emerald-300 shadow-2xl backdrop-blur-xl animate-bounce">
            {toastMessage}
          </div>
        )}

        {/* Navigation Breadcrumb */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              to="/catalog/all"
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs font-semibold text-slate-300 hover:border-gold/30 hover:bg-gold/10 hover:text-gold transition-colors"
            >
              ← All Catalogs
            </Link>
            <span className="text-slate-600">/</span>
            <span className="text-xs text-gold font-semibold uppercase tracking-wider">
              {event?.type || "Event"} Hub
            </span>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to={`/organizer/dashboard?event_id=${eventId}`}
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 px-4 py-2 text-xs font-bold text-slate-950 shadow-lg shadow-amber-500/20 hover:scale-105 transition-all"
            >
              <span>🎙️ Upload Recording</span>
            </Link>
            <Link
              to="/community"
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-slate-200 hover:border-gold/30 hover:bg-gold/10 hover:text-gold transition-all"
            >
              <span>💬 Community Feed</span>
            </Link>
            <Link
              to={user?.role === "regular_user" ? "/user/dashboard" : "/organizer/dashboard"}
              className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-slate-300 hover:border-gold/30 hover:text-gold transition-all"
            >
              Dashboard
            </Link>
          </div>
        </div>

        {/* Hero Event Banner */}
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-900/90 to-slate-950 p-8 shadow-2xl backdrop-blur-xl">
          <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent blur-2xl" />

          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div>
              <div className="flex flex-wrap items-center gap-2.5 mb-3">
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/20 px-3 py-1 text-xs font-bold text-amber-300">
                  <span>🎪</span>
                  <span className="capitalize">{event?.type || "Event"}</span>
                </span>
                <span className="text-xs text-slate-400">
                  📅{" "}
                  {event?.date
                    ? new Date(event.date).toLocaleDateString(undefined, { dateStyle: "full" })
                    : "Scheduled Date"}
                </span>
                {event?.location && (
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    📍 {event.location}
                  </span>
                )}
              </div>

              <h1 className="text-2xl md:text-4xl font-black text-white tracking-tight">
                {event?.name || "Event Overview"}
              </h1>

              {event?.topic && (
                <p className="mt-2 text-sm text-slate-300 flex items-center gap-2">
                  <span className="text-amber-400">💡 Theme:</span> {event.topic}
                </p>
              )}

              <div className="mt-4 flex items-center gap-2 text-xs text-slate-400">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-500/20 font-bold text-amber-300 text-xs">
                  {event?.organizer_name ? event.organizer_name[0].toUpperCase() : "O"}
                </span>
                <span>
                  Organized by{" "}
                  <strong className="text-white font-semibold">
                    {event?.organizer_name || "Community Organizer"}
                  </strong>
                </span>
              </div>
            </div>

            {/* Quick Stats */}
            <div className="flex flex-wrap md:flex-col gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-center min-w-[120px]">
                <span className="block text-2xl font-black text-amber-400">{posts.length}</span>
                <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">
                  All Posts
                </span>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-center min-w-[120px]">
                <span className="block text-2xl font-black text-emerald-400">
                  {transcriptQuery.data?.avg_confidence
                    ? `${Math.round(transcriptQuery.data.avg_confidence * 100)}%`
                    : "100%"}
                </span>
                <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">
                  Grounding Score
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Switching: Generated Content vs Full Transcript */}
        <div className="mt-8 flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setActiveTab("content")}
              className={`rounded-xl px-5 py-2.5 text-xs font-bold transition-all ${
                activeTab === "content"
                  ? "bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-lg shadow-orange-500/20"
                  : "border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              📄 Generated Posts &amp; Reflections ({posts.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("transcript")}
              className={`rounded-xl px-5 py-2.5 text-xs font-bold transition-all ${
                activeTab === "transcript"
                  ? "bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-lg shadow-orange-500/20"
                  : "border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              🎙️ Full Searchable Transcript
            </button>
          </div>

          {activeTab === "content" && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 hidden sm:inline">Filter format:</span>
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="rounded-xl border border-white/10 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 focus:border-amber-500/50 focus:outline-none"
              >
                <option value="all">All Formats ({posts.length})</option>
                <option value="linkedin">💼 LinkedIn</option>
                <option value="instagram">📸 Instagram</option>
                <option value="newsletter">📧 Newsletter</option>
                <option value="blog">📝 Blog</option>
                <option value="summary">📊 Summary</option>
                <option value="flyer">🎨 Flyer</option>
              </select>
            </div>
          )}
        </div>

        {/* Tab 1: Generated Content Feed */}
        {activeTab === "content" && (
          <div className="mt-6 space-y-6">
            {filteredPosts.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-white/10 bg-slate-900/40 p-12 text-center">
                <span className="text-4xl">📝</span>
                <h3 className="mt-3 text-lg font-bold text-white">No posts generated for this event yet</h3>
                <p className="mt-1 text-xs text-slate-400 max-w-sm mx-auto">
                  Upload an event recording or write reflections to generate all 6 publish-ready multi-agent posts.
                </p>
                <div className="mt-5 flex items-center justify-center gap-3">
                  <Link
                    to={`/organizer/dashboard?event_id=${eventId}`}
                    className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20"
                  >
                    <span>🎙️ Upload Recording</span>
                  </Link>
                  <Link
                    to="/community"
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-white/10"
                  >
                    Write Reflection
                  </Link>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {filteredPosts.map((post) => {
                  const badge = TYPE_BADGES[post.type] || {
                    label: post.type,
                    icon: "📌",
                    color: "bg-slate-500/20 text-slate-300 border-slate-500/30",
                  };
                  const isCopied = copiedId === post.id;

                  return (
                    <div
                      key={post.id}
                      className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-white/10 bg-slate-900/80 p-6 shadow-xl backdrop-blur-xl transition-all hover:border-white/20"
                    >
                      <div>
                        <div className="flex items-center justify-between border-b border-white/5 pb-3 mb-4">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${badge.color}`}
                          >
                            <span>{badge.icon}</span>
                            <span>{badge.label}</span>
                          </span>

                          <div className="flex items-center gap-2 text-xs text-slate-400">
                            <span>
                              Author: <strong className="text-slate-200">{post.author_name || "Speaker"}</strong>
                            </span>
                          </div>
                        </div>

                        {post.title && (
                          <h3
                            onClick={() => setViewingPost(post)}
                            className="text-base font-bold text-white group-hover:text-amber-300 transition-colors cursor-pointer"
                          >
                            {post.title}
                          </h3>
                        )}

                        <div
                          onClick={() => setViewingPost(post)}
                          className="mt-3 text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto rounded-xl bg-black/20 p-4 font-sans cursor-pointer hover:bg-black/30 transition-colors"
                          title="Click to view full post"
                        >
                          {post.body}
                        </div>
                      </div>

                      {/* Post Actions */}
                      <div className="mt-5 flex flex-wrap items-center justify-between gap-2 pt-4 border-t border-white/5">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setViewingPost(post)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-white/10 hover:text-white transition-colors"
                          >
                            <span>🔍 View</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => startEditing(post)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 transition-colors"
                          >
                            <span>✏️ Edit / Update</span>
                          </button>
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              handleCopy(`${post.title ? post.title + "\n\n" : ""}${post.body}`, post.id)
                            }
                            className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-white/10 hover:text-white transition-colors"
                          >
                            {isCopied ? "✓ Copied!" : "📋 Copy"}
                          </button>

                          <Link
                            to={`/community?repurpose=${post.id}&event_id=${eventId}`}
                            className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-amber-500/20 to-orange-500/20 border border-amber-500/30 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/30 transition-all"
                          >
                            <span>✍️ Repurpose</span>
                          </Link>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Searchable Full Audio Transcript */}
        {activeTab === "transcript" && (
          <div className="mt-6 rounded-2xl border border-white/10 bg-slate-900/80 p-6 shadow-xl backdrop-blur-xl">
            <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span>🎙️</span> Grounded Speech-to-Text Transcription
                </h3>
                <p className="text-xs text-slate-400">
                  Full text indexed by VideoDB and verified with confidence scoring.
                </p>
              </div>

              <div className="relative max-w-xs w-full">
                <input
                  type="text"
                  value={transcriptSearch}
                  onChange={(e) => setTranscriptSearch(e.target.value)}
                  placeholder="Search transcript text..."
                  className="w-full rounded-xl border border-white/10 bg-white/5 pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
                />
                <span className="absolute inset-y-0 left-3 flex items-center text-xs text-slate-400">
                  🔍
                </span>
              </div>
            </div>

            <div className="max-h-[500px] overflow-y-auto rounded-xl bg-black/30 p-6 font-mono text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
              {fullTranscriptText}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* MODAL 1: FULL POST VIEWER */}
        {/* ========================================================================= */}
        {viewingPost && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
            <div className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-white/15 bg-slate-900 p-6 sm:p-8 shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-amber-500/20 border border-amber-500/30 px-3 py-1 text-xs font-bold text-amber-300 uppercase">
                    {viewingPost.type}
                  </span>
                  <span className="text-xs text-slate-400">
                    Author: {viewingPost.author_name || "Speaker"}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => setViewingPost(null)}
                  className="rounded-full p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
                >
                  ✕
                </button>
              </div>

              <div className="my-6 max-h-[60vh] overflow-y-auto pr-2 space-y-4">
                {viewingPost.title && (
                  <h2 className="text-xl font-bold text-white tracking-tight">
                    {viewingPost.title}
                  </h2>
                )}
                <div className="rounded-2xl bg-black/40 p-5 text-sm text-slate-200 leading-relaxed whitespace-pre-wrap font-sans border border-white/5">
                  {viewingPost.body}
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    const p = viewingPost;
                    setViewingPost(null);
                    startEditing(p);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs font-bold text-amber-300 hover:bg-amber-500/20"
                >
                  <span>✏️ Edit This Post</span>
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      handleCopy(
                        `${viewingPost.title ? viewingPost.title + "\n\n" : ""}${viewingPost.body}`,
                        viewingPost.id,
                      )
                    }
                    className="inline-flex items-center gap-1.5 rounded-xl bg-white/10 px-4 py-2 text-xs font-semibold text-white hover:bg-white/20"
                  >
                    <span>📋 Copy Full Post</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewingPost(null)}
                    className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-white/5"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* MODAL 2: EDIT / UPDATE POST MODAL */}
        {/* ========================================================================= */}
        {editingPost && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
            <div className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-amber-500/30 bg-slate-900 p-6 sm:p-8 shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>✏️</span> Edit &amp; Update Post
                  </h3>
                  <p className="text-xs text-slate-400">
                    Format: <span className="text-amber-300 uppercase font-semibold">{editingPost.type}</span> • Modify title and body copy
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setEditingPost(null)}
                  className="rounded-full p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
                >
                  ✕
                </button>
              </div>

              {updatePostMutation.error && (
                <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
                  {(updatePostMutation.error as Error).message}
                </div>
              )}

              <form onSubmit={handleSaveEdit} className="mt-6 space-y-4">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-300">
                    Post Title
                  </label>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="Enter engaging title..."
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-slate-300">
                      Post Body (Markdown Supported)
                    </label>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {editBody.length} chars
                    </span>
                  </div>
                  <textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    rows={10}
                    required
                    placeholder="Write or edit post content..."
                    className="w-full rounded-xl border border-white/10 bg-white/5 p-4 font-mono text-xs text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/20 leading-relaxed"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-4 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setEditingPost(null)}
                    className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-white/5"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updatePostMutation.isPending || !editBody.trim()}
                    className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20 hover:scale-105 transition-all disabled:opacity-50"
                  >
                    {updatePostMutation.isPending ? "Saving Changes..." : "💾 Save & Update Post"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Member 4 Attendee Q&A Assistant */}
        <EventChatWidget eventId={eventId} eventName={event?.name} />
      </div>
    </GoldenShell>
  );
}
