import { Link, useLocation } from "react-router-dom";

const SECTIONS = [
  { name: "All events", path: "/catalog/all", icon: "🌐" },
  { name: "Meetups", path: "/catalog/meetup", icon: "👥" },
  { name: "Conferences", path: "/catalog/event", icon: "🎪" },
  { name: "Talks", path: "/catalog/speech", icon: "🎤" },
];

export function CatalogNav() {
  const location = useLocation();

  return (
    <nav
      aria-label="Event catalogs"
      className="grid grid-cols-1 items-center gap-21 rounded-panel border border-white/[0.08] bg-surface p-21 lg:grid-cols-golden-reverse lg:gap-34"
    >
      {/* 38.2%: what this bar is for */}
      <div className="min-w-0">
        <h2 className="font-display text-h3 font-semibold text-ink">Browse events</h2>
        <p className="mt-[4px] text-sm leading-relaxed text-ink-dim">
          Transcripts and published posts from every recorded session.
        </p>
      </div>

      {/* 61.8%: four equal catalog buttons on one row */}
      <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
        {SECTIONS.map((s) => {
          const isActive = location.pathname === s.path;
          return (
            <Link
              key={s.path}
              to={s.path}
              aria-current={isActive ? "page" : undefined}
              className={`flex h-[55px] items-center justify-center gap-8 rounded-card border px-13 text-sm font-medium transition-colors ${
                isActive
                  ? "neu-pressed border-amber-400/60 bg-amber-400/[0.08] text-ink"
                  : "neu-raised border-white/[0.06] bg-white/[0.02] text-ink-dim hover:text-ink"
              }`}
            >
              <span aria-hidden="true">{s.icon}</span>
              <span className="truncate">{s.name}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
