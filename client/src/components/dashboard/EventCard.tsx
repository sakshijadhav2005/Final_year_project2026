import { Link } from "react-router-dom";
import type { EventPublic } from "@/lib/api";
import { getEventCity, getCityBadge } from "@/lib/eventLocation";

type EventCardProps = {
  event: EventPublic;
  onSelect?: (event: EventPublic) => void;
  selected?: boolean;
};

const TYPE_CONFIG: Record<string, { label: string; icon: string; badgeClass: string }> = {
  meetup: {
    label: "Meetup",
    icon: "👥",
    badgeClass: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  },
  event: {
    label: "Event",
    icon: "🎪",
    badgeClass: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  },
  speech: {
    label: "Speech",
    icon: "🎤",
    badgeClass: "bg-sky-500/20 text-sky-300 border-sky-500/30",
  },
  other: {
    label: "Session",
    icon: "📌",
    badgeClass: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  },
};

export function EventCard({ event, onSelect, selected = false }: EventCardProps) {
  const config = TYPE_CONFIG[event.type] ?? TYPE_CONFIG.other;
  const detectedCity = getEventCity(event);
  const cityBadge = detectedCity ? getCityBadge(detectedCity) : null;

  const formattedDate = new Date(event.date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div
      onClick={() => onSelect?.(event)}
      className={`group relative flex flex-col justify-between overflow-hidden rounded-2xl border p-6 shadow-xl backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 ${
        selected
          ? "border-amber-400 bg-slate-900/90 ring-2 ring-amber-400/50 shadow-amber-500/20"
          : "border-white/10 bg-slate-900/60 hover:border-white/20 hover:shadow-2xl hover:shadow-amber-500/10 cursor-pointer"
      }`}
    >
      <div className="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-gradient-to-br from-amber-500/10 via-purple-500/5 to-transparent blur-xl transition-all duration-300 group-hover:scale-150" />

      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${config.badgeClass}`}
            >
              <span>{config.icon}</span>
              <span>{config.label}</span>
            </span>

            {cityBadge && (
              <span className="inline-flex items-center gap-1 rounded-full border border-gold/30 bg-gold/10 px-2.5 py-1 text-xs font-medium text-gold dark:text-gold-soft">
                <span>{cityBadge.icon}</span>
                <span>{cityBadge.label}</span>
              </span>
            )}
          </div>

          <span className="text-xs font-medium text-slate-400">📅 {formattedDate}</span>
        </div>

        <h3 className="text-lg font-bold text-white transition-colors group-hover:text-amber-300">
          {event.name}
        </h3>

        {event.topic && (
          <p className="mt-2 text-sm text-slate-300 line-clamp-2">
            💡 <span className="text-slate-400 font-medium">Topic:</span> {event.topic}
          </p>
        )}

        <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/10 text-[10px] font-bold text-slate-200">
            {event.organizer_name ? event.organizer_name[0].toUpperCase() : "O"}
          </span>
          <span>Organized by <strong className="text-slate-200 font-semibold">{event.organizer_name || "Organizer"}</strong></span>
        </div>
      </div>

      <div className="mt-6 flex items-center gap-2 pt-4 border-t border-white/5">
        <Link
          to={`/events/${event.id}`}
          className="inline-flex flex-1 items-center justify-center gap-1 rounded-xl bg-gradient-to-r from-amber-500/20 to-orange-500/20 border border-amber-500/30 px-3 py-2 text-xs font-semibold text-amber-300 transition-all hover:bg-amber-500/30"
        >
          <span>🎙️ Event Hub &amp; Transcript</span>
        </Link>

        <Link
          to={`/community?event_id=${event.id}`}
          className="inline-flex items-center justify-center gap-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-slate-300 transition-all hover:border-white/20 hover:text-white"
          title="Community Discussions"
        >
          <span>💬</span>
        </Link>

        {onSelect && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(event);
            }}
            className={`inline-flex items-center justify-center rounded-xl px-3 py-2 text-xs font-semibold transition-all ${
              selected
                ? "bg-amber-400 text-slate-950 font-bold shadow-sm"
                : "bg-amber-500/20 text-amber-300 hover:bg-amber-500/30"
            }`}
          >
            {selected ? "✓ Active" : "Select"}
          </button>
        )}
      </div>

    </div>
  );
}
