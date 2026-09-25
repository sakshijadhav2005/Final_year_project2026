import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { UserPublic, UserRole } from "@/lib/api";

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserPublic | null;
  setSession: (accessToken: string, refreshToken: string, user: UserPublic) => void;
  clear: () => void;
  logout: () => void;
};

export type { UserRole };

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setSession: (accessToken, refreshToken, user) => set({ accessToken, refreshToken, user }),
      clear: () => set({ accessToken: null, refreshToken: null, user: null }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    { name: "eventai-auth" },
  ),
);
