import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  fetchSocialImage,
  listPublications,
  listSocialAccounts,
  publishContent,
  publishInstagramWithImage,
  type SocialPlatform,
} from "@/lib/api";

interface PublishPanelProps {
  token: string;
  contentId: string;
  platform: SocialPlatform;
  approved: boolean;
  onPublished?: (url: string | null) => void;
}

const PLATFORM_STYLE: Record<SocialPlatform, { label: string; button: string }> = {
  linkedin: { label: "LinkedIn", button: "bg-[#0A66C2] hover:bg-[#004182]" },
  instagram: {
    label: "Instagram",
    button: "bg-gradient-to-r from-[#F58529] via-[#DD2A7B] to-[#8134AF] hover:opacity-90",
  },
};

/** Instagram posts need a picture: the generated recap card, or the user's own. */
function InstagramImagePicker({
  token,
  contentId,
  file,
  onFile,
}: {
  token: string;
  contentId: string;
  file: File | null;
  onFile: (file: File | null) => void;
}) {
  const card = useQuery({
    queryKey: ["social-image", contentId],
    queryFn: () => fetchSocialImage(token, contentId),
    staleTime: Infinity,
  });
  const [fileUrl, setFileUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setFileUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setFileUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const src = fileUrl ?? card.data;
  return (
    <div className="space-y-8">
      <div className="overflow-hidden rounded-card border border-white/[0.08] bg-black/20">
        {src ? (
          <img src={src} alt="Image that will be posted" className="aspect-[4/5] w-full object-contain" />
        ) : (
          <div className="flex aspect-[4/5] items-center justify-center text-xs text-ink-dim">
            {card.isError ? "Could not render the recap card" : "Rendering recap card…"}
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-8 text-xs">
        <label className="cursor-pointer rounded-full border border-white/[0.12] px-13 py-[6px] text-ink transition-colors hover:border-amber-400/50">
          {file ? "Choose another photo" : "Use my own photo"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />
        </label>
        {file && (
          <button type="button" onClick={() => onFile(null)} className="text-ink-dim underline hover:text-ink">
            Use the recap card
          </button>
        )}
      </div>
    </div>
  );
}

/** "Publish to <platform>" for an approved draft, with the link once it is live. */
export function PublishPanel({ token, contentId, platform, approved, onPublished }: PublishPanelProps) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [image, setImage] = useState<File | null>(null);
  const { label, button } = PLATFORM_STYLE[platform];

  const accounts = useQuery({ queryKey: ["social-accounts"], queryFn: () => listSocialAccounts(token) });
  const history = useQuery({
    queryKey: ["publications", contentId],
    queryFn: () => listPublications(token, contentId),
  });

  const publish = useMutation({
    mutationFn: () =>
      platform === "instagram" && image
        ? publishInstagramWithImage(token, contentId, image)
        : publishContent(token, contentId, platform),
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
  const ready = approved && status?.configured && status.account && !status.account.expired && !live;
  const buttonClass = `rounded-full px-21 py-8 text-sm font-semibold text-white transition-colors disabled:opacity-50 ${button}`;

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
          <button type="button" onClick={() => publish.mutate()} disabled={publish.isPending} className={buttonClass}>
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
        className={`self-start ${buttonClass}`}
      >
        Publish to {label}
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-8 rounded-panel border border-white/[0.08] bg-surface p-21">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-dim">Publish</span>
      {platform === "instagram" && ready && (
        <InstagramImagePicker token={token} contentId={contentId} file={image} onFile={setImage} />
      )}
      {body}
      {error && !live && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
