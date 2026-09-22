import { useEffect, useState } from "react";
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

  useEffect(() => {
    if (!jobId || !token) return;

    // Connect using EventSource
    // Note: EventSource native doesn't support headers, but our backend accepts bearer token in query parameter:
    // get_user_from_bearer_or_query accepts ?token=...
    const url = `/api/v1/jobs/${jobId}/events?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);

    es.onopen = () => {
      setIsConnected(true);
    };

    es.addEventListener("job", (e) => {
      try {
        const parsed = JSON.parse(e.data) as JobEventData;
        setEventData(parsed);
        if (TERMINAL_STATUSES.has(parsed.status)) {
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
    };

    return () => {
      es.close();
      setIsConnected(false);
    };
  }, [jobId, token]);

  return { eventData, isConnected };
}
