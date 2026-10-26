import { useEffect, useRef, useState } from "react";

import { isExpiringSoon, refreshSession } from "@/lib/session";
import type { AgentStatus } from "@/types/pipeline";

interface JobEventData {
  id: string;
  status: string;
  progress: Record<string, AgentStatus>;
  error_message: string | null;
}

const TERMINAL_STATUSES = new Set([
  "pending_review",
  "ready_to_publish",
  "needs_reupload",
  "needs_review",
  "failed",
  "cancelled",
]);

export function useJobEvents(jobId: string | undefined, token: string | null) {
  const [eventData, setEventData] = useState<JobEventData | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  // Bumped to reopen the stream after a dropped connection.
  const [attempt, setAttempt] = useState(0);
  const finished = useRef(false);

  useEffect(() => {
    finished.current = false;
    setAttempt(0);
  }, [jobId]);

  useEffect(() => {
    if (!jobId || !token || finished.current) return;
    let retryTimer: number | undefined;

    // EventSource cannot send headers, so the backend accepts the token as ?token=.
    // The token is only checked when the stream opens; when it changes (background
    // renewal) this effect reconnects with the new one.
    const url = `${import.meta.env.VITE_API_URL ?? ""}/api/v1/jobs/${jobId}/events?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);

    es.onopen = () => {
      setIsConnected(true);
    };

    es.addEventListener("job", (e) => {
      try {
        const parsed = JSON.parse(e.data) as JobEventData;
        setEventData(parsed);
        if (TERMINAL_STATUSES.has(parsed.status)) {
          finished.current = true;
          es.close();
          setIsConnected(false);
        }
      } catch {
        /* ignore parse error */
      }
    });

    es.onerror = () => {
      es.close();
      setIsConnected(false);
      if (finished.current) return;
      // The connection dropped mid-run (expired token, server restart, network).
      // Renew the token if needed and reconnect instead of freezing the progress view.
      const delay = Math.min(1000 * 2 ** Math.min(attempt, 4), 15000);
      retryTimer = window.setTimeout(async () => {
        if (isExpiringSoon(token, 30_000)) {
          const fresh = await refreshSession();
          if (!fresh) return; // signed out for real: the router sends the user to login
          if (fresh !== token) return; // the token change re-runs this effect
        }
        setAttempt((n) => n + 1);
      }, delay);
    };

    return () => {
      window.clearTimeout(retryTimer);
      es.close();
      setIsConnected(false);
    };
  }, [jobId, token, attempt]);

  return { eventData, isConnected };
}
