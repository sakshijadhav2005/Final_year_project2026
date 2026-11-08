import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/App";
import { startErrorReporter } from "@/lib/errorReporter";
import { queryClient } from "@/lib/queryClient";
import { startSessionKeeper } from "@/lib/session";
import { useThemeStore } from "@/store/theme";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/instrument-sans";
import "@/styles/index.css";

useThemeStore.getState().setTheme(useThemeStore.getState().theme);
// Renew the login in the background so long pipeline runs never sign the user out.
startSessionKeeper();
// Development: uncaught browser errors go to the error-repair agent (Admin → Error fixes).
startErrorReporter();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
