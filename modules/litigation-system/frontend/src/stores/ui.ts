/* 全局 UI 状态（zustand）：主题亮暗 / 侧栏折叠。
   主题：data-theme 运行时变量切换（tokens.css 双主题），localStorage 持久化，
   首次访问跟随系统 prefers-color-scheme（docs/02 §2.1 G0-02/03）。 */

import { create } from "zustand";

const THEME_KEY = "lit.theme";

function initialTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const initial = initialTheme();
/* 模块加载即应用主题，避免首帧闪烁 */
if (typeof document !== "undefined") {
  document.documentElement.dataset.theme = initial;
}

interface UiState {
  theme: "light" | "dark";
  sidebarCollapsed: boolean;
  toggleTheme: () => void;
  setSidebarCollapsed: (v: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  theme: initial,
  sidebarCollapsed: false,
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        /* 隐私模式等场景忽略 */
      }
      return { theme: next };
    }),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
}));