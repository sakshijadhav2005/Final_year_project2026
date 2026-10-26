import type { ReactNode } from "react";

import { AppHeader } from "@/layouts/AppHeader";

type Props = {
  children: ReactNode;
};

export function GoldenShell({ children }: Props) {
  return (
    <div className="relative min-h-screen overflow-x-hidden text-ink">
      <AppHeader />
      <div className="relative mx-auto w-full max-w-7xl px-21 pb-89 pt-34 sm:px-34">
        <main className="w-full">{children}</main>
      </div>
    </div>
  );
}
