import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { GoldenShell } from "@/layouts/GoldenShell";
import { getApiHealth, getReady } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useThemeStore } from "@/store/theme";

export function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const health = useQuery({ queryKey: ["api-health"], queryFn: getApiHealth });
  const ready = useQuery({ queryKey: ["ready"], queryFn: getReady });

  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);

  const [retentionHours, setRetentionHours] = useState("72");
  const [selectedLangs, setSelectedLangs] = useState<string[]>(["en", "hi"]);
  const [savedMsg, setSavedMsg] = useState(false);

  function handleSave() {
    setSavedMsg(true);
    setTimeout(() => setSavedMsg(false), 2500);
  }

  function toggleLang(lang: string) {
    if (selectedLangs.includes(lang)) {
      if (selectedLangs.length > 1) {
        setSelectedLangs(selectedLangs.filter((l) => l !== lang));
      }
    } else {
      setSelectedLangs([...selectedLangs, lang]);
    }
  }

  return (
    <GoldenShell>
      <div className="max-w-3xl mx-auto">
        <div className="mb-21 flex items-center justify-between">
          <div>
            <h1 className="font-display text-h1 font-semibold text-ink-light dark:text-ink-dark">
              Workspace Settings
            </h1>
          </div>
          <Link
            to="/dashboard"
            className="btn-ghost btn-sm"
          >
            ← Dashboard
          </Link>
        </div>

      {savedMsg && (
        <div className="mb-21 rounded-card bg-success/20 p-13 text-xs font-medium text-success">
          ✓ Settings saved successfully!
        </div>
      )}

      <div className="space-y-34 max-w-2xl">
        {/* Account Info */}
        <section className="rounded-card border border-black/10 bg-surface-light p-21 dark:border-white/[0.08] dark:bg-surface-dark dark:shadow-none">
          <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Account & Role</h3>
          <div className="mt-13 grid grid-cols-2 gap-13 text-xs">
            <div>
              <span className="text-ink-light/50 dark:text-ink-dim block">Logged in as:</span>
              <span className="font-medium text-ink-light dark:text-ink-dark">{user?.email || "user@example.com"}</span>
            </div>
            <div>
              <span className="text-ink-light/50 dark:text-ink-dim block">Assigned Role:</span>
              <span className="font-semibold text-ink">{user?.role?.replace("_", " ") || "Organizer"}</span>
            </div>
          </div>
        </section>

        {/* Theme Settings */}
        <section className="rounded-card border border-black/10 bg-surface-light p-21 dark:border-white/[0.08] dark:bg-surface-dark dark:shadow-none">
          <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Appearance & Design System</h3>
          <p className="mt-[4px] text-xs text-ink-light/50 dark:text-ink-dim">Velvet stage palette on a golden-ratio grid</p>

          <div className="mt-13 flex gap-13">
            <button
              type="button"
              onClick={() => setTheme("dark")}
              className={`flex items-center gap-8 rounded-card border px-21 py-13 text-xs font-medium transition-all ${
                theme === "dark"
                  ? "border-amber-400/60 bg-amber-400/[0.08] text-ink"
                  : "border-black/10 text-ink-light/70 hover:border-black/30 dark:border-white/[0.08] dark:text-ink-dim dark:hover:border-white/30"
              }`}
            >
              🌙 Dark Mode (Default)
            </button>
            <button
              type="button"
              onClick={() => setTheme("light")}
              className={`flex items-center gap-8 rounded-card border px-21 py-13 text-xs font-medium transition-all ${
                theme === "light"
                  ? "border-amber-400/60 bg-amber-400/[0.08] text-ink"
                  : "border-black/10 text-ink-light/70 hover:border-black/30 dark:border-white/[0.08] dark:text-ink-dim dark:hover:border-white/30"
              }`}
            >
              ☀️ Light Mode
            </button>
          </div>
        </section>

        {/* Media Retention Settings */}
        <section className="rounded-card border border-black/10 bg-surface-light p-21 dark:border-white/[0.08] dark:bg-surface-dark dark:shadow-none">
          <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Privacy & Media Retention</h3>
          <p className="mt-[4px] text-xs text-ink-light/50 dark:text-ink-dim">
            Automatically purge original media files from disk after processing to ensure participant privacy.
          </p>

          <div className="mt-13">
            <select
              value={retentionHours}
              onChange={(e) => setRetentionHours(e.target.value)}
              className="w-full max-w-xs rounded-card border border-black/10 bg-canvas-light p-13 text-xs text-ink-light dark:border-white/[0.08] dark:bg-canvas-dark dark:text-ink-dark"
            >
              <option value="24">Purge after 24 Hours</option>
              <option value="72">Purge after 72 Hours (Default)</option>
              <option value="168">Purge after 7 Days</option>
              <option value="0">Retain indefinitely</option>
            </select>
          </div>
        </section>

        {/* Default Translation Languages */}
        <section className="rounded-card border border-black/10 bg-surface-light p-21 dark:border-white/[0.08] dark:bg-surface-dark dark:shadow-none">
          <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Default Target Languages</h3>
          <p className="mt-[4px] text-xs text-ink-light/50 dark:text-ink-dim">
            Selected languages will automatically be translated by Gemini after guardrail approval.
          </p>

          <div className="mt-13 flex flex-wrap gap-8">
            {[
              { code: "en", name: "English" },
              { code: "hi", name: "Hindi" },
              { code: "es", name: "Spanish" },
              { code: "fr", name: "French" },
              { code: "de", name: "German" },
              { code: "ja", name: "Japanese" },
            ].map((lang) => {
              const active = selectedLangs.includes(lang.code);
              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => toggleLang(lang.code)}
                  className={`rounded-card border px-13 py-8 text-xs font-medium transition-all ${
                    active
                      ? "border-amber-400/60 bg-amber-400/[0.08] text-ink"
                      : "border-black/10 text-ink-light/70 hover:text-ink-light hover:border-black/30 dark:border-white/[0.08] dark:text-ink-dim dark:hover:text-ink-dark dark:hover:border-white/30"
                  }`}
                >
                  {active ? "✓ " : "+ "}
                  {lang.name}
                </button>
              );
            })}
          </div>
        </section>

        {/* System Diagnostics */}
        <section className="rounded-card border border-black/10 bg-surface-light p-21 dark:border-white/[0.08] dark:bg-surface-dark dark:shadow-none">
          <h3 className="font-semibold text-gold mb-13 text-sm">System Diagnostics &amp; Health</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-13">
            <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
              <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">API Gateway</span>
              <span className="font-semibold text-teal">{health.data?.status ?? "online"}</span>
            </div>
            <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
              <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">API Version</span>
              <span className=" text-gold dark:text-gold-soft">{health.data?.version ?? "0.1.0"}</span>
            </div>
            <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
              <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">PostgreSQL Database</span>
              <span className="font-semibold text-teal">{ready.data?.checks.postgres ?? "connected"}</span>
            </div>
            <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
              <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">Redis Job Broker</span>
              <span className="font-semibold text-teal">{ready.data?.checks.redis ?? "connected"}</span>
            </div>
          </div>
        </section>

        {/* Save Button */}
        <div>
          <button
            type="button"
            onClick={handleSave}
            className="btn-primary py-13"
          >
            Save preferences
          </button>
        </div>
      </div>
    </div>
    </GoldenShell>
  );
}
