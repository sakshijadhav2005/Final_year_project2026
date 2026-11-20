import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  approveContent,
  downloadContent,
  patchContent,
  rejectContent,
  type BackTranslationCheck,
  type ContentPublic,
} from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { LinkedInCard } from "./renderers/LinkedInCard";
import { NewsletterPreview } from "./renderers/NewsletterPreview";
import { FlyerPreview } from "./renderers/FlyerPreview";
import { InstagramCard } from "./renderers/InstagramCard";
import { XCard } from "./renderers/XCard";
import { BlogArticle } from "./renderers/BlogArticle";
import { SummaryView } from "./renderers/SummaryView";
import { SourcesPanel } from "./SourcesPanel";
import { PublishSection } from "@/components/social/PublishPanel";

/** Result of translating a draft back into English and comparing it with the original. */
function BackTranslationNotice({ check }: { check: BackTranslationCheck }) {
  const pct = check.score == null ? null : Math.round(check.score * 100);
  if (check.status === "pass") {
    return (
      <div className="text-xs text-ink-dim">
        <p>✓ Back-translation check: {pct}% of the English content words came back</p>
        {check.back_text && (
          <details className="mt-[4px]">
            <summary className="cursor-pointer">Show the back-translation</summary>
            <p className="mt-[4px] whitespace-pre-wrap opacity-80">{check.back_text}</p>
          </details>
        )}
      </div>
    );
  }
  const message =
    check.status === "low_agreement"
      ? `Back-translation check: only ${pct}% of the English content words came back (minimum ${Math.round(
          (check.min_score ?? 0) * 100,
        )}%). Meaning may have drifted; compare before approving.`
      : check.status === "untranslated"
        ? "Back-translation check: this language could not be translated, so the English text is shown."
        : "Back-translation check could not run for this draft; review the translation by hand.";
  return (
    <div className="rounded-card border border-warning/30 bg-warning/10 p-13 text-xs text-warning">
      <p className="font-semibold">⚠️ {message}</p>
      {check.back_text && (
        <details className="mt-[4px]">
          <summary className="cursor-pointer">Show the back-translation</summary>
          <p className="mt-[4px] whitespace-pre-wrap opacity-90">{check.back_text}</p>
        </details>
      )}
    </div>
  );
}

const REVIEWED_STATUSES = ["approved", "rejected", "ready_to_publish"];

interface ContentStudioProps {
  token: string;
  jobId: string;
  pieces: ContentPublic[];
}

type StudioType = "summary" | "blog" | "linkedin" | "newsletter" | "instagram" | "flyer" | "x";

function normalizeType(type: string): StudioType {
  const t = (type || "").toLowerCase().replace(/[-_]/g, "");
  if (t.includes("summary")) return "summary";
  if (t.includes("blog")) return "blog";
  if (["x", "xpost", "tweet", "twitter", "twitterpost"].includes(t)) return "x";
  if (t.includes("linkedin")) return "linkedin";
  if (t.includes("newsletter")) return "newsletter";
  if (t.includes("insta") || t.includes("ig")) return "instagram";
  if (t.includes("flyer") || t.includes("poster")) return "flyer";
  return "summary";
}

const TYPE_CONFIG: Record<StudioType, { label: string; icon: string; desc: string }> = {
  summary: { label: "Summary", icon: "📝", desc: "Executive briefing & key takeaways" },
  blog: { label: "Blog Post", icon: "📰", desc: "Long-form editorial article" },
  linkedin: { label: "LinkedIn", icon: "💼", desc: "Professional social feed post" },
  newsletter: { label: "Newsletter", icon: "📧", desc: "Email template with highlights" },
  instagram: { label: "Instagram", icon: "📸", desc: "Visual post caption with tags" },
  flyer: { label: "Flyer Poster", icon: "🎨", desc: "Visual recap poster card" },
  x: { label: "X", icon: "𝕏", desc: "One post within 280 characters" },
};

