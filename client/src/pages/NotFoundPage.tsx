import { Link } from "react-router-dom";

import { GoldenShell } from "@/layouts/GoldenShell";

export function NotFoundPage() {
  return (
    <GoldenShell>
      <div className="max-w-md mx-auto py-55 text-center">
        <h1 className="font-display text-4xl font-normal italic text-ink-light dark:text-ink-dark">
          404 — Page Not Found
        </h1>
        <p className="mt-13 text-sm text-ink-dim">The session or page you are looking for does not exist.</p>
        <Link
          to="/"
          className="mt-21 inline-block rounded-full border border-gold/30 bg-gold/10 px-21 py-8 text-xs font-medium text-gold-soft hover:border-gold transition-all"
        >
          ← Return to Studio
        </Link>
      </div>
    </GoldenShell>
  );
}
