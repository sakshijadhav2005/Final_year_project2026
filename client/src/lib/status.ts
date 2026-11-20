// Plain-language labels for job and draft statuses, shared by every status chip.
const LABELS: Record<string, string> = {
  queued: "Queued",
  validating: "Checking the file",
  transcribing: "Transcribing",
  analyzing: "Analysing",
  planning: "Planning",
  generating: "Writing drafts",
  guarding: "Checking drafts",
  translating: "Translating",
  pending_review: "Awaiting review",
  needs_review: "Needs review",
  ready_to_publish: "Ready to publish",
  approved: "Approved",
  rejected: "Rejected",
  needs_reupload: "Needs a new recording",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function statusLabel(status: string | null | undefined): string {
  if (!status) return "";
  const known = LABELS[status];
  if (known) return known;
  const words = status.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** A readable session name: its event or file name, else a short id. */
export function sessionTitle(job: { id: string; title?: string | null } | null | undefined): string {
  if (!job) return "Session";
  return job.title?.trim() || `Session ${job.id.slice(0, 8)}`;
}
