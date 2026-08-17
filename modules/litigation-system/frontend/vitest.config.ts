// Vitest 配置（与 vite.config.ts 共用 @ 别名；jsdom 环境跑组件测试）。
// plan 测试计划「前端 Vitest + RTL」：搜索筛选/分页、主题切换、导出脚注、概览渲染。
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      css: false,
    },
  }),
);