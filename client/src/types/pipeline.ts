export const AGENT_NAMES = [
  "quality_check",
  "topic_extraction",
  "highlight_detection",
  "speaker_analysis",
  "sentiment_analysis",
  "content_planner",
  "generator",
  "guardrail",
  "translation",
] as const;

export type AgentName = (typeof AGENT_NAMES)[number];
export type AgentStatus = "queued" | "running" | "complete" | "failed" | "skipped";
