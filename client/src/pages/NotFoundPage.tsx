import { Link } from "react-router-dom";

import { GoldenShell } from "@/layouts/GoldenShell";

export function NotFoundPage() {
  return (
    <GoldenShell>
      <div className="max-w-md mx-auto py-55 text-center">
        <h1 className="font-display text-h1 font-semibold text-ink-light dark:text-ink-dark">
          404 — Page Not Found
        </h1>
        <p className="mt-13 text-sm text-ink-dim">The session or page you are looking for does not exist.</p>
        <Link
          to="/"
          className="btn-ghost btn-sm mt-21"
        >
          ← Return to Studio
        </Link>
      </div>
    </GoldenShell>
  );
}
