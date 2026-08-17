/* Vitest 全局 setup：jest-dom 断言 + jsdom 缺失的浏览器 API stub。 */
import { beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";

/* ui store 初始主题读取 matchMedia；jsdom 无实现 */
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

/* Chart.tsx（ECharts 封装）使用 ResizeObserver 自适应 */
if (!window.ResizeObserver) {
  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  window.ResizeObserver = RO as unknown as typeof ResizeObserver;
}

/* jsdom 无 URL.createObjectURL（导出测试触发 downloadBlob） */
if (!URL.createObjectURL) {
  URL.createObjectURL = () => "blob:mock";
  URL.revokeObjectURL = () => {};
}

/* 每次用例前清掉 localStorage 残留（ui store 主题持久化） */
beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});