import { authFetch, refreshSession } from "@/lib/session";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export type UserRole = "admin" | "content_creator" | "event_organizer" | "regular_user";

export type EventType = "meetup" | "event" | "speech" | "other";

export type EventPublic = {
  id: string;
  name: string;
  date: string;
  topic?: string | null;
  organizer_name?: string | null;
  location?: string | null;
  banner_image?: string | null;
  description?: string | null;
  type: EventType;
  organizer_id: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type UserPublic = {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  user: UserPublic;
};

export type JobPublic = {
  id: string;
  user_id?: string | null;
  event_id?: string | null;
  status: string;
  requested_types: string[] | null;
  target_languages: string[] | null;
  progress: Record<string, string> | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string | null;
  finished_at: string | null;
};

export type TranscriptPublic = {
  full_text: string;
  language: string;
  avg_confidence: number | null;
  quality_json: Record<string, unknown> | null;
  segments: unknown[] | null;
  provider: string;
  badge: "high" | "medium" | "low";
};

export type ContentPublic = {
  id: string;
  job_id?: string | null;
  event_id?: string | null;
  user_id?: string | null;
  author_name?: string | null;
  type: string;
  language: string;
  title: string | null;
  body: string;
  structured: Record<string, unknown> | null;
  status: string;
  version: number;
  grounding: { pass?: boolean; unsupported?: string[] } | null;
  moderation: { pass?: boolean; hits?: string[] } | null;
  created_at?: string | null;
};

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  env?: string;
};

export type ReadyResponse = {
  status: string;
  checks: { postgres: string; redis: string };
};

