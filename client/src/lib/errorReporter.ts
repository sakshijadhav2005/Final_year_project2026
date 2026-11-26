const API_BASE = import.meta.env.VITE_API_URL ?? "";

/**
 * Development only: send uncaught browser errors to the backend's error-repair agent.
 * React 19 reports render errors through window "error" too, so this covers them.
 */
export function startErrorReporter() {
  if (!import.meta.env.DEV) return;
  const seen = new Set<string>();

  const send = (name: string, message: string, stack?: string) => {
    const key = `${name}|${message}|${(stack ?? "").split("\n")[1] ?? ""}`;
    if (seen.has(key) || seen.size > 50) return;
    seen.add(key);
    void fetch(`${API_BASE}/api/v1/autofix/client-errors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, message: message.slice(0, 4000), stack: stack?.slice(0, 20000), page: location.pathname }),
      keepalive: true,
    }).catch(() => undefined);
  };

  window.addEventListener("error", (e) => {
    const err = e.error instanceof Error ? e.error : null;
    send(err?.name ?? "Error", err?.message ?? e.message, err?.stack);
  });
  window.addEventListener("unhandledrejection", (e) => {
    const err = e.reason instanceof Error ? e.reason : null;
    // Failed API calls are already recorded on the server side.
    if (!err || err.name === "ApiError" || /^(Failed to fetch|NetworkError|Load failed)/i.test(err.message)) return;
    send(err.name, err.message, err.stack);
  });
}
