import { create } from "zustand";

interface AuthState {
  isLoggedIn: boolean;
  setLoggedIn: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isLoggedIn: typeof window !== "undefined" && !!window.localStorage?.getItem?.("access_token"),
  setLoggedIn: (v) => set({ isLoggedIn: v }),
}));