export function ContentStudio({ token, jobId, pieces }: ContentStudioProps) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);

  const targetDashboard = user?.role === "regular_user" ? "/user/dashboard" : "/organizer/dashboard";

  // Normalize pieces to ensure exactly 1 item per canonical format type.
  // Memoised: a new array every render gave currentPiece a new identity every
  // render, so the sync effect below reset isEditing and closed the editor at once.
  const normalizedPieces = useMemo(
    () => pieces.map((p) => ({ ...p, normalizedType: normalizeType(p.type) })),
    [pieces],
  );

  const [activeType, setActiveType] = useState<StudioType>("summary");
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

  // Session review progress: every draft in every language must be approved or rejected.
  const reviewedCount = normalizedPieces.filter((p) => REVIEWED_STATUSES.includes(p.status)).length;
  const totalCount = normalizedPieces.length;
  const pieceFor = (type: StudioType, lang: string) =>
    normalizedPieces.find((p) => p.normalizedType === type && (p.language || "en") === lang);
  // Unreviewed drafts in tab order (format, then language), starting after the open one.
  const reviewOrder = availableTypes.flatMap((type) =>
    availableLangs.map((lang) => ({ type, lang, piece: pieceFor(type, lang) })),
  );
  const openIndex = reviewOrder.findIndex((o) => o.piece?.id === currentPiece?.id);
  const nextUnreviewed = [...reviewOrder.slice(openIndex + 1), ...reviewOrder.slice(0, openIndex + 1)].find(
    (o) => o.piece && o.piece.id !== currentPiece?.id && o.piece.status === "pending_review",
  );
  function openNextUnreviewed() {
    if (!nextUnreviewed) return;
    setActiveType(nextUnreviewed.type);
    setActiveLang(nextUnreviewed.lang);
  }

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
      <div className="rounded-card border border-dashed border-white/20 p-34 text-center">
        <p className="text-sm opacity-60">Content is being generated by the pipeline…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-21">
      {/* Toast Notification */}
      {feedbackMsg && (
        <div role="status" className="fixed bottom-21 right-21 z-50 rounded-card border border-white/[0.12] bg-surface-raised px-21 py-13 text-sm font-medium text-ink">
          {feedbackMsg}
        </div>
      )}

      {/* Dashboard Return & Review Progress Bar */}
      <div className="flex flex-wrap items-center justify-between gap-13">
        <div className="min-w-0 flex-1 space-y-8">
          <div className="flex flex-wrap items-baseline gap-x-13 gap-y-[4px]">
            <p className="text-sm font-semibold text-ink">
              {reviewedCount} of {totalCount} drafts reviewed
            </p>
            <p className="text-xs text-ink-dim">Nothing is published until you approve it.</p>
          </div>
          <div
            className="h-[6px] max-w-md overflow-hidden rounded-full bg-white/[0.08]"
            role="progressbar"
            aria-label="Drafts reviewed"
            aria-valuemin={0}
            aria-valuemax={totalCount}
            aria-valuenow={reviewedCount}
          >
            <div
              className="h-full rounded-full bg-success transition-[width] duration-300 ease-out"
              style={{ width: `${totalCount ? (reviewedCount / totalCount) * 100 : 0}%` }}
            />
          </div>
        </div>

        {nextUnreviewed && (
          <button
            type="button"
            onClick={openNextUnreviewed}
            className="inline-flex items-center gap-8 rounded-full border border-white/[0.12] px-21 py-8 text-sm text-ink transition-colors hover:border-amber-400/50"
          >
            Next unreviewed
          </button>
        )}

        <Link
          to={targetDashboard}
          className="inline-flex items-center gap-8 rounded-full border border-white/[0.12] px-21 py-8 text-sm text-ink transition-colors hover:border-amber-400/50"
        >
          <span>Back to dashboard</span>
        </Link>
      </div>

      {/* Content Type Tabs (Deduplicated 6 Canonical Formats) */}
      <div className="flex flex-wrap items-center justify-between gap-13 border-b border-white/[0.08] pb-13">
        <div className="neu-inset flex flex-wrap gap-[4px] rounded-panel p-[5px]">
          {availableTypes.map((type) => {
            const config = TYPE_CONFIG[type] || { label: type, icon: "📄", desc: "" };
            const isActive = activeType === type;
            const piece = pieceFor(type, activeLang) || normalizedPieces.find((p) => p.normalizedType === type);
            const isApproved = piece?.status === "approved";
            const isPending = piece?.status === "pending_review";

            return (
              <button
                key={type}
                type="button"
                onClick={() => setActiveType(type)}
                className={`flex items-center gap-8 rounded-full px-13 py-8 text-sm transition-colors ${
                  isActive
                    ? "neu-raised bg-surface-raised font-medium text-ink"
                    : "text-ink-dim hover:text-ink"
                }`}
              >
                <span>{config.icon}</span>
                <span>{config.label}</span>
                {isApproved && <span className="text-xs text-success">✓</span>}
                {isPending && <span className="h-[6px] w-[6px] rounded-full bg-pending" aria-label="Awaiting review" />}
              </button>
            );
          })}
        </div>

        {/* Language Tabs if multiple */}
        {availableLangs.length > 1 && (
          <div className="neu-inset flex items-center gap-[4px] rounded-full p-[5px] text-xs">
            {availableLangs.map((lang) => (
              <button
                key={lang}
                type="button"
                onClick={() => setActiveLang(lang)}
                className={`rounded-full px-13 py-[4px] font-semibold transition-colors ${
                  activeLang === lang ? "neu-raised bg-surface-raised text-ink" : "text-ink-dim hover:text-ink"
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
          {/* Golden split: the draft (61.8%) beside its review controls (38.2%) */}
          <div className="grid grid-cols-1 gap-21 lg:grid-cols-golden lg:items-start">
            <div className="min-w-0 space-y-13">
              {/* Grounding / Moderation Alerts */}
              {currentPiece.grounding && currentPiece.grounding.pass === false && (
                <div className="rounded-card border border-warning/30 bg-warning/10 p-13 text-xs text-warning">
                  <p className="font-semibold">⚠️ Grounding Alert: Potential unsupported claim detected</p>
                  <ul className="mt-[4px] list-disc pl-21 opacity-90">
                    {(currentPiece.grounding.unsupported || []).slice(0, 3).map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {currentPiece.grounding?.back_translation && (
                <BackTranslationNotice check={currentPiece.grounding.back_translation} />
              )}

              {currentPiece.moderation && currentPiece.moderation.pass === false && (
                <div className="rounded-card border border-danger/30 bg-danger/10 p-13 text-xs text-danger">
                  ⚠️ Moderation Flag: Output triggered keyword review:{" "}
                  {(currentPiece.moderation.hits || []).join(", ")}
                </div>
              )}

              {/* Main Display Area: Editor or Rich Previewer */}
              <div className="flex justify-start">
                {isEditing ? (
                  <div className="w-full max-w-3xl rounded-card border border-amber-400/40 bg-surface p-21">
                    <label htmlFor="draft-title-headline" className="block text-xs font-semibold opacity-60">Title / Headline</label>
                    <input id="draft-title-headline"
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="mt-[4px] w-full rounded-card border border-black/10 bg-canvas-light px-13 py-8 text-sm dark:border-white/[0.08] dark:bg-canvas-dark"
                      placeholder="Enter title…"
                    />

                    <label htmlFor="draft-content-body" className="mt-21 block text-xs font-semibold opacity-60">Content Body</label>
                    <textarea id="draft-content-body"
                      rows={14}
                      value={editBody}
                      onChange={(e) => setEditBody(e.target.value)}
                      className="mt-[4px] w-full rounded-card border border-black/10 bg-canvas-light p-13 text-sm font-sans leading-relaxed dark:border-white/[0.08] dark:bg-canvas-dark"
                      placeholder="Enter content…"
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
                    {currentPiece.normalizedType === "x" && (
                      <XCard body={currentPiece.body} onCopy={() => notify("✓ Copied to clipboard!")} />
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
            </div>

            <aside className="min-w-0 space-y-13 lg:order-last">
              {/* Action Toolbar */}
              <div className="flex flex-col gap-21 rounded-panel border border-white/[0.08] bg-surface p-21">
                <div className="flex items-center gap-13">
                  <span
                    className={`rounded-full px-13 py-[4px] text-xs font-semibold ${
                      currentPiece.status === "approved"
                        ? "bg-success/15 text-success"
                        : currentPiece.status === "rejected"
                        ? "bg-danger/15 text-danger"
                        : "bg-pending/15 text-pending-soft"
                    }`}
                  >
                    {currentPiece.status === "pending_review" ? "Awaiting review" : currentPiece.status === "approved" ? "Approved" : currentPiece.status === "rejected" ? "Rejected" : currentPiece.status.replace("_", " ")}
                  </span>

                  {isEditing ? (
                    <span className="text-xs text-warning">● Editing Draft</span>
                  ) : (
                    <span className="text-xs text-ink-dim">Version {currentPiece.version || 1}</span>
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
                        className="rounded-full bg-amber-400 px-21 py-8 text-sm font-semibold text-on-accent transition-colors hover:bg-amber-300"
                      >
                        {saveMutation.isPending ? "Saving…" : "Save changes"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setIsEditing(false)}
                        className="rounded-full px-13 py-8 text-sm text-ink-dim transition-colors hover:text-ink"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setIsEditing(true)}
                      className="rounded-full border border-white/[0.12] px-21 py-8 text-sm text-ink transition-colors hover:border-amber-400/50"
                    >
                      Edit
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
                    className="rounded-full border border-white/[0.12] px-21 py-8 text-sm text-ink transition-colors hover:border-amber-400/50"
                  >
                    Download
                  </button>

                </div>
              </div>
              {/* Evidence before the decision: where each sentence came from */}
              <SourcesPanel key={currentPiece.id} token={token} jobId={jobId} contentId={currentPiece.id} body={currentPiece.body} />

              {/* Human Approval Gate */}
              {currentPiece.status === "pending_review" ? (
                <div className="space-y-13 rounded-panel border border-white/[0.08] bg-surface p-21">
                  <p className="text-xs leading-relaxed text-ink-dim">
                    Checked the sources? Approving marks this draft ready. When every draft is reviewed, the session
                    becomes ready to publish.
                  </p>
                  <div className="flex flex-wrap items-center gap-8">
                    <button
                      type="button"
                      onClick={() => approveMutation.mutate(currentPiece.id)}
                      disabled={approveMutation.isPending || isEditing}
                      title={isEditing ? "Save or cancel your edit first" : undefined}
                      className="btn-primary"
                    >
                      {approveMutation.isPending ? "Approving…" : "Approve"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowRejectModal(true)}
                      className="rounded-full border border-rose-400/40 px-21 py-8 text-sm text-rose-300 transition-colors hover:bg-rose-400/10"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ) : (
                <p className="px-8 text-xs leading-relaxed text-ink-dim">
                  {currentPiece.status === "rejected"
                    ? "Rejected. Edit and save it, or regenerate the session, to get a new version to review."
                    : "Approved. You can publish it below."}
                </p>
              )}

              <PublishSection
                token={token}
                contentId={currentPiece.id}
                kind={currentPiece.normalizedType}
                approved={currentPiece.status === "approved" || currentPiece.status === "ready_to_publish"}
                onPublished={notify}
              />

            </aside>
          </div>
        </>
      )}

      {/* Reject Reason Modal */}
      {showRejectModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-21"
          onClick={(e) => e.target === e.currentTarget && setShowRejectModal(false)}
          onKeyDown={(e) => e.key === "Escape" && setShowRejectModal(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="reject-draft-title"
            className="w-full max-w-md rounded-card border border-danger/40 bg-surface-light p-21 dark:bg-surface-dark"
          >
            <h3 id="reject-draft-title" className="font-display text-lg text-ink-light dark:text-ink-dark">
              Reject Draft
            </h3>
            <p className="mt-[4px] text-xs opacity-60">
              Provide feedback for why this content is being rejected:
            </p>

            {/* Focus lands in the reason box when the dialog opens, so Esc works at once. */}
            <textarea
              rows={4}
              autoFocus
              aria-label="Reason for rejecting"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g., Tone is too informal, missed key metrics mentioned by speaker…"
              className="mt-13 w-full rounded-card border border-black/10 bg-canvas-light p-13 text-sm dark:border-white/[0.08] dark:bg-canvas-dark"
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
                className="rounded-card bg-danger px-21 py-8 text-xs font-semibold text-on-accent hover:opacity-90"
              >
                {rejectMutation.isPending ? "Rejecting…" : "Confirm Rejection"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