function authHeaders(token?: string | null): HeadersInit {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export async function request<T>(
  path: string,
  init: RequestInit & { token?: string | null; json?: unknown } = {},
): Promise<T> {
  const { token, json, headers, ...rest } = init;
  const send = (bearer?: string | null) =>
    fetch(`${API_BASE}${path}`, {
      ...rest,
      headers: {
        ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(bearer),
        ...(headers ?? {}),
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  let response = await send(token);
  // An expired access token is not a reason to sign out: renew it and retry once.
  // refreshSession() signs the user out only if the refresh token is rejected too.
  if (response.status === 401 && token) {
    const fresh = await refreshSession(token);
    if (fresh) response = await send(fresh);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (payload.detail && typeof payload.detail === "object" && "detail" in payload.detail) {
        message = String((payload.detail as { detail: string }).detail);
      }
    } catch {
      /* ignore */
    }
    const error = new Error(message);
    error.name = "ApiError"; // the server records its own failures; the browser reporter skips these
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const getApiHealth = () => request<HealthResponse>("/api/v1/health");
export const getReady = () => request<ReadyResponse>("/api/v1/ready");
export const registerAccount = (email: string, password: string, role: UserRole) =>
  request<TokenResponse>("/api/v1/auth/register", { method: "POST", json: { email, password, role } });
export const loginAccount = (email: string, password: string) =>
  request<TokenResponse>("/api/v1/auth/login", { method: "POST", json: { email, password } });
export const fetchMe = (token: string) => request<UserPublic>("/api/v1/auth/me", { token });
/** The signed-in user's own sessions. `all` (admins only) returns every user's. */
export const listJobs = (token: string, opts?: { all?: boolean }) =>
  request<JobPublic[]>(`/api/v1/jobs${opts?.all ? "?scope=all" : ""}`, { token });
export const getJob = (token: string, id: string) => request<JobPublic>(`/api/v1/jobs/${id}`, { token });
export const getTranscript = (token: string, id: string) =>
  request<TranscriptPublic>(`/api/v1/jobs/${id}/transcript`, { token });
export const getJobContent = (token: string, id: string) =>
  request<ContentPublic[]>(`/api/v1/jobs/${id}/content`, { token });
export type ProvenanceClaim = {
  sentence: string;
  status: "traced" | "partial" | "untraced";
  support: number;
  position: number | null;
  start: number | null;
  end: number | null;
  evidence: string | null;
};

export type ContentProvenance = {
  available: boolean;
  method?: string;
  claims: ProvenanceClaim[];
  summary: {
    claims: number;
    traced: number;
    partial: number;
    coverage: number | null;
    bins: number[];
    spread: number;
  } | null;
};

export const getContentProvenance = (token: string, id: string) =>
  request<ContentProvenance>(`/api/v1/content/${id}/provenance`, { token });

/** <audio> cannot send headers, so the backend accepts the token as ?token= (like SSE). */
export const jobMediaUrl = (token: string, jobId: string) =>
  `${API_BASE}/api/v1/jobs/${jobId}/media?token=${encodeURIComponent(token)}`;

export const approveContent = (token: string, id: string) =>
  request<ContentPublic>(`/api/v1/content/${id}/approve`, { method: "POST", token });
export const rejectContent = (token: string, id: string, reason: string) =>
  request<ContentPublic>(`/api/v1/content/${id}/reject`, { method: "POST", token, json: { reason } });
// ── Social publishing ──────────────────────────────────────────────────────────
export type SocialPlatform = "linkedin";

export type SocialPlatformStatus = {
  platform: SocialPlatform;
  configured: boolean;
  account: {
    platform: SocialPlatform;
    display_name: string | null;
    connected_at: string | null;
    expires_at: string | null;
    expired: boolean;
  } | null;
};

export type SocialPost = {
  id: string;
  content_id: string;
  platform: SocialPlatform;
  status: "posted" | "failed" | "pending";
  external_post_id: string | null;
  post_url: string | null;
  error: string | null;
  created_at: string | null;
};

export const listSocialAccounts = (token: string) =>
  request<SocialPlatformStatus[]>("/api/v1/social/accounts", { token });
/** Returns the platform's sign-in URL; the caller sends the browser there. */
export const startSocialConnect = (token: string, platform: SocialPlatform) =>
  request<{ authorize_url: string }>(`/api/v1/social/${platform}/connect`, { token, credentials: "include" });
export const disconnectSocial = (token: string, platform: SocialPlatform) =>
  request<void>(`/api/v1/social/accounts/${platform}`, { method: "DELETE", token });
export const publishContent = (token: string, id: string, platform: SocialPlatform) =>
  request<SocialPost>(`/api/v1/content/${id}/publish`, { method: "POST", token, json: { platform } });
export const listPublications = (token: string, id: string) =>
  request<SocialPost[]>(`/api/v1/content/${id}/publications`, { token });

export const listAdminJobs = (token: string) => request<JobPublic[]>("/api/v1/admin/jobs", { token });
export const listAudit = (token: string) => request<Record<string, string | null>[]>("/api/v1/admin/audit", { token });

export type AutoFixStatus =
  | "new" | "external" | "fixing" | "proposed" | "revising" | "approved" | "rejected" | "failed";

export type AutoFixSummary = {
  id: string;
  fingerprint: string;
  source: "api" | "pipeline" | "frontend";
  error_type: string;
  message: string;
  location: string | null;
  occurrences: number;
  status: AutoFixStatus;
  status_detail: string | null;
  attempts: number;
  risk: "low" | "medium" | "high" | null;
  cost_usd: number;
  branch: string | null;
  pr_url: string | null;
  title: string | null;
  created_at: string | null;
  last_seen: string | null;
  decided_at: string | null;
};

type CheckBlock = { passed: boolean | null; output: string } | null;
export type RiskFinding = { file: string | null; line: number | null; finding: string; risk: "low" | "medium" | "high" };

export type AutoFixDetail = AutoFixSummary & {
  stack: string | null;
  context: Record<string, string> | null;
  report: { fixed?: boolean; title?: string; root_cause?: string; fix?: string; test?: string; risk?: string; notes?: string } | null;
  diff: string | null;
  checks: { passed: boolean; backend: CheckBlock; frontend: CheckBlock; reproduced: boolean | null; note?: string } | null;
  review: {
    scan: { risk: string; blocked: boolean; findings: RiskFinding[]; files: string[] };
    agent: { verdict?: string; risk?: string; notes?: string[] } | null;
  } | null;
  feedback: string | null;
  base_branch: string | null;
  base_commit: string | null;
  decided_by: string | null;
};

export type AutoFixAgentStatus = {
  active: boolean;
  environment: string;
  agent_found: boolean;
  agent_cmd: string | null;
  github_cli: boolean;
  attempts_today: number;
  max_per_day: number;
  llm_review: boolean;
  gateway: { gateway: "portkey" | "direct"; ready: boolean; route: string | null; detail?: string };
};

export const getAutoFixStatus = (token: string) => request<AutoFixAgentStatus>("/api/v1/autofix/status", { token });
export const listAutoFixes = (token: string) => request<AutoFixSummary[]>("/api/v1/autofix/issues", { token });
export const getAutoFix = (token: string, id: string) => request<AutoFixDetail>(`/api/v1/autofix/issues/${id}`, { token });
export const approveAutoFix = (token: string, id: string) =>
  request<AutoFixDetail>(`/api/v1/autofix/issues/${id}/approve`, { method: "POST", token });
export const rejectAutoFix = (token: string, id: string, reason: string) =>
  request<AutoFixDetail>(`/api/v1/autofix/issues/${id}/reject`, { method: "POST", token, json: { reason } });
export const reviseAutoFix = (token: string, id: string, feedback: string) =>
  request<AutoFixDetail>(`/api/v1/autofix/issues/${id}/revise`, { method: "POST", token, json: { feedback } });
export const retryAutoFix = (token: string, id: string) =>
  request<AutoFixDetail>(`/api/v1/autofix/issues/${id}/retry`, { method: "POST", token });

export const patchContent = (
  token: string,
  id: string,
  data: { title?: string | null; body?: string | null },
) => request<ContentPublic>(`/api/v1/content/${id}`, { method: "PATCH", token, json: data });

export const cancelJob = (token: string, id: string) =>
  request<JobPublic>(`/api/v1/jobs/${id}/cancel`, { method: "POST", token });

export const regenerateJob = (
  token: string,
  id: string,
  data?: { requested_types?: string[]; target_languages?: string[] },
) => request<JobPublic>(`/api/v1/jobs/${id}/regenerate`, { method: "POST", token, json: data });

export async function downloadContent(
  token: string,
  contentId: string,
  format: "markdown" | "text" | "json" = "markdown",
  filename?: string,
) {
  const res = await authFetch(`/api/v1/content/${contentId}/download?format=${format}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const ext = format === "json" ? "json" : format === "text" ? "txt" : "md";
  a.download = filename ? `${filename}.${ext}` : `content_${contentId}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function uploadRecording(
  token: string,
  file: File,
  options: { consent: boolean; languages: string; types: string; event_id?: string },
) {
  const body = new FormData();
  body.append("file", file);
  body.append("consent_confirmed", options.consent ? "true" : "false");
  body.append("target_languages", options.languages);
  body.append("requested_types", options.types);
  if (options.event_id) {
    body.append("event_id", options.event_id);
  }
  return request<JobPublic>("/api/v1/uploads", { method: "POST", token, body });
}

export const listEvents = (token: string, type?: EventType | "all") =>
  request<EventPublic[]>(`/api/v1/events${type && type !== "all" ? `?type=${type}` : ""}`, { token });
/** Only the events the signed-in user created (for "which event is this recording for?"). */
export const listMyEvents = (token: string) => request<EventPublic[]>("/api/v1/events?mine=true", { token });

export const getEvent = (token: string, id: string) =>
  request<EventPublic>(`/api/v1/events/${id}`, { token });

export const createEvent = (
  token: string,
  data: {
    name: string;
    date: string;
    topic?: string;
    location?: string;
    banner_image?: string;
    description?: string;
    organizer_name?: string;
    type?: EventType;
  },
) => request<EventPublic>("/api/v1/events", { method: "POST", token, json: data });

export const listCommunityContent = (token: string, params?: { event_id?: string; type?: string }) => {
  const q = new URLSearchParams();
  if (params?.event_id) q.set("event_id", params.event_id);
  if (params?.type) q.set("type", params.type);
  const qs = q.toString();
  return request<ContentPublic[]>(`/api/v1/content${qs ? `?${qs}` : ""}`, { token });
};

export type UserProfilePublic = {
  full_name: string | null;
  organization: string | null;
  job_title: string | null;
  bio: string | null;
  linkedin_handle: string | null;
  instagram_handle: string | null;
  website_url: string | null;
  brand_tone: string | null;
  custom_signoff: string | null;
};

export type UserProfileUpdate = Partial<UserProfilePublic>;

export type ChatMessagePublic = {
  id: string;
  session_id: string;
  sender_type: "user" | "assistant" | "system";
  content: string;
  created_at?: string | null;
};

export type ChatSessionPublic = {
  id: string;
  user_id: string;
  event_id?: string | null;
  job_id?: string | null;
  context_type: "organizer_copilot" | "attendee_qa" | "general";
  title: string;
  created_at?: string | null;
  messages?: ChatMessagePublic[];
};

export const createPost = (
  token: string,
  data: { title: string; body: string; type?: string; event_id?: string },
) => request<ContentPublic>("/api/v1/content", { method: "POST", token, json: data });

export const deleteJob = (token: string, id: string) =>
  request<void>(`/api/v1/jobs/${id}`, { method: "DELETE", token });

export const deleteEvent = (token: string, id: string) =>
  request<void>(`/api/v1/events/${id}`, { method: "DELETE", token });

export const getProfile = (token: string) =>
  request<UserProfilePublic>("/api/v1/auth/profile", { token });

export const updateProfile = (token: string, data: UserProfileUpdate) =>
  request<UserProfilePublic>("/api/v1/auth/profile", { method: "PUT", token, json: data });

export const listChatSessions = (token: string, eventId?: string) =>
  request<ChatSessionPublic[]>(`/api/v1/chat/sessions${eventId ? `?event_id=${eventId}` : ""}`, { token });

export const createChatSession = (
  token: string,
  data: { context_type?: string; event_id?: string; job_id?: string; title?: string },
) => request<ChatSessionPublic>("/api/v1/chat/sessions", { method: "POST", token, json: data });

export const getChatSession = (token: string, sessionId: string) =>
  request<ChatSessionPublic>(`/api/v1/chat/sessions/${sessionId}`, { token });

export const sendChatMessage = (
  token: string,
  sessionId: string,
  data: { content: string; context_type?: string },
) => request<ChatMessagePublic>(`/api/v1/chat/sessions/${sessionId}/messages`, { method: "POST", token, json: data });



