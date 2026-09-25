interface StatsGridProps {
  eventsCount: number;
  totalSessions: number;
  activeProcessingCount: number;
  pipelineStatus: "Active" | "Ready";
  isLoading?: boolean;
}

export function StatsGrid({
  eventsCount,
  totalSessions,
  activeProcessingCount,
  pipelineStatus,
  isLoading = false,
}: StatsGridProps) {
  const stats = [
    {
      label: "Managed Events",
      value: isLoading ? "—" : eventsCount,
      icon: "🎪",
      subtitle: "Live catalogs & conferences",
      badge: null,
      badgeClass: "",
    },
    {
      label: "Recording Sessions",
      value: isLoading ? "—" : totalSessions,
      icon: "🎙️",
      subtitle: "Ingested audio & video runs",
      badge: null,
      badgeClass: "",
    },
    {
      label: "Active Processing",
      value: isLoading ? "—" : activeProcessingCount,
      icon: "⚡",
      subtitle:
        activeProcessingCount > 0
          ? "Currently queued or generating"
          : "No active pipeline jobs",
      badge: activeProcessingCount > 0 ? "In flight" : null,
      badgeClass:
        "rounded-full border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300",
    },
    {
      label: "Pipeline Status",
      value: pipelineStatus,
      icon: "🚀",
      subtitle:
        pipelineStatus === "Active"
          ? "Generating drafts & transcripts"
          : "Standby • Ready for ingestion",
      badge: pipelineStatus === "Active" ? "Active" : "Ready",
      badgeClass:
        pipelineStatus === "Active"
          ? "rounded-full border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300 animate-pulse"
          : "rounded-full border border-teal/30 bg-teal/15 px-2 py-0.5 text-[10px] font-semibold text-teal",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-13 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-card border border-gold/20 bg-surface-light p-21 shadow-sm backdrop-blur-xl dark:border-gold/20 dark:bg-surface-dark transition-all hover:border-gold/40"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-light/60 dark:text-ink-dim">
              {stat.label}
            </span>
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gold/10 border border-gold/20 text-sm">
              {stat.icon}
            </span>
          </div>

          <div className="mt-13 flex items-baseline gap-2">
            <span className="font-display text-2xl font-semibold text-ink-light dark:text-ink-dark">
              {stat.value}
            </span>
            {stat.badge && <span className={stat.badgeClass}>{stat.badge}</span>}
          </div>

          <p className="mt-4 text-xs text-ink-light/60 dark:text-ink-dim">
            {stat.subtitle}
          </p>
        </div>
      ))}
    </div>
  );
}
