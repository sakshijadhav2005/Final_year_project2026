const API_BASE = import.meta.env.VITE_API_URL ?? "";

export type UserRole = "admin" | "content_creator" | "event_organizer" | "regular_user";

export type EventType = "meetup" | "event" | "speech" | "other";

export type EventPublic = {
  id: string;
  name: string;
  date: string;
  topic?: string | null;
  organizer_name?: string | null;
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
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...authHeaders(token),
      ...(headers ?? {}),
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
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
    throw new Error(message);
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
export const listJobs = (token: string) => request<JobPublic[]>("/api/v1/jobs", { token });
export const getJob = (token: string, id: string) => request<JobPublic>(`/api/v1/jobs/${id}`, { token });
export const getTranscript = (token: string, id: string) =>
  request<TranscriptPublic>(`/api/v1/jobs/${id}/transcript`, { token });
export const getJobContent = (token: string, id: string) =>
  request<ContentPublic[]>(`/api/v1/jobs/${id}/content`, { token });
export const approveContent = (token: string, id: string) =>
  request<ContentPublic>(`/api/v1/content/${id}/approve`, { method: "POST", token });
export const rejectContent = (token: string, id: string, reason: string) =>
  request<ContentPublic>(`/api/v1/content/${id}/reject`, { method: "POST", token, json: { reason } });
export const listAdminJobs = (token: string) => request<JobPublic[]>("/api/v1/admin/jobs", { token });
export const listAudit = (token: string) => request<Record<string, string | null>[]>("/api/v1/admin/audit", { token });

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
  const res = await fetch(`${API_BASE}/api/v1/content/${contentId}/download?format=${format}`, {
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

export const listEvents = (token: string, type?: EventType) =>
  request<EventPublic[]>(`/api/v1/events${type ? `?type=${type}` : ""}`, { token });

export const getEvent = (token: string, id: string) =>
  request<EventPublic>(`/api/v1/events/${id}`, { token });

export const createEvent = (
  token: string,
  data: { name: string; date: string; topic?: string; organizer_name?: string; type?: EventType },
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



