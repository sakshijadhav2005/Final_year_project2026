import type { AgentStatus } from "@/types/pipeline";

type Props = {
  progress?: Record<string, string>;
  jobStatus?: string;
  transcriptConfidence?: "high" | "medium" | "low" | null;
  avgConfidence?: number | null;
  className?: string;
};

export function PipelineStepper({
  progress = {},
  jobStatus = "queued",
  transcriptConfidence,
  avgConfidence,
  className = "",
}: Props) {
  // Determine overall status for grouped steps
  const isJobDone = ["pending_review", "ready_to_publish"].includes(jobStatus);
  const isFailed = ["failed", "needs_reupload"].includes(jobStatus);

  // Grouped steps
  const steps = [
    {
      id: "ingest",
      title: "1. Upload & Quality Pre-Check",
      description: "Antivirus, silence detection & sample rate",
      status: getStepStatus([progress.quality_check], jobStatus, isJobDone, isFailed),
      icon: "🛡️",
    },
    {
      id: "transcribe",
      title: "2. Source Transcription",
      description: transcriptConfidence
        ? `Confidence: ${transcriptConfidence.toUpperCase()} ${avgConfidence ? `(${(avgConfidence * 100).toFixed(0)}%)` : ""}`
        : "VideoDB speech-to-text & timestamp indexing",
      status:
        transcriptConfidence || progress.topic_extraction || isJobDone
          ? "complete"
          : jobStatus === "validating"
          ? "running"
          : "queued",
      icon: "🎙️",
    },
    {
      id: "analysis",
      title: "3. 4-Agent Intelligence Fan-Out",
      description: "Topics, Highlights, Speaker Roles & Sentiment",
      status: getStepStatus(
        [
          progress.topic_extraction,
          progress.highlight_detection,
          progress.speaker_analysis,
          progress.sentiment_analysis,
        ],
        jobStatus,
        isJobDone,
        isFailed,
      ),
      icon: "🧠",
      subAgents: [
        { name: "Topics", status: progress.topic_extraction },
        { name: "Highlights", status: progress.highlight_detection },
        { name: "Speakers", status: progress.speaker_analysis },
        { name: "Sentiment", status: progress.sentiment_analysis },
      ],
    },
    {
      id: "planner",
      title: "4. Content Planner & RAG Gate",
      description: "Brief synthesis & context augmentation",
      status: getStepStatus([progress.content_planner, progress.rag_retrieve], jobStatus, isJobDone, isFailed),
      icon: "📐",
    },
    {
      id: "generator",
      title: "5. Multi-Format Generation",
      description: "Gemini LLM generation for requested asset types",
      status: getStepStatus([progress.generator], jobStatus, isJobDone, isFailed),
      icon: "✨",
    },
    {
      id: "guardrail",
      title: "6. Guardrails & Grounding",
      description: "Moderation & hallucination verification",
      status: getStepStatus([progress.guardrail], jobStatus, isJobDone, isFailed),
      icon: "🔒",
    },
    {
      id: "translation",
      title: "7. Multi-Language Translation",
      description: "Target languages translation pass",
      status: getStepStatus([progress.translation], jobStatus, isJobDone, isFailed),
      icon: "🌐",
    },
    {
      id: "review",
      title: "8. Human Review & Publish",
      description:
        jobStatus === "ready_to_publish"
          ? "All assets approved for publishing"
          : jobStatus === "pending_review"
          ? "Ready for human editorial review & sign-off"
          : "Awaits agent pipeline completion",
      status:
        jobStatus === "ready_to_publish"
          ? "complete"
          : jobStatus === "pending_review"
          ? "running"
          : "queued",
      icon: "✍️",
    },
  ];

  return (
    <div className={`glass p-21 border-gold/20 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-8 mb-13 border-b border-[#D8B478]/15 pb-13">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-gold">AI Execution Pipeline</span>
          <h3 className="font-display text-lg text-ink-light dark:text-ink-dark">
            End-to-End Workflow Progression
          </h3>
        </div>
        <div className="flex items-center gap-8">
          <span
            className={`rounded-full px-13 py-2 text-xs font-semibold uppercase tracking-wider ${
              jobStatus === "ready_to_publish"
                ? "bg-success/15 text-success border border-success/30"
                : jobStatus === "pending_review"
                ? "bg-gold/15 text-gold-soft border border-gold/30 animate-pulse"
                : isFailed
                ? "bg-danger/15 text-danger border border-danger/30"
                : "bg-teal/15 text-teal border border-teal/30 animate-pulse"
            }`}
          >
            {jobStatus.replace("_", " ")}
          </span>
        </div>
      </div>

      <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((s) => {
          const isDone = s.status === "complete";
          const isRunning = s.status === "running";
          const isStepFailed = s.status === "failed";

          return (
            <div
              key={s.id}
              className={`relative flex flex-col justify-between rounded-card border p-13 transition-all ${
                isRunning
                  ? "border-gold bg-gold/10 shadow-[0_0_15px_rgba(216,180,120,0.2)]"
                  : isDone
                  ? "border-success/30 bg-success/[0.04]"
                  : isStepFailed
                  ? "border-danger/40 bg-danger/[0.04]"
                  : "border-white/5 bg-white/[0.02] opacity-70"
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-8">
                  <span className="text-base">{s.icon}</span>
                  <span
                    className={`rounded-full px-8 py-1 text-[10px] font-semibold uppercase tracking-wider ${
                      isRunning
                        ? "bg-gold/20 text-gold-soft animate-pulse"
                        : isDone
                        ? "bg-success/20 text-success"
                        : isStepFailed
                        ? "bg-danger/20 text-danger"
                        : "bg-white/10 text-ink-dim"
                    }`}
                  >
                    {isRunning ? "In Progress" : isDone ? "Done ✓" : isStepFailed ? "Failed" : "Pending"}
                  </span>
                </div>
                <h4 className="font-sans text-xs font-semibold text-ink-light dark:text-ink-dark">
                  {s.title}
                </h4>
                <p className="mt-4 text-[11px] leading-snug text-ink-dim">
                  {s.description}
                </p>
              </div>

              {s.subAgents && (
                <div className="mt-8 flex flex-wrap gap-4 border-t border-white/5 pt-8">
                  {s.subAgents.map((sa) => (
                    <span
                      key={sa.name}
                      className={`rounded px-4 py-1 text-[9px] font-mono ${
                        sa.status === "complete"
                          ? "bg-success/20 text-success"
                          : sa.status === "running"
                          ? "bg-gold/20 text-gold-soft animate-pulse"
                          : "bg-white/5 text-ink-dim"
                      }`}
                    >
                      {sa.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function getStepStatus(
  statuses: (string | undefined)[],
  _jobStatus: string,
  isJobDone: boolean,
  isFailed: boolean,
): AgentStatus {
  if (isFailed) {
    if (statuses.some((s) => s === "failed")) return "failed";
  }
  if (isJobDone) return "complete";
  if (statuses.some((s) => s === "running")) return "running";
  if (statuses.every((s) => s === "complete")) return "complete";
  if (statuses.some((s) => s === "complete")) return "running";
  if (statuses.some((s) => s === "failed")) return "failed";
  return "queued";
}
