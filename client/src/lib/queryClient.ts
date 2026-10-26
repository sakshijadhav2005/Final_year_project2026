import { QueryClient } from "@tanstack/react-query";

import { useAuthStore } from "@/store/auth";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Cached data belongs to whoever was signed in when it was fetched. When the
// account changes (sign out, sign in as someone else) drop all of it, so nobody
// ever sees the previous person's sessions, drafts or transcripts.
let cachedFor = useAuthStore.getState().user?.id ?? null;
useAuthStore.subscribe((state) => {
  const now = state.accessToken ? (state.user?.id ?? null) : null;
  if (now !== cachedFor) {
    cachedFor = now;
    queryClient.cancelQueries();
    queryClient.clear();
  }
});
