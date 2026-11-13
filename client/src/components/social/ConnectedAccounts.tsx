import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { disconnectSocial, listSocialAccounts, startSocialConnect, type SocialPlatform } from "@/lib/api";

const PLATFORM_LABEL: Record<SocialPlatform, string> = { linkedin: "LinkedIn", instagram: "Instagram" };

const PLATFORM_BADGE: Record<SocialPlatform, { text: string; className: string }> = {
  linkedin: { text: "in", className: "bg-[#0A66C2]" },
  instagram: { text: "IG", className: "bg-gradient-to-tr from-[#F58529] via-[#DD2A7B] to-[#8134AF]" },
};

const ENV_HINT: Record<SocialPlatform, string> = {
  linkedin: "LINKEDIN_CLIENT_ID",
  instagram: "INSTAGRAM_CLIENT_ID",
};

const ERROR_TEXT: Record<string, string> = {
  invalid_state: "The sign-in link expired or was opened in another browser. Try again.",
  user_cancelled_login: "You cancelled the LinkedIn sign-in.",
  user_cancelled_authorize: "You cancelled the LinkedIn sign-in.",
  linkedin_oauth_failed: "LinkedIn did not accept the sign-in. Check the app's products and redirect URL.",
  linkedin_unreachable: "Could not reach LinkedIn. Check your connection and try again.",
  user_denied: "You cancelled the Instagram sign-in.",
  instagram_oauth_failed: "Instagram did not accept the sign-in. It must be a Business or Creator account.",
  instagram_unreachable: "Could not reach Instagram. Check your connection and try again.",
};

/** Settings section: connect the accounts that approved drafts can be published to. */
export function ConnectedAccounts({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [banner, setBanner] = useState<{ ok: boolean; text: string } | null>(null);

  const accounts = useQuery({ queryKey: ["social-accounts"], queryFn: () => listSocialAccounts(token) });

  // The OAuth callback lands on /settings?social=linkedin&status=connected|error&reason=...
  useEffect(() => {
    const platform = params.get("social") as SocialPlatform | null;
    const status = params.get("status");
    if (!platform || !status) return;
    const label = PLATFORM_LABEL[platform] ?? platform;
    if (status === "connected") setBanner({ ok: true, text: `✓ ${label} connected.` });
    else setBanner({ ok: false, text: ERROR_TEXT[params.get("reason") ?? ""] ?? `Could not connect ${label}.` });
    setParams({}, { replace: true });
    queryClient.invalidateQueries({ queryKey: ["social-accounts"] });
  }, [params, setParams, queryClient]);

  const connect = useMutation({
    mutationFn: (platform: SocialPlatform) => startSocialConnect(token, platform),
    onSuccess: ({ authorize_url }) => {
      window.location.assign(authorize_url);
    },
    onError: (err: Error) => setBanner({ ok: false, text: err.message }),
  });

  const disconnect = useMutation({
    mutationFn: (platform: SocialPlatform) => disconnectSocial(token, platform),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["social-accounts"] }),
  });

  return (
    <section className="rounded-card border border-black/10 bg-surface-light p-21 dark:border-white/[0.08] dark:bg-surface-dark dark:shadow-none">
      <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Connected accounts</h3>
      <p className="mt-[4px] text-xs text-ink-light/50 dark:text-ink-dim">
        Publish approved drafts straight to your own social accounts. Nothing is posted until you press Publish.
      </p>

      {banner && (
        <div
          className={`mt-13 rounded-card p-13 text-xs font-medium ${
            banner.ok ? "bg-success/20 text-success" : "bg-danger/15 text-danger"
          }`}
        >
          {banner.text}
        </div>
      )}

      <div className="mt-13 space-y-8">
        {accounts.isLoading && <p className="text-xs text-ink-dim">Loading…</p>}
        {accounts.isError && <p className="text-xs text-danger">Could not load connected accounts.</p>}
        {accounts.data?.map((item) => {
          const label = PLATFORM_LABEL[item.platform] ?? item.platform;
          const account = item.account;
          return (
            <div
              key={item.platform}
              className="flex flex-wrap items-center justify-between gap-13 rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]"
            >
              <div className="flex items-center gap-13">
                <span
                  className={`flex h-8 w-8 items-center justify-center rounded text-[11px] font-bold text-white ${PLATFORM_BADGE[item.platform]?.className ?? "bg-ink-dim"}`}
                >
                  {PLATFORM_BADGE[item.platform]?.text ?? "?"}
                </span>
                <div>
                  <span className="block font-medium text-ink-light dark:text-ink-dark">{label}</span>
                  <span className="text-ink-light/60 dark:text-ink-dim">
                    {!item.configured
                      ? `Not set up on this server (${ENV_HINT[item.platform]})`
                      : account
                        ? account.expired
                          ? `${account.display_name ?? "Connected"} · connection expired`
                          : `Connected as ${account.display_name ?? "your account"}`
                        : "Not connected"}
                  </span>
                </div>
              </div>
              {item.configured && (
                <div className="flex gap-8">
                  {(!account || account.expired) && (
                    <button
                      type="button"
                      onClick={() => connect.mutate(item.platform)}
                      disabled={connect.isPending}
                      className="btn-primary btn-sm"
                    >
                      {connect.isPending ? "Opening…" : account ? "Reconnect" : "Connect"}
                    </button>
                  )}
                  {account && (
                    <button
                      type="button"
                      onClick={() => disconnect.mutate(item.platform)}
                      disabled={disconnect.isPending}
                      className="btn-ghost btn-sm"
                    >
                      Disconnect
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
