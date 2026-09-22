import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createPost, type EventPublic } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

type CreatePostFormProps = {
  events?: EventPublic[];
  defaultEventId?: string;
  onSuccess?: () => void;
  onCancel?: () => void;
};

export function CreatePostForm({
  events = [],
  defaultEventId = "",
  onSuccess,
  onCancel,
}: CreatePostFormProps) {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [eventId, setEventId] = useState(defaultEventId);
  const [postType, setPostType] = useState("discussion");

  const mutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("Not authenticated");
      return createPost(token, {
        title,
        body,
        type: postType,
        event_id: eventId || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["community-content"] });
      setTitle("");
      setBody("");
      onSuccess?.();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) return;
    mutation.mutate();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl backdrop-blur-xl"
    >
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <span>✍️</span> Share with the Community
          </h3>
          <p className="text-xs text-slate-400">
            Publish your insights, questions, or highlights from attended sessions
          </p>
        </div>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="text-xs text-slate-400 hover:text-white"
          >
            ✕ Close
          </button>
        )}
      </div>

      {mutation.error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
          {(mutation.error as Error).message}
        </div>
      )}

      <div>
        <label className="mb-1 block text-xs font-semibold text-slate-300">Post Title</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g., Key takeaways from the opening keynote..."
          required
          className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-semibold text-slate-300">Tag Event (Optional)</label>
          <select
            value={eventId}
            onChange={(e) => setEventId(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-amber-500/50 focus:outline-none"
          >
            <option value="">General Community Discussion</option>
            {events.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.name} ({ev.type})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-xs font-semibold text-slate-300">Category</label>
          <select
            value={postType}
            onChange={(e) => setPostType(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-amber-500/50 focus:outline-none"
          >
            <option value="discussion">💬 Discussion / Feedback</option>
            <option value="summary">📝 Session Summary</option>
            <option value="question">❓ Question for Speaker</option>
            <option value="announcement">📢 Announcement</option>
          </select>
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-semibold text-slate-300">Post Content</label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
          placeholder="Share your thoughts, session notes, or ideas with the community..."
          required
          className="w-full rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
        />
      </div>

      <div className="flex items-center justify-between pt-2">
        <span className="text-[11px] text-slate-500">
          Posting as: <strong className="text-slate-300">{user?.email}</strong>
        </span>

        <div className="flex items-center gap-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-white/5"
            >
              Cancel
            </button>
          )}

          <button
            type="submit"
            disabled={mutation.isPending || !title.trim() || !body.trim()}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20 transition-all hover:scale-105 hover:from-amber-400 hover:to-orange-500 disabled:opacity-50"
          >
            {mutation.isPending ? "Publishing..." : "Publish Post 🚀"}
          </button>
        </div>
      </div>
    </form>
  );
}
