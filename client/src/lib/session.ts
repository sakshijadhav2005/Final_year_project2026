import { useAuthStore } from "@/store/auth";

/**
 * Keeps the user signed in while long jobs run.
 *
 * Access tokens are short-lived (ACCESS_TOKEN_EXPIRE_MINUTES, 15 min by default).
 * Instead of signing the user out when one expires, we swap the refresh token for a
 * new pair: proactively a couple of minutes before expiry, and on demand when a
 * request comes back 401. Only when the refresh token itself is rejected is the
 * user signed out.
 */

const API_BASE = import.meta.env.VITE_API_URL ?? "";
const REFRESH_EARLY_MS = 2 * 60 * 1000; // renew 2 minutes before expiry
const CHECK_EVERY_MS = 30 * 1000;

type TokenPair = {
  access_token: string;
  refresh_token: string;
  user: Parameters<ReturnType<typeof useAuthStore.getState>["setSession"]>[2];
};

let inFlight: Promise<string | null> | null = null;

/** Seconds-since-epoch `exp` claim of a JWT, or null if it cannot be read. */
export function tokenExpiry(token: string | null | undefined): number | null {
  if (!token) return null;
  try {
    const part = token.split(".")[1];
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "="));
    const exp = (JSON.parse(json) as { exp?: number }).exp;
    return typeof exp === "number" ? exp * 1000 : null;
  } catch {
    return null;
  }
}

export function isExpiringSoon(token: string | null | undefined, withinMs = REFRESH_EARLY_MS): boolean {
  const exp = tokenExpiry(token);
  return exp !== null && exp - Date.now() < withinMs;
}

/** Another tab may already have rotated the tokens: pick up what it saved. */
async function syncFromOtherTabs() {
  try {
    await useAuthStore.persist.rehydrate();
  } catch {
    /* storage unavailable: keep in-memory state */
  }
}

/**
 * Exchange the refresh token for a new access token. Concurrent callers share one
 * request (the server rotates refresh tokens, so two parallel refreshes would
 * invalidate each other). Returns the new access token, or null if signed out.
 */
export function refreshSession(failedToken?: string | null): Promise<string | null> {
  // The token that just failed was already replaced (by this tab or another one).
  const current = useAuthStore.getState().accessToken;
  if (failedToken && current && current !== failedToken && !isExpiringSoon(current, 10_000)) {
    return Promise.resolve(current);
  }
  if (inFlight) return inFlight;
  inFlight = (async () => {
    const before = useAuthStore.getState().accessToken;
    await syncFromOtherTabs();
    const state = useAuthStore.getState();
    // Another tab refreshed in the meantime and its token is still good.
    if (state.accessToken && state.accessToken !== before && !isExpiringSoon(state.accessToken)) {
      return state.accessToken;
    }
    if (!state.refreshToken) {
      if (state.accessToken || state.user) state.logout();
      return null;
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });
      if (res.status === 401 || res.status === 403) {
        // A different tab may have used this refresh token a moment ago.
        await syncFromOtherTabs();
        const latest = useAuthStore.getState();
        if (latest.refreshToken && latest.refreshToken !== state.refreshToken && latest.accessToken) {
          return latest.accessToken;
        }
        latest.logout();
        return null;
      }
      if (!res.ok) return state.accessToken; // server hiccup: keep the session, try again later
      const pair = (await res.json()) as TokenPair;
      useAuthStore.getState().setSession(pair.access_token, pair.refresh_token, pair.user);
      return pair.access_token;
    } catch {
      return state.accessToken; // offline: do not sign the user out
    }
  })().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

/** fetch() with the current access token; on 401 it refreshes once and retries. */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const send = (token: string | null) => {
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(`${API_BASE}${path}`, { ...init, headers });
  };
  let token = useAuthStore.getState().accessToken;
  if (token && isExpiringSoon(token, 10_000)) token = await refreshSession();
  const res = await send(token);
  if (res.status !== 401 || !useAuthStore.getState().refreshToken) return res;
  const fresh = await refreshSession(token);
  return fresh ? send(fresh) : res;
}

let keeperStarted = false;

/** Start the background timer that renews the token before it expires. */
export function startSessionKeeper() {
  if (keeperStarted || typeof window === "undefined") return;
  keeperStarted = true;
  const tick = () => {
    const { accessToken, refreshToken } = useAuthStore.getState();
    if (accessToken && refreshToken && isExpiringSoon(accessToken)) void refreshSession();
  };
  tick();
  window.setInterval(tick, CHECK_EVERY_MS);
  // Laptops sleep; timers pause. Check again as soon as the tab is visible.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") tick();
  });
  // Keep every open tab on the same (latest) tokens.
  window.addEventListener("storage", (e) => {
    if (e.key === "eventai-auth") void syncFromOtherTabs();
  });
}
