import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { approveContent, downloadContent, patchContent, rejectContent, type ContentPublic } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { LinkedInCard } from "./renderers/LinkedInCard";
import { NewsletterPreview } from "./renderers/NewsletterPreview";
import { FlyerPreview } from "./renderers/FlyerPreview";
import { InstagramCard } from "./renderers/InstagramCard";
import { BlogArticle } from "./renderers/BlogArticle";
import { SummaryView } from "./renderers/SummaryView";

interface ContentStudioProps {
  token: string;
  jobId: string;
  pieces: ContentPublic[];
}

export function normalizeType(type: string): "summary" | "blog" | "linkedin" | "newsletter" | "instagram" | "flyer" {
  const t = (type || "").toLowerCase().replace(/[-_]/g, "");
  if (t.includes("summary")) return "summary";
  if (t.includes("blog")) return "blog";
  if (t.includes("linkedin")) return "linkedin";
  if (t.includes("newsletter")) return "newsletter";
  if (t.includes("insta") || t.includes("ig")) return "instagram";
  if (t.includes("flyer") || t.includes("poster")) return "flyer";
  return "summary";
}

const TYPE_CONFIG: Record<
  "summary" | "blog" | "linkedin" | "newsletter" | "instagram" | "flyer",
  { label: string; icon: string; desc: string }
> = {
  summary: { label: "Summary", icon: "📝", desc: "Executive briefing & key takeaways" },
  blog: { label: "Blog Post", icon: "📰", desc: "Long-form editorial article" },
  linkedin: { label: "LinkedIn", icon: "💼", desc: "Professional social feed post" },
  newsletter: { label: "Newsletter", icon: "📧", desc: "Email template with highlights" },
  instagram: { label: "Instagram", icon: "📸", desc: "Visual post caption with tags" },
  flyer: { label: "Flyer Poster", icon: "🎨", desc: "Visual recap poster card" },
};

