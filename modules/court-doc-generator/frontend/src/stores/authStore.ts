import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  workspaceId: string | null;
  workspaceName: string | null;
  token: string | null;
  setAuth: (id: string, name: string, token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      workspaceId: null,
      workspaceName: null,
      token: null,
      setAuth: (id, name, token) => set({ workspaceId: id, workspaceName: name, token }),
      logout: () => set({ workspaceId: null, workspaceName: null, token: null }),
    }),
    { name: "court-auth" }
  )
);
