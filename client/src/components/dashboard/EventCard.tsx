import { Link } from "react-router-dom";
import type { EventPublic } from "@/lib/api";

type EventCardProps = {
  event: EventPublic;
  onSelect?: (event: EventPublic) => void;
};

const TYPE_CONFIG: Record<string, { label: string; icon: string; badgeClass: string }> = {
  meetup: {
    label: "Meetup",
    icon: "👥",
    badgeClass: "bg-amber-400/15 text-amber-300",
  },
  event: {
    label: "Event",
    icon: "🎪",
    badgeClass: "bg-amber-400/15 text-amber-300",
  },
  speech: {
    label: "Speech",
    icon: "🎤",
    badgeClass: "bg-amber-400/15 text-amber-300",
  },
  other: {
    label: "Session",
    icon: "📌",
    badgeClass: "bg-amber-400/15 text-amber-300",
  },
};

export function EventCard({ event, onSelect }: EventCardProps) {
  const config = TYPE_CONFIG[event.type] ?? TYPE_CONFIG.other;

  const formattedDate = new Date(event.date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="glass-interactive group relative flex flex-col justify-between overflow-hidden rounded-panel border border-white/[0.08] bg-surface p-21">

      <div>
        <div className="mb-13 flex items-center justify-between gap-8">
          <span
            className={`inline-flex items-center gap-8 rounded-full border px-8 py-1 text-xs font-semibold ${config.badgeClass}`}
          >
            <span>{config.icon}</span>
            <span>{config.label}</span>
          </span>

          <span className="text-xs font-medium text-slate-400">📅 {formattedDate}</span>
        </div>

        <h3 className="text-lg font-bold text-white transition-colors group-hover:text-amber-300">
          {event.name}
        </h3>

        {event.topic && (
          <p className="mt-8 text-sm text-slate-300 line-clamp-2">
            💡 <span className="text-slate-400 font-medium">Topic:</span> {event.topic}
          </p>
        )}

        <div className="mt-13 flex items-center gap-8 text-xs text-slate-400">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/10 text-[10px] font-bold text-slate-200">
            {event.organizer_name ? event.organizer_name[0].toUpperCase() : "O"}
          </span>
          <span>Organized by <strong className="text-slate-200 font-semibold">{event.organizer_name || "Organizer"}</strong></span>
        </div>
      </div>

      <div className="mt-21 flex items-center gap-8 pt-13 border-t border-white/5">
        <Link
          to={`/events/${event.id}`}
          className="btn-ghost btn-sm flex-1"
        >
          <span>🎙️ Event Hub &amp; Transcript</span>
        </Link>

        <Link
          to={`/community?event_id=${event.id}`}
          className="inline-flex items-center justify-center gap-1 rounded-card border border-white/[0.08] bg-white/5 px-13 py-8 text-xs font-semibold text-slate-300 transition-all hover:border-white/20 hover:text-white"
          title="Community Discussions"
        >
          <span>💬</span>
        </Link>

        {onSelect && (
          <button
            type="button"
            onClick={() => onSelect(event)}
            className="inline-flex items-center justify-center rounded-card bg-amber-500/20 px-13 py-8 text-xs font-semibold text-amber-300 transition-all hover:bg-amber-500/30"
          >
            Select
          </button>
        )}
      </div>

    </div>
  );
}
