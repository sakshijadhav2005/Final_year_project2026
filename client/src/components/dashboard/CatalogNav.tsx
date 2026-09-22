import { Link, useLocation } from "react-router-dom";

export function CatalogNav() {
  const location = useLocation();

  const sections = [
    { name: "All Catalogs", path: "/catalog/all", icon: "🌐", badge: "Live" },
    { name: "Meetups", path: "/catalog/meetup", icon: "👥", badge: "Network" },
    { name: "Conferences & Events", path: "/catalog/event", icon: "🎪", badge: "Keynote" },
    { name: "Speeches & Talks", path: "/catalog/speech", icon: "🎤", badge: "Sessions" },
  ];

  return (
    <div className="mb-8 rounded-2xl border border-white/10 bg-slate-900/60 p-4 shadow-xl backdrop-blur-xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Browse Event Catalogs
            </h3>
          </div>
          <p className="text-sm font-medium text-slate-200">
            Explore curated event sessions, talk transcripts & AI-generated content
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {sections.map((s) => {
            const isActive = location.pathname === s.path;
            return (
              <Link
                key={s.name}
                to={s.path}
                className={`group relative inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition-all duration-200 ${
                  isActive
                    ? "bg-gradient-to-r from-amber-500/20 via-orange-500/20 to-rose-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_15px_rgba(245,158,11,0.2)]"
                    : "border border-white/5 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10 hover:text-white"
                }`}
              >
                <span className="text-sm transition-transform group-hover:scale-110">{s.icon}</span>
                <span>{s.name}</span>
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                    isActive ? "bg-amber-400/20 text-amber-200" : "bg-white/10 text-slate-400"
                  }`}
                >
                  {s.badge}
                </span>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
