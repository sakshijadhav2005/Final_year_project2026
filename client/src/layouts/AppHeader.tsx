import { NavLink } from "react-router-dom";

import { NeuSwitch } from "@/components/ui/NeuSwitch";
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
        { to: "/community", label: "Community" },
        { to: "/settings", label: "Settings" },
        ...(user.role === "admin" ? [{ to: "/admin", label: "Admin" }] : []),
      ]
    : [
        { to: "/", label: "Home" },
        { to: "/login", label: "Sign in" },
      ];

  return (
    <header className="sticky top-0 z-30 backdrop-blur-md">
      {/* Same container + gutters as the page body so the logo lines up with content */}
      <div className="mx-auto flex h-[68px] w-full max-w-7xl items-center justify-between gap-21 px-21 sm:px-34">
        <NavLink to="/" className="flex items-center gap-13">
          <div className="orbit-icon">
            <div className="ring" />
            <div className="core" />
          </div>
          <span className="font-display text-[20px] font-semibold tracking-[-0.01em] text-ink">EventAI</span>
        </NavLink>

        <nav className="flex items-center gap-8 sm:gap-13">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                `${link.to === "/dashboard" ? "inline-flex" : "hidden sm:inline-flex"} rounded-full px-13 py-8 text-sm transition-colors ${
                  isActive
                    ? "neu-pressed bg-white/[0.03] font-medium text-ink"
                    : "text-ink-dim hover:text-ink"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}

          {user ? (
            <button
              type="button"
              className="rounded-full px-13 py-8 text-sm text-ink-dim transition-colors hover:text-danger"
              onClick={clear}
            >
              Sign out
            </button>
          ) : (
            <NavLink
              to="/register"
              className="rounded-full bg-amber-400 px-21 py-8 text-sm font-semibold text-on-accent transition-colors hover:bg-amber-300"
            >
              Create account
            </NavLink>
          )}

          <NeuSwitch
            checked={theme === "dark"}
            onChange={toggleTheme}
            ariaLabel={theme === "dark" ? "Dark theme on. Switch to light theme" : "Light theme on. Switch to dark theme"}
            offIcon={
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                <circle cx="12" cy="12" r="4.5" />
                <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.5 1.5M17.2 17.2l1.5 1.5M5.3 18.7l1.5-1.5M17.2 6.8l1.5-1.5" />
              </svg>
            }
            onIcon={
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />
              </svg>
            }
          />
        </nav>
      </div>
    </header>
  );
}
