
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

  // Grouped steps with sequential lifecycle gating
  const steps = [
    {
      id: "ingest",
      title: "1. Upload & Quality Pre-Check",
      description: "Antivirus, silence detection & sample rate",
      status: isFailed && progress.quality_check === "failed"
        ? "failed"
        : progress.quality_check === "complete" || isJobDone || ["transcribing", "analyzing", "planning", "generating", "guarding", "translating", "pending_review", "ready_to_publish"].includes(jobStatus)
        ? "complete"
        : jobStatus === "validating" || progress.quality_check === "running"
        ? "running"
        : "queued",
      icon: "🛡️",
    },
    {
      id: "transcribe",
      title: "2. Source Transcription",
      description: transcriptConfidence
        ? `Confidence: ${transcriptConfidence.toUpperCase()} ${avgConfidence ? `(${(avgConfidence * 100).toFixed(0)}%)` : ""}`
        : "VideoDB speech-to-text & timestamp indexing",
      status:
        isJobDone || ["analyzing", "planning", "generating", "guarding", "translating", "pending_review", "ready_to_publish"].includes(jobStatus) || progress.topic_extraction === "complete"
          ? "complete"
          : jobStatus === "transcribing"
          ? "running"
          : "queued",
      icon: "🎙️",
    },
    {
      id: "analysis",
      title: "3. 4-Agent Intelligence Fan-Out",
      description: "Topics, Highlights, Speaker Roles & Sentiment",
      status:
        isJobDone || ["planning", "generating", "guarding", "translating", "pending_review", "ready_to_publish"].includes(jobStatus) || (progress.topic_extraction === "complete" && progress.highlight_detection === "complete")
          ? "complete"
          : jobStatus === "analyzing" || progress.topic_extraction === "running"
          ? "running"
          : "queued",
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
      title: "4. Editorial Brief & Planning",
      description: "Synthesis of key takeaways & editorial structure",
      status:
        isJobDone || ["generating", "guarding", "translating", "pending_review", "ready_to_publish"].includes(jobStatus) || progress.content_planner === "complete"
          ? "complete"
          : jobStatus === "planning" || progress.content_planner === "running"
          ? "running"
          : "queued",
      icon: "📐",
    },
    {
      id: "generator",
      title: "5. Multi-Format Generation",
      description: "Gemini LLM generation for requested asset types",
      status:
        isJobDone || ["guarding", "translating", "pending_review", "ready_to_publish"].includes(jobStatus) || progress.generator === "complete"
          ? "complete"
          : jobStatus === "generating" || progress.generator === "running"
          ? "running"
          : "queued",
      icon: "✨",
    },
    {
      id: "guardrail",
      title: "6. Guardrails & Grounding",
      description: "Moderation & hallucination verification",
      status:
        isJobDone || ["translating", "pending_review", "ready_to_publish"].includes(jobStatus) || progress.guardrail === "complete"
          ? "complete"
          : jobStatus === "guarding" || progress.guardrail === "running"
          ? "running"
          : "queued",
      icon: "🔒",
    },
    {
      id: "translation",
      title: "7. Multi-Language Translation",
      description: "Target languages translation pass",
      status:
        isJobDone || ["pending_review", "ready_to_publish"].includes(jobStatus) || progress.translation === "complete"
          ? "complete"
          : jobStatus === "translating" || progress.translation === "running"
          ? "running"
          : "queued",
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
    <div className={`glass p-21 sm:p-34 ${className}`}>
      <div className="mb-21 flex flex-wrap items-center justify-between gap-13">
        <div>
          <h3 className="font-display text-h2 text-ink">Pipeline</h3>
          <p className="mt-[4px] text-sm text-ink-dim">Eight stages from upload to your approval.</p>
        </div>
        <div className="flex items-center gap-8">
          <span
            className={`rounded-full px-13 py-[2px] text-xs font-semibold ${
              jobStatus === "ready_to_publish"
                ? "bg-success/15 text-success border border-success/30"
                : jobStatus === "pending_review"
                ? "bg-amber-400/15 text-amber-300 border border-amber-400/30"
                : isFailed
                ? "bg-danger/15 text-danger border border-danger/30"
                : "bg-white/[0.06] text-ink border border-white/[0.12]"
            }`}
          >
            {jobStatus === "pending_review" ? "Awaiting review" : jobStatus === "ready_to_publish" ? "Ready to publish" : jobStatus.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      <div className="grid auto-rows-fr gap-13 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((s) => {
          const isDone = s.status === "complete";
          const isRunning = s.status === "running";
          const isStepFailed = s.status === "failed";

          return (
            <div
              key={s.id}
              className={`relative flex flex-col justify-between rounded-card border p-13 transition-all ${
                isRunning
                  ? "stage-live border-amber-400/70 bg-amber-400/[0.06]"
                  : isDone
                  ? "border-white/[0.08] bg-white/[0.02]"
                  : isStepFailed
                  ? "border-danger/40 bg-danger/[0.04]"
                  : "border-dashed border-white/[0.1] text-ink-dim"
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-8">
                  <span className="text-base">{s.icon}</span>
                  <span
                    className={`rounded-full px-8 py-1 text-[10px] font-semibold ${
                      isRunning
                        ? "bg-amber-400/20 text-amber-300"
                        : isDone
                        ? "bg-success/15 text-success"
                        : isStepFailed
                        ? "bg-danger/20 text-danger"
                        : "bg-white/10 text-ink-dim"
                    }`}
                  >
                    {isRunning ? "In progress" : isDone ? "Done" : isStepFailed ? "Failed" : "Waiting"}
                  </span>
                </div>
                <h4 className="font-sans text-sm font-semibold text-ink">
                  {s.title}
                </h4>
                <p className="mt-[4px] text-xs leading-snug text-ink-dim">
                  {s.description}
                </p>
              </div>

              {s.subAgents && (
                <div className="mt-13 flex flex-wrap gap-[4px]">
                  {s.subAgents.map((sa) => (
                    <span
                      key={sa.name}
                      className={`rounded-full px-8 py-[2px] text-[11px] ${
                        sa.status === "complete"
                          ? "bg-success/20 text-success"
                          : sa.status === "running"
                          ? "bg-amber-400/20 text-amber-300"
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

