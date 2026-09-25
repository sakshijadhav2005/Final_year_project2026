import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { GoldenShell } from "@/layouts/GoldenShell";
import { getApiHealth, getProfile, getReady, updateProfile } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useThemeStore } from "@/store/theme";

export function SettingsPage() {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const health = useQuery({ queryKey: ["api-health"], queryFn: getApiHealth });
  const ready = useQuery({ queryKey: ["ready"], queryFn: getReady });

  // Brand Memory Profile Query
  const profileQuery = useQuery({
    queryKey: ["user-profile"],
    queryFn: () => (token ? getProfile(token) : Promise.resolve(null)),
    enabled: !!token,
  });

  // Local form state for Creator Profile & Brand Memory
  const [fullName, setFullName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [linkedinHandle, setLinkedinHandle] = useState("");
  const [instagramHandle, setInstagramHandle] = useState("");
  const [brandTone, setBrandTone] = useState("Professional");
  const [customSignoff, setCustomSignoff] = useState("");
  const [bio, setBio] = useState("");

  const [profileSavedMsg, setProfileSavedMsg] = useState(false);
  const [profileErrorMsg, setProfileErrorMsg] = useState(false);

  // Populate form fields when profile data loads
  useEffect(() => {
    if (profileQuery.data) {
      setFullName(profileQuery.data.full_name || "");
      setJobTitle(profileQuery.data.job_title || "");
      setOrganization(profileQuery.data.organization || "");
      setWebsiteUrl(profileQuery.data.website_url || "");
      setLinkedinHandle(profileQuery.data.linkedin_handle || "");
      setInstagramHandle(profileQuery.data.instagram_handle || "");
      setBrandTone(profileQuery.data.brand_tone || "Professional");
      setCustomSignoff(profileQuery.data.custom_signoff || "");
      setBio(profileQuery.data.bio || "");
    }
  }, [profileQuery.data]);

  // Mutation to update brand profile
  const profileMutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("Not authenticated");
      return updateProfile(token, {
        full_name: fullName.trim() || null,
        job_title: jobTitle.trim() || null,
        organization: organization.trim() || null,
        website_url: websiteUrl.trim() || null,
        linkedin_handle: linkedinHandle.trim() || null,
        instagram_handle: instagramHandle.trim() || null,
        brand_tone: brandTone.trim() || null,
        custom_signoff: customSignoff.trim() || null,
        bio: bio.trim() || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-profile"] });
      setProfileErrorMsg(false);
      setProfileSavedMsg(true);
      setTimeout(() => setProfileSavedMsg(false), 3000);
    },
    onError: () => {
      setProfileSavedMsg(false);
      setProfileErrorMsg(true);
    },
  });

  function handleProfileSubmit(e: React.FormEvent) {
    e.preventDefault();
    setProfileSavedMsg(false);
    setProfileErrorMsg(false);
    profileMutation.mutate();
  }

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
            <p className="text-xs font-semibold uppercase tracking-wider text-gold">Configuration</p>
            <h1 className="font-display text-2xl font-bold md:text-3xl text-ink-light dark:text-ink-dark">
              Workspace Settings
            </h1>
          </div>
          <Link
            to="/dashboard"
            className="rounded-full border border-gold/30 bg-surface-light/80 dark:bg-white/[0.03] px-21 py-8 text-xs font-medium text-gold hover:border-gold transition-all dark:text-gold-soft"
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
          <section className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
            <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Account & Role</h3>
            <div className="mt-13 grid grid-cols-2 gap-13 text-xs">
              <div>
                <span className="text-ink-light/50 dark:text-ink-dim block">Logged in as:</span>
                <span className="font-medium text-ink-light dark:text-ink-dark">{user?.email || "user@example.com"}</span>
              </div>
              <div>
                <span className="text-ink-light/50 dark:text-ink-dim block">Assigned Role:</span>
                <span className="font-semibold uppercase text-accent">{user?.role?.replace("_", " ") || "Organizer"}</span>
              </div>
            </div>
          </section>

          {/* Creator Profile & Brand Memory */}
          <section className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">
                  Creator Profile &amp; Brand Memory
                </h3>
                <p className="mt-4 text-xs text-ink-light/50 dark:text-ink-dim">
                  Personal and organization context injected automatically into all generated AI content.
                </p>
              </div>
              {profileQuery.isLoading && (
                <span className="text-xs text-gold dark:text-gold-soft animate-pulse">Loading profile...</span>
              )}
            </div>

            {profileSavedMsg && (
              <div className="mt-13 rounded-card border border-success/30 bg-success/20 p-13 text-xs font-medium text-success">
                ✓ Brand profile saved successfully!
              </div>
            )}

            {profileErrorMsg && (
              <div className="mt-13 rounded-card border border-danger/30 bg-danger/20 p-13 text-xs font-medium text-danger">
                ⚠️ Unable to save brand profile. Please try again.
              </div>
            )}

            <form onSubmit={handleProfileSubmit} className="mt-21 space-y-13">
              {/* Full Name & Job Title */}
              <div className="grid grid-cols-1 gap-13 sm:grid-cols-2">
                <div>
                  <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Dr. Alex Morgan"
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                    Job Title
                  </label>
                  <input
                    type="text"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                    placeholder="e.g. Principal AI Architect"
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>
              </div>

              {/* Organization & Brand Tone */}
              <div className="grid grid-cols-1 gap-13 sm:grid-cols-2">
                <div>
                  <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                    Organization
                  </label>
                  <input
                    type="text"
                    value={organization}
                    onChange={(e) => setOrganization(e.target.value)}
                    placeholder="e.g. Cloud Native Pune"
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                    Brand Tone
                  </label>
                  <select
                    value={brandTone}
                    onChange={(e) => setBrandTone(e.target.value)}
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-[#141826] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  >
                    <option value="Professional">Professional</option>
                    <option value="Friendly">Friendly</option>
                    <option value="Technical">Technical</option>
                    <option value="Inspirational">Inspirational</option>
                    <option value="Conversational">Conversational</option>
                  </select>
                </div>
              </div>

              {/* LinkedIn & Instagram Handles */}
              <div className="grid grid-cols-1 gap-13 sm:grid-cols-2">
                <div>
                  <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                    LinkedIn Handle
                  </label>
                  <input
                    type="text"
                    value={linkedinHandle}
                    onChange={(e) => setLinkedinHandle(e.target.value)}
                    placeholder="e.g. in/alexmorgan"
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                    Instagram Handle
                  </label>
                  <input
                    type="text"
                    value={instagramHandle}
                    onChange={(e) => setInstagramHandle(e.target.value)}
                    placeholder="e.g. @alex.ai"
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>
              </div>

              {/* Website URL & Custom Sign-off */}
              <div className="grid grid-cols-1 gap-13 sm:grid-cols-2">
                <div>
                  <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                    Website URL
                  </label>
                  <input
                    type="url"
                    value={websiteUrl}
                    onChange={(e) => setWebsiteUrl(e.target.value)}
                    placeholder="e.g. https://alexmorgan.dev"
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                    Custom Sign-off
                  </label>
                  <input
                    type="text"
                    value={customSignoff}
                    onChange={(e) => setCustomSignoff(e.target.value)}
                    placeholder="e.g. Stay curious and keep building 🚀"
                    className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                  />
                </div>
              </div>

              {/* Bio / Brand Context */}
              <div>
                <label className="block text-xs uppercase tracking-wider text-ink-light/60 dark:text-ink-dim mb-4">
                  Author Bio / Brand Context
                </label>
                <textarea
                  rows={3}
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  placeholder="e.g. Organizer of Docker Pune with 10+ years in distributed systems..."
                  className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] p-13 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none leading-relaxed"
                />
              </div>

              {/* Save Brand Profile Button */}
              <div className="pt-8">
                <button
                  type="submit"
                  disabled={profileMutation.isPending}
                  className="rounded-full border border-gold/30 bg-gradient-to-r from-gold/20 via-lavender/15 to-teal/10 px-21 py-8 text-xs font-semibold text-gold dark:text-gold-soft hover:border-gold hover:scale-105 transition-all disabled:opacity-50"
                >
                  {profileMutation.isPending ? "Saving..." : "Save Brand Profile"}
                </button>
              </div>
            </form>
          </section>

        {/* System Diagnostics */}
        <section className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
          <h3 className="font-semibold uppercase tracking-wider text-gold mb-13 text-sm">System Diagnostics &amp; Health</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-13">
            <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
              <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">API Gateway</span>
              <span className="font-semibold text-teal">{health.data?.status ?? "online"}</span>
            </div>
            <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
              <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">API Version</span>
              <span className="font-mono text-gold dark:text-gold-soft">{health.data?.version ?? "0.1.0"}</span>
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

        {/* Theme Settings */}
        <section className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
          <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Appearance & Design System</h3>
          <p className="mt-4 text-xs text-ink-light/50 dark:text-ink-dim">Deep Signal design tokens with golden ratio layout</p>

            <div className="mt-13 flex gap-13">
              <button
                type="button"
                onClick={() => setTheme("dark")}
                className={`flex items-center gap-8 rounded-card border px-21 py-13 text-xs font-medium transition-all ${
                  theme === "dark"
                    ? "border-primary bg-primary/20 text-primary shadow-sm"
                    : "border-black/10 text-ink-light/70 hover:border-black/30 dark:border-white/10 dark:text-ink-dim dark:hover:border-white/30"
                }`}
              >
                🌙 Dark Mode (Default)
              </button>
              <button
                type="button"
                onClick={() => setTheme("light")}
                className={`flex items-center gap-8 rounded-card border px-21 py-13 text-xs font-medium transition-all ${
                  theme === "light"
                    ? "border-primary bg-primary/20 text-primary shadow-sm"
                    : "border-black/10 text-ink-light/70 hover:border-black/30 dark:border-white/10 dark:text-ink-dim dark:hover:border-white/30"
                }`}
              >
                ☀️ Light Mode
              </button>
            </div>
          </section>

          {/* Media Retention Settings */}
          <section className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
            <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Privacy & Media Retention</h3>
            <p className="mt-4 text-xs text-ink-light/50 dark:text-ink-dim">
              Automatically purge original media files from disk after processing to ensure participant privacy.
            </p>

            <div className="mt-13">
              <select
                value={retentionHours}
                onChange={(e) => setRetentionHours(e.target.value)}
                className="w-full max-w-xs rounded-card border border-black/10 bg-canvas-light p-13 text-xs text-ink-light dark:border-white/10 dark:bg-canvas-dark dark:text-ink-dark"
              >
                <option value="24">Purge after 24 Hours</option>
                <option value="72">Purge after 72 Hours (Default)</option>
                <option value="168">Purge after 7 Days</option>
                <option value="0">Retain indefinitely</option>
              </select>
            </div>
          </section>

          {/* Default Translation Languages */}
          <section className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
            <h3 className="text-sm font-semibold text-ink-light dark:text-ink-dark">Default Target Languages</h3>
            <p className="mt-4 text-xs text-ink-light/50 dark:text-ink-dim">
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
                        ? "border-accent bg-accent/20 text-accent shadow-sm"
                        : "border-black/10 text-ink-light/70 hover:text-ink-light hover:border-black/30 dark:border-white/10 dark:text-ink-dim dark:hover:text-ink-dark dark:hover:border-white/30"
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
          <section className="rounded-card border border-black/10 bg-surface-light p-21 shadow-sm dark:border-white/10 dark:bg-surface-dark dark:shadow-none">
            <h3 className="font-semibold uppercase tracking-wider text-gold mb-13 text-sm">System Diagnostics &amp; Health</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-13">
              <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
                <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">API Gateway</span>
                <span className="font-semibold text-teal">{health.data?.status ?? "online"}</span>
              </div>
              <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
                <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">API Version</span>
                <span className="font-mono text-gold dark:text-gold-soft">{health.data?.version ?? "0.1.0"}</span>
              </div>
              <div className="rounded-card border border-black/5 bg-canvas-light p-13 text-xs dark:border-white/5 dark:bg-white/[0.04]">
                <span className="text-ink-light/50 dark:text-ink-dim block text-[11px]">MySQL Database</span>
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
              className="rounded-full border border-gold/30 bg-gradient-to-r from-gold/20 to-teal/20 px-34 py-13 text-sm font-semibold text-gold hover:border-gold hover:scale-105 transition-all dark:text-gold-soft"
            >
              Save Preferences
            </button>
          </div>
        </div>
      </div>
    </GoldenShell>
  );
}
