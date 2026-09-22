type Level = "high" | "medium" | "low";

const map: Record<Level, { className: string; label: string }> = {
  high: { className: "text-success bg-success/10", label: "High confidence" },
  medium: { className: "text-warning bg-warning/10", label: "Medium confidence" },
  low: { className: "text-danger bg-danger/10", label: "Low confidence" },
};

export function ConfidenceBadge({ level }: { level: Level }) {
  const item = map[level];
  return (
    <span className={`rounded-full px-13 py-8 text-sm ${item.className}`}>{item.label}</span>
  );
}
