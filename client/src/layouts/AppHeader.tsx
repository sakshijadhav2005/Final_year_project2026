import { NavLink } from "react-router-dom";

import { useAuthStore } from "@/store/auth";
import { useThemeStore } from "@/store/theme";

export function AppHeader() {
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const theme = useThemeStore((s) => s.theme);
  const user = useAuthStore((s) => s.user);
  const clear = useAuthStore((s) => s.clear);

  const links = user
    ? [
        { to: "/", label: "Upload" },
        { to: "/dashboard", label: "Dashboard" },
        { to: "/settings", label: "Settings" },
        ...(user.role === "admin" ? [{ to: "/admin", label: "Admin" }] : []),
      ]
    : [
        { to: "/", label: "Studio" },
        { to: "/login", label: "Sign In" },
        { to: "/register", label: "Join" },
      ];

  return (
    <header className="relative z-20 flex items-center justify-between border-b border-black/5 dark:border-[#D8B478]/15 px-34 py-21 backdrop-blur-md bg-white/70 dark:bg-transparent">
      {/* Brand with Orbiting Icon */}
      <NavLink to="/" className="flex items-center gap-13 group">
        <div className="orbit-icon">
          <div className="ring" />
          <div className="core" />
        </div>
        <span className="font-display text-xl font-medium tracking-wide text-ink-light transition-colors group-hover:text-gold dark:text-ink-dark dark:group-hover:text-gold-soft">
          EventAI
        </span>
      </NavLink>

      {/* Center / Right Controls */}
      <div className="flex items-center gap-21">
        {/* Live Session Equalizer Indicator */}
        <div className="hidden items-center gap-8 rounded-full border border-black/10 dark:border-[#D8B478]/25 bg-black/[0.02] dark:bg-white/[0.04] px-13 py-4 text-xs tracking-wider text-gold dark:text-gold-soft sm:flex">
          <span className="live-bars">
            <span />
            <span />
            <span />
          </span>
          <span className="text-[11px] font-medium uppercase">Session Live</span>
        </div>

        {/* Navigation Links */}
        <nav className="flex items-center gap-13 sm:gap-21">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                `text-xs uppercase tracking-widest transition-all ${
                  isActive
                    ? "font-semibold text-gold dark:text-gold-soft"
                    : "text-ink-light/70 hover:text-ink-light dark:text-ink-dim dark:hover:text-ink-dark"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}

          {user && (
            <button
              type="button"
              className="text-xs uppercase tracking-widest text-ink-light/70 hover:text-danger dark:text-ink-dim dark:hover:text-danger"
              onClick={clear}
            >
              Sign Out
            </button>
          )}

          {/* Theme Toggle Button */}
          <button
            type="button"
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-black/10 dark:border-[#D8B478]/20 bg-black/[0.03] dark:bg-white/[0.04] text-xs text-gold dark:text-gold-soft transition-all hover:scale-110 hover:border-gold/50 dark:hover:border-[#D8B478]/50"
            title="Toggle theme"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </nav>
      </div>
    </header>
  );
}
