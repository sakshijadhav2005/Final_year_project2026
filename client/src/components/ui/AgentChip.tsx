type Props = {
  label: string;
  status: string;
};

const styles: Record<string, string> = {
  queued: "bg-white/5 text-ink-dark/70",
  running: "bg-accent/15 text-accent ring-1 ring-accent/40",
  complete: "bg-success/15 text-success",
  failed: "bg-danger/15 text-danger",
  skipped: "bg-white/5 text-ink-dark/50",
};

export function AgentChip({ label, status }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-8 rounded-full px-13 py-8 text-sm ${styles[status] ?? styles.queued}`}
    >
      <span
        className={`h-8 w-8 rounded-full ${
          status === "running" ? "bg-accent animate-pulse" : "bg-current opacity-70"
        }`}
      />
      {label}
      <span className="capitalize opacity-80">{status}</span>
    </span>
  );
}
