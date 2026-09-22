import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { registerAccount, type UserRole } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function RegisterPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("password123");
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState<UserRole>("event_organizer");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => registerAccount(email, password, role),
    onSuccess: (data) => {
      setSession(data.access_token, data.refresh_token, data.user);
      navigate("/dashboard");
    },
    onError: (err: Error) => setError(err.message),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <GoldenShell>
      <div className="w-full max-w-md mx-auto py-21">
        <div className="mb-21">
          <p className="text-xs font-semibold uppercase tracking-wider text-gold">Onboarding</p>
          <h1 className="font-display text-3xl font-normal italic text-ink-light dark:text-ink-dark">
            Create an <em className="not-italic text-gold dark:text-gold-soft">EventAI</em> Account
          </h1>
        </div>

        <form className="glass p-34 flex flex-col gap-13" onSubmit={onSubmit}>
          <div>
            <label className="block text-xs uppercase tracking-wider text-ink-light/50 dark:text-ink-dim mb-4">Email</label>
            <input
              className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-sm text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
              type="email"
              placeholder="organizer@conference.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-ink-light/50 dark:text-ink-dim mb-4">Password</label>
            <div className="relative">
              <input
                className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 pr-34 text-sm text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-10 top-1/2 -translate-y-1/2 text-ink-light/50 dark:text-ink-dim hover:text-gold focus:outline-none"
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24M1 1l22 22" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-ink-light/50 dark:text-ink-dim mb-4">Account Role</label>
            <select
              className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-sm text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
            >
              <option value="event_organizer" className="bg-surface-light dark:bg-[#141826]">Event Organizer (Full Upload &amp; Review)</option>
              <option value="content_creator" className="bg-surface-light dark:bg-[#141826]">Content Creator (Review &amp; Edit)</option>
            </select>
          </div>

          {error && (
            <div className="rounded-card border border-danger/40 bg-danger/10 p-13 text-xs text-danger flex flex-col gap-4">
              <div className="flex items-center gap-8 font-semibold">
                <span>⚠️ Registration Notice</span>
              </div>
              <p>{error}</p>
              {error.toLowerCase().includes("registered") || error.toLowerCase().includes("taken") ? (
                <p className="mt-4 text-[11px] text-ink-light/80 dark:text-ink-dim">
                  This email address already has an account. You can <Link to="/login" className="text-gold dark:text-gold-soft font-semibold underline">Sign In Here</Link>.
                </p>
              ) : null}
            </div>
          )}

          <button
            type="submit"
            disabled={mutation.isPending}
            className="mt-13 rounded-full border border-gold/30 bg-gradient-to-r from-gold/20 via-lavender/15 to-teal/10 px-21 py-13 font-sans text-sm font-medium text-gold dark:text-gold-soft hover:border-gold hover:scale-[1.02] transition-all"
          >
            {mutation.isPending ? "Creating Account…" : "Register Workspace Account →"}
          </button>
        </form>

        <p className="mt-21 text-xs text-ink-light/50 dark:text-ink-dim">
          Already registered?{" "}
          <Link to="/login" className="text-gold dark:text-gold-soft underline hover:text-ink-light dark:hover:text-white">
            Sign in to existing account
          </Link>
        </p>
      </div>
    </GoldenShell>
  );
}
