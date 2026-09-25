import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createPost, type EventPublic } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

type CreatePostFormProps = {
  events?: EventPublic[];
  defaultEventId?: string;
  defaultTitle?: string;
  defaultBody?: string;
  onSuccess?: () => void;
  onCancel?: () => void;
};

export function CreatePostForm({
  events = [],
  defaultEventId = "",
  defaultTitle = "",
  defaultBody = "",
  onSuccess,
  onCancel,
}: CreatePostFormProps) {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const [title, setTitle] = useState(defaultTitle);
  const [body, setBody] = useState(defaultBody);
  const [eventId, setEventId] = useState(defaultEventId);
  const [postType, setPostType] = useState("discussion");

  useEffect(() => {
    if (defaultEventId) setEventId(defaultEventId);
  }, [defaultEventId]);

  useEffect(() => {
    if (defaultTitle) setTitle(defaultTitle);
  }, [defaultTitle]);

  useEffect(() => {
    if (defaultBody) setBody(defaultBody);
  }, [defaultBody]);

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
      className="space-y-13 rounded-card border border-gold/30 bg-surface-light p-21 shadow-xl backdrop-blur-xl dark:border-gold/20 dark:bg-surface-dark"
    >
      <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-13">
        <div>
          <h3 className="font-display text-base font-semibold text-ink-light dark:text-ink-dark flex items-center gap-2">
            <span>✍️</span> Share with the Community
          </h3>
          <p className="text-xs text-ink-light/60 dark:text-ink-dim mt-1">
            Publish your insights, questions, or highlights from attended sessions
          </p>
        </div>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="text-xs text-ink-light/50 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark transition-colors"
          >
            ✕ Close
          </button>
        )}
      </div>

      {mutation.error && (
        <div className="rounded-card border border-danger/30 bg-danger/15 p-13 text-xs font-medium text-danger">
          {(mutation.error as Error).message}
        </div>
      )}

      <div>
        <label className="mb-4 block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
          Post Title
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g., Key takeaways from the opening keynote..."
          required
          className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
        />
      </div>

      <div className="grid grid-cols-1 gap-13 sm:grid-cols-2">
        <div>
          <label className="mb-4 block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
            Tag Event (Optional)
          </label>
          <select
            value={eventId}
            onChange={(e) => setEventId(e.target.value)}
            className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-surface-dark px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
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
          <label className="mb-4 block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
            Category
          </label>
          <select
            value={postType}
            onChange={(e) => setPostType(e.target.value)}
            className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-surface-dark px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
          >
            <option value="discussion">💬 Discussion / Feedback</option>
            <option value="summary">📝 Session Summary</option>
            <option value="question">❓ Question for Speaker</option>
            <option value="announcement">📢 Announcement</option>
          </select>
        </div>
      </div>

      <div>
        <label className="mb-4 block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
          Post Content
        </label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
          placeholder="Share your thoughts, session notes, or ideas with the community..."
          required
          className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] p-13 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none leading-relaxed"
        />
      </div>

      <div className="flex items-center justify-between pt-8 border-t border-black/10 dark:border-white/10">
        <span className="text-[11px] text-ink-light/60 dark:text-ink-dim">
          Posting as: <strong className="text-ink-light dark:text-ink-dark">{user?.email}</strong>
        </span>

        <div className="flex items-center gap-8">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full border border-black/10 dark:border-white/10 px-13 py-8 text-xs font-medium text-ink-light/70 dark:text-ink-dim hover:text-ink-light dark:hover:text-ink-dark transition-colors"
            >
              Cancel
            </button>
          )}

          <button
            type="submit"
            disabled={mutation.isPending || !title.trim() || !body.trim()}
            className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/20 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:bg-gold/30 disabled:opacity-50 transition-all shadow-sm"
          >
            {mutation.isPending ? "Publishing..." : "Publish Post 🚀"}
          </button>
        </div>
      </div>
    </form>
  );
}
