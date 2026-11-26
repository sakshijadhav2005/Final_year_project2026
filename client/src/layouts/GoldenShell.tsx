import type { ReactNode } from "react";

import { AppHeader } from "@/layouts/AppHeader";

type Props = {
  children: ReactNode;
};

export function GoldenShell({ children }: Props) {
  return (
    <div className="relative min-h-screen overflow-x-hidden text-ink">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-13 focus:top-13 focus:z-50 focus:rounded-full focus:bg-amber-400 focus:px-21 focus:py-8 focus:text-sm focus:font-semibold focus:text-on-accent"
      >
        Skip to content
      </a>
      <AppHeader />
      <div className="relative mx-auto w-full max-w-7xl px-21 pb-89 pt-34 sm:px-34">
        <main id="main-content" tabIndex={-1} className="w-full focus:outline-none">
          {children}
        </main>
      </div>
    </div>
  );
}
