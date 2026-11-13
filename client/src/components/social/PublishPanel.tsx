import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listPublications, listSocialAccounts, publishContent, type SocialPlatform } from "@/lib/api";

interface PublishPanelProps {
  token: string;
  contentId: string;
  platform: SocialPlatform;
  approved: boolean;
  onPublished?: (url: string | null) => void;
}

/** "Publish to LinkedIn" for an approved draft, with the link once it is live. */
export function PublishPanel({ token, contentId, platform, approved, onPublished }: PublishPanelProps) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const accounts = useQuery({ queryKey: ["social-accounts"], queryFn: () => listSocialAccounts(token) });
  const history = useQuery({
    queryKey: ["publications", contentId],
    queryFn: () => listPublications(token, contentId),
  });

  const publish = useMutation({
    mutationFn: () => publishContent(token, contentId, platform),
    onSuccess: (post) => {
      setConfirming(false);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["publications", contentId] });
      onPublished?.(post.post_url);
    },
    onError: (err: Error) => {
      setConfirming(false);
      setError(err.message);
      queryClient.invalidateQueries({ queryKey: ["publications", contentId] });
    },
  });

  const status = accounts.data?.find((a) => a.platform === platform);
  const live = history.data?.find((p) => p.platform === platform && p.status === "posted");
  const label = "LinkedIn";

  let body: ReactNode;
  if (live) {
    body = (
      <p className="text-xs text-success">
        ✓ Published to {label}.{" "}
        {live.post_url && (
          <a href={live.post_url} target="_blank" rel="noreferrer" className="underline">
            View post ↗
          </a>
        )}
      </p>
    );
  } else if (!approved) {
    body = <p className="text-xs text-ink-dim">Approve this draft to publish it to {label}.</p>;
  } else if (status && !status.configured) {
    body = <p className="text-xs text-ink-dim">{label} publishing is not set up on this server.</p>;
  } else if (status && (!status.account || status.account.expired)) {
    body = (
      <p className="text-xs text-ink-dim">
        <Link to="/settings" className="underline">
          {status.account ? "Reconnect" : "Connect"} your {label} account
        </Link>{" "}
        to publish this draft.
      </p>
    );
  } else if (confirming) {
    body = (
      <div className="space-y-8">
        <p className="text-xs text-ink">
          Post this publicly as <strong>{status?.account?.display_name ?? "you"}</strong> on {label}?
        </p>
        <div className="flex gap-8">
          <button
            type="button"
            onClick={() => publish.mutate()}
            disabled={publish.isPending}
            className="rounded-full bg-[#0A66C2] px-21 py-8 text-sm font-semibold text-white transition-colors hover:bg-[#004182]"
          >
            {publish.isPending ? "Publishing…" : "Yes, publish"}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            disabled={publish.isPending}
            className="rounded-full px-13 py-8 text-sm text-ink-dim transition-colors hover:text-ink"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  } else {
    body = (
      <button
        type="button"
        onClick={() => {
          setError(null);
          setConfirming(true);
        }}
        disabled={!status}
        className="rounded-full bg-[#0A66C2] px-21 py-8 text-sm font-semibold text-white transition-colors hover:bg-[#004182] disabled:opacity-50"
      >
        Publish to {label}
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-8 rounded-panel border border-white/[0.08] bg-surface p-21">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-dim">Publish</span>
      {body}
      {error && !live && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
