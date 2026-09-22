import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { loginAccount } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const [email, setEmail] = useState("organizer@example.com");
  const [password, setPassword] = useState("password123");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => loginAccount(email, password),
    onSuccess: (data) => {
      setSession(data.access_token, data.refresh_token, data.user);
      if (data.user.role === "regular_user") {
        navigate("/user/dashboard");
      } else {
        navigate("/organizer/dashboard");
      }
    },
    onError: (err: Error) => setError(err.message),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <GoldenShell>
      <div className="w-full max-w-md mx-auto">
        <div className="mb-21">
          <p className="text-xs font-semibold uppercase tracking-wider text-gold">Authentication</p>
          <h1 className="font-display text-3xl font-normal italic text-ink-light dark:text-ink-dark">
            Sign In to <em className="not-italic text-gold dark:text-gold-soft">EventAI</em>
          </h1>
        </div>

        <form className="glass p-34 flex flex-col gap-13" onSubmit={onSubmit}>
          <div className="rounded-card border border-gold/20 bg-gold/5 p-10 text-xs text-ink-light/80 dark:text-ink-dim flex items-center gap-8">
            <span className="text-gold text-base">ℹ️</span>
            <span>If you are a new user, please <strong>register first</strong> before signing in.</span>
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-ink-light/50 dark:text-ink-dim mb-4">Email Address</label>
            <input
              className="w-full rounded-card border border-black/10 dark:border-white/10 bg-canvas-light dark:bg-white/[0.04] px-13 py-8 text-sm text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@organization.com"
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

          {error && (
            <div className="rounded-card border border-danger/40 bg-danger/10 p-13 text-xs text-danger flex flex-col gap-4">
              <div className="flex items-center gap-8 font-semibold">
                <span>⚠️ Sign In Failed</span>
              </div>
              <p>{error}</p>
              <p className="mt-4 text-[11px] text-ink-light/80 dark:text-ink-dim">
                If you haven't created an account yet, please <Link to="/register" className="text-gold dark:text-gold-soft font-semibold underline">Register First</Link>.
              </p>
            </div>
          )}

          <button
            type="submit"
            disabled={mutation.isPending}
            className="mt-13 rounded-full border border-gold/30 bg-gradient-to-r from-gold/20 via-lavender/15 to-teal/10 px-21 py-13 font-sans text-sm font-medium text-gold dark:text-gold-soft hover:border-gold hover:scale-[1.02] transition-all"
          >
            {mutation.isPending ? "Signing In…" : "Sign In to Workspace →"}
          </button>
        </form>

        <p className="mt-21 text-xs text-ink-light/50 dark:text-ink-dim">
          Don't have an account yet?{" "}
          <Link to="/register" className="text-gold dark:text-gold-soft underline hover:text-ink-light dark:hover:text-white">
            Register as an Organizer or Creator
          </Link>
        </p>
      </div>
    </GoldenShell>
  );
}
