import type { ReactNode } from "react";

import { AppHeader } from "@/layouts/AppHeader";
import { AuroraBackground } from "@/components/ui/AuroraBackground";

type Props = {
  children: ReactNode;
};

export function GoldenShell({ children }: Props) {
  return (
    <div className="relative min-h-screen overflow-x-hidden text-ink-light dark:text-ink-dark selection:bg-gold/30 selection:text-gold-soft">
      <AuroraBackground />
      <AppHeader />
      <div className="relative z-10 mx-auto w-full max-w-7xl px-21 py-34 sm:px-34">
        <main className="w-full">{children}</main>
      </div>
    </div>
  );
}
