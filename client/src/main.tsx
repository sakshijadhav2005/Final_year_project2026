import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/App";
import { queryClient } from "@/lib/queryClient";
import { startSessionKeeper } from "@/lib/session";
import { useThemeStore } from "@/store/theme";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/instrument-sans";
import "@/styles/index.css";

useThemeStore.getState().setTheme(useThemeStore.getState().theme);
// Renew the login in the background so long pipeline runs never sign the user out.
startSessionKeeper();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