export function ContentStudio({ token, jobId, pieces }: ContentStudioProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const targetDashboard = user?.role === "regular_user" ? "/user/dashboard" : "/organizer/dashboard";

  // Normalize pieces to ensure exactly 1 item per canonical format type
  const normalizedPieces = pieces.map((p) => ({
    ...p,
    normalizedType: normalizeType(p.type),
  }));

  const [activeType, setActiveType] = useState<"summary" | "blog" | "linkedin" | "newsletter" | "instagram" | "flyer">("summary");
  const [activeLang, setActiveLang] = useState<string>("en");

  // Editing state
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  // Available canonical types & languages (deduplicated)
  const availableTypes = Array.from(new Set(normalizedPieces.map((p) => p.normalizedType)));
  const availableLangs = Array.from(new Set(pieces.map((p) => p.language || "en")));

  // Set initial active type if default not present
  useEffect(() => {
    if (availableTypes.length > 0 && !availableTypes.includes(activeType)) {
      setActiveType(availableTypes[0]);
    }
  }, [availableTypes, activeType]);

  // Current active piece
  const currentPiece =
    normalizedPieces.find(
      (p) => p.normalizedType === activeType && (p.language === activeLang || (!p.language && activeLang === "en")),
    ) ||
    normalizedPieces.find((p) => p.normalizedType === activeType) ||
    normalizedPieces[0];

  // Sync edit state when active piece changes
  useEffect(() => {
    if (currentPiece) {
      setEditTitle(currentPiece.title || "");
      setEditBody(currentPiece.body || "");
      setIsEditing(false);
    }
  }, [currentPiece]);

  function notify(msg: string) {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 3000);
  }

  // Mutations
  const approveMutation = useMutation({
    mutationFn: (id: string) => approveContent(token, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content", jobId] });
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      notify("✓ Content marked as Approved!");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectContent(token, id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content", jobId] });
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      setShowRejectModal(false);
      setRejectReason("");
      notify("Content rejected.");
    },
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      patchContent(token, currentPiece!.id, {
        title: editTitle,
        body: editBody,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content", jobId] });
      setIsEditing(false);
      notify("✓ Draft changes saved!");
    },
  });

  if (!pieces || pieces.length === 0) {
    return (
      <div className="rounded-card border border-dashed border-primary/30 p-34 text-center">
        <p className="text-sm opacity-60">Content is being generated by the pipeline...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-21">
      {/* Toast Notification */}
      {feedbackMsg && (
        <div className="fixed bottom-21 right-21 z-50 rounded-card bg-primary px-21 py-13 text-sm font-medium text-white shadow-xl">
          {feedbackMsg}
        </div>
      )}

      {/* Dashboard Return & Review Progress Bar */}
      <div className="flex flex-wrap items-center justify-between gap-13 rounded-card border border-gold/30 bg-gold/10 p-13">
        <div className="flex items-center gap-10">
          <span className="text-xl">✅</span>
          <div>
            <p className="text-xs font-bold text-gold-soft">Human Review Gate Active</p>
            <p className="text-[11px] text-ink-dim">
              Approve, reject, or edit generated content before publishing.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => navigate(targetDashboard)}
          className="inline-flex items-center gap-2 rounded-full border border-gold/50 bg-gold/20 px-21 py-8 text-xs font-bold text-gold-soft hover:bg-gold/30 transition-all shadow"
        >
          <span>← Done with Review / Return to Dashboard</span>
        </button>
      </div>

      {/* Content Type Tabs (Deduplicated 6 Canonical Formats) */}
      <div className="flex flex-wrap items-center justify-between gap-13 border-b border-black/10 pb-13 dark:border-white/10">
        <div className="flex flex-wrap gap-8">
          {availableTypes.map((type) => {
            const config = TYPE_CONFIG[type] || { label: type, icon: "📄", desc: "" };
            const isActive = activeType === type;
            const piece = normalizedPieces.find((p) => p.normalizedType === type);
            const isApproved = piece?.status === "approved";
            const isPending = piece?.status === "pending_review";

            return (
              <button
                key={type}
                type="button"
                onClick={() => setActiveType(type)}
                className={`flex items-center gap-8 rounded-card px-13 py-8 text-sm font-medium transition-all ${
                  isActive
                    ? "bg-primary text-white shadow-md"
                    : "bg-surface-light text-ink-light hover:bg-black/5 dark:bg-surface-dark dark:text-ink-dark dark:hover:bg-white/5"
                }`}
              >
                <span>{config.icon}</span>
                <span>{config.label}</span>
                {isApproved && <span className="text-xs text-success">✓</span>}
                {isPending && <span className="h-2 w-2 rounded-full bg-accent animate-pulse"></span>}
              </button>
            );
          })}
        </div>

        {/* Language Tabs if multiple */}
        {availableLangs.length > 1 && (
          <div className="flex items-center gap-4 text-xs">
            <span className="opacity-60">Lang:</span>
            {availableLangs.map((lang) => (
              <button
                key={lang}
                type="button"
                onClick={() => setActiveLang(lang)}
                className={`rounded px-8 py-4 font-semibold uppercase ${
                  activeLang === lang
                    ? "bg-accent text-canvas-dark"
                    : "bg-surface-light opacity-70 dark:bg-surface-dark"
                }`}
              >
                {lang}
              </button>
            ))}
          </div>
        )}
      </div>

      {currentPiece && (
        <>
          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-13 rounded-card bg-surface-light p-13 dark:bg-surface-dark">
            <div className="flex items-center gap-13">
              <span
                className={`rounded-full px-13 py-4 text-xs font-semibold uppercase tracking-wider ${
                  currentPiece.status === "approved"
                    ? "bg-success/15 text-success"
                    : currentPiece.status === "rejected"
                    ? "bg-danger/15 text-danger"
                    : "bg-accent/15 text-accent"
                }`}
              >
                Status: {currentPiece.status.replace("_", " ")}
              </span>

              {isEditing ? (
                <span className="text-xs text-warning">● Editing Draft</span>
              ) : (
                <span className="text-xs opacity-60">v{currentPiece.version || 1}</span>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-8">
              {/* Edit / View Toggle */}
              {isEditing ? (
                <>
                  <button
                    type="button"
                    onClick={() => saveMutation.mutate()}
                    disabled={saveMutation.isPending}
                    className="rounded-card bg-accent px-13 py-8 text-xs font-semibold text-canvas-dark hover:opacity-90"
                  >
                    {saveMutation.isPending ? "Saving..." : "💾 Save Changes"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsEditing(false)}
                    className="rounded-card bg-black/5 px-13 py-8 text-xs font-medium dark:bg-white/5"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsEditing(true)}
                  className="rounded-card border border-black/10 bg-canvas-light px-13 py-8 text-xs font-medium hover:border-primary dark:border-white/10 dark:bg-canvas-dark"
                >
                  ✏️ Edit Copy
                </button>
              )}

              {/* Download Buttons */}
              <button
                type="button"
                onClick={() =>
                  downloadContent(
                    token,
                    currentPiece.id,
                    currentPiece.normalizedType === "flyer" ? "json" : "markdown",
                    `${currentPiece.normalizedType}_recap`,
                  )
                }
                className="rounded-card border border-black/10 bg-canvas-light px-13 py-8 text-xs font-medium hover:border-primary dark:border-white/10 dark:bg-canvas-dark"
              >
                📥 Download
              </button>

              {/* Human Approval Gate */}
              {currentPiece.status === "pending_review" && (
                <>
                  <button
                    type="button"
                    onClick={() => approveMutation.mutate(currentPiece.id)}
                    disabled={approveMutation.isPending}
                    className="rounded-card bg-success px-13 py-8 text-xs font-semibold text-white hover:opacity-90 shadow"
                  >
                    {approveMutation.isPending ? "Approving..." : "✓ Approve"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRejectModal(true)}
                    className="rounded-card bg-danger/20 px-13 py-8 text-xs font-semibold text-danger hover:bg-danger/30"
                  >
                    ✕ Reject
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Grounding / Moderation Alerts */}
          {currentPiece.grounding && currentPiece.grounding.pass === false && (
            <div className="rounded-card border border-warning/30 bg-warning/10 p-13 text-xs text-warning">
              <p className="font-semibold">⚠️ Grounding Alert: Potential unsupported claim detected</p>
              <ul className="mt-4 list-disc pl-21 opacity-90">
                {(currentPiece.grounding.unsupported || []).slice(0, 3).map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {currentPiece.moderation && currentPiece.moderation.pass === false && (
            <div className="rounded-card border border-danger/30 bg-danger/10 p-13 text-xs text-danger">
              ⚠️ Moderation Flag: Output triggered keyword review:{" "}
              {(currentPiece.moderation.hits || []).join(", ")}
            </div>
          )}

          {/* Main Display Area: Editor or Rich Previewer */}
          <div className="flex justify-center">
            {isEditing ? (
              <div className="w-full max-w-3xl rounded-card border border-primary/30 bg-surface-light p-21 shadow-lg dark:bg-surface-dark">
                <label className="block text-xs font-semibold uppercase opacity-60">Title / Headline</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="mt-4 w-full rounded-card border border-black/10 bg-canvas-light px-13 py-8 text-sm dark:border-white/10 dark:bg-canvas-dark"
                  placeholder="Enter title..."
                />

                <label className="mt-21 block text-xs font-semibold uppercase opacity-60">Content Body</label>
                <textarea
                  rows={14}
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  className="mt-4 w-full rounded-card border border-black/10 bg-canvas-light p-13 text-sm font-sans leading-relaxed dark:border-white/10 dark:bg-canvas-dark"
                  placeholder="Enter content..."
                />

                <div className="mt-13 flex justify-between text-xs opacity-60">
                  <span>Words: {editBody.trim() ? editBody.trim().split(/\s+/).length : 0}</span>
                  <span>Characters: {editBody.length}</span>
                </div>
              </div>
            ) : (
              /* Specialized Rich Renderer */
              <>
                {currentPiece.normalizedType === "linkedin" && (
                  <LinkedInCard
                    title={currentPiece.title}
                    body={currentPiece.body}
                    onCopy={() => notify("✓ Copied to clipboard!")}
                  />
                )}
                {currentPiece.normalizedType === "newsletter" && (
                  <NewsletterPreview
                    title={currentPiece.title}
                    body={currentPiece.body}
                    onCopy={() => notify("✓ Copied to clipboard!")}
                  />
                )}
                {currentPiece.normalizedType === "flyer" && (
                  <FlyerPreview
                    title={currentPiece.title}
                    body={currentPiece.body}
                    structured={currentPiece.structured}
                    onCopy={() => notify("✓ Copied to clipboard!")}
                  />
                )}
                {currentPiece.normalizedType === "instagram" && (
                  <InstagramCard
                    title={currentPiece.title}
                    body={currentPiece.body}
                    onCopy={() => notify("✓ Copied to clipboard!")}
                  />
                )}
                {currentPiece.normalizedType === "blog" && (
                  <BlogArticle
                    title={currentPiece.title}
                    body={currentPiece.body}
                    onCopy={() => notify("✓ Copied to clipboard!")}
                  />
                )}
                {currentPiece.normalizedType === "summary" && (
                  <SummaryView
                    title={currentPiece.title}
                    body={currentPiece.body}
                    onCopy={() => notify("✓ Copied to clipboard!")}
                  />
                )}
              </>
            )}
          </div>
        </>
      )}

      {/* Reject Reason Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-21 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-card border border-danger/40 bg-surface-light p-21 shadow-2xl dark:bg-surface-dark">
            <h3 className="font-display text-lg text-ink-light dark:text-ink-dark">Reject Draft</h3>
            <p className="mt-4 text-xs opacity-60">
              Provide feedback for why this content is being rejected:
            </p>

            <textarea
              rows={4}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g., Tone is too informal, missed key metrics mentioned by speaker..."
              className="mt-13 w-full rounded-card border border-black/10 bg-canvas-light p-13 text-sm dark:border-white/10 dark:bg-canvas-dark"
            />

            <div className="mt-21 flex justify-end gap-13">
              <button
                type="button"
                onClick={() => setShowRejectModal(false)}
                className="rounded-card px-13 py-8 text-xs font-medium opacity-60 hover:opacity-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  rejectMutation.mutate({
                    id: currentPiece!.id,
                    reason: rejectReason || "Rejected by user",
                  })
                }
                disabled={rejectMutation.isPending}
                className="rounded-card bg-danger px-21 py-8 text-xs font-semibold text-white shadow hover:opacity-90"
              >
                {rejectMutation.isPending ? "Rejecting..." : "Confirm Rejection"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
