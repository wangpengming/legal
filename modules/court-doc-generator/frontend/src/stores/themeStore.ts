/** F7 暗色模式：light / dark / system 三态，持久化 localStorage。 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "light" | "dark" | "system";

interface ThemeState {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
}

/** 解析最终生效的主题（system 跟随系统偏好）。 */
function resolveMode(mode: ThemeMode, prefersDark: boolean): "light" | "dark" {
  if (mode === "system") return prefersDark ? "dark" : "light";
  return mode;
}

/** 写入 <html data-theme="dark">。 */
export function applyTheme(mode: ThemeMode): void {
  const dark =
    typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
      : false;
  document.documentElement.dataset.theme = resolveMode(mode, dark);
}

export const useThemeStore = create<ThemeState>()(
  persist(
    set => ({
      mode: "system",
      setMode: mode => set({ mode }),
    }),
    { name: "courtdoc:theme" },
  ),
);

// 模块加载即应用，避免暗色用户首屏闪白
if (typeof document !== "undefined") {
  applyTheme(useThemeStore.getState().mode);
}