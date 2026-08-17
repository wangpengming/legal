/* plan 测试计划「前端 Vitest + RTL」：主题切换（G0-02/03 亮暗双主题 + localStorage 持久化 + data-theme 同步）。 */
import { beforeEach, describe, expect, it } from "vitest";
import { useUiStore } from "../ui";

describe("useUiStore 主题切换", () => {
  beforeEach(() => {
    useUiStore.setState({ theme: "light", sidebarCollapsed: false });
  });

  it("light → dark → light 往返，且 data-theme / localStorage 同步", () => {
    expect(useUiStore.getState().theme).toBe("light");
    useUiStore.getState().toggleTheme();
    expect(useUiStore.getState().theme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("lit.theme")).toBe("dark");

    useUiStore.getState().toggleTheme();
    expect(useUiStore.getState().theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("lit.theme")).toBe("light");
  });

  it("侧栏折叠状态可切换", () => {
    expect(useUiStore.getState().sidebarCollapsed).toBe(false);
    useUiStore.getState().setSidebarCollapsed(true);
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
  });
});