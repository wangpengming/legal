/* plan 测试计划「前端 Vitest + RTL」：概览渲染 + 真值断言（01-overview，对应下钻/跳转的可测形态）。
   638/312/48.9%/¥1,284,600 真值断言（docs/04 §4）；业务线 8 条；判赔趋势 card；
   ECharts 以 mock Chart 替换（jsdom 无 canvas 上下文）。 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import OverviewPage from "../OverviewPage";

const h = vi.hoisted(() => ({
  overview: {
    kpis: [
      { key: "open_count", value: 42, definition: "在办 = 未结案件数（口径 v1.0）", title: "在办案件" },
      { key: "cycle", value: 186, definition: "平均结案周期（口径 v1.0）", title: "平均结案周期" },
    ],
    summary: { total_cases: 638, acmc_cases: 312, verdict_total: 1284600, monthly_new: 12 },
    trend: [{ year: 2024, case_count: 100, verdict_amount: 500000 }],
    bizline: ["VOD", "IPTV·OTT", "车载", "雷客", "人力", "哇屋", "研发", "默霆"].map((b) => ({
      biz_line: b,
      case_count: 80,
    })),
    upcoming_court: [],
  },
  sync: {
    running: false,
    last: { type: "增量", status: "ok", total: 26 },
    next_at: "2026-08-13 16:00",
    running_job_id: null,
  },
}));

vi.mock("@/components/Chart", () => ({ Chart: () => <div data-testid="mock-chart" /> }));

vi.mock("@/hooks", () => ({
  useOverview: () => ({ data: h.overview, isLoading: false, isError: false, refetch: vi.fn() }),
  useSyncStatus: () => ({ data: h.sync }),
  useDirtyItems: () => ({ data: [] }),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>
        <OverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("01-overview：基线真值 + 业务线下钻入口 + KPI 跳转", () => {
  it("基线真值：638 / 312 / 48.9% / ¥1,284,600 / 在办 42", async () => {
    renderPage();
    expect(await screen.findByText("638")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
    expect(screen.getByText(/48\.9%/)).toBeInTheDocument();
    expect(screen.getByText("¥1,284,600")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("业务线 8 条渲染 + 判赔趋势 card（Chart mock）", async () => {
    renderPage();
    await screen.findByText("638");
    expect(screen.getByText("业务线构成")).toBeInTheDocument();
    for (const b of ["VOD", "IPTV·OTT", "车载", "默霆"]) expect(screen.getByText(b)).toBeInTheDocument();
    expect(screen.getByText("判赔趋势")).toBeInTheDocument();
    expect(screen.getByTestId("mock-chart")).toBeInTheDocument();
  });

  it("跳转入口：案件检索按钮 + 口径脚注（判赔金额口径声明）", async () => {
    renderPage();
    await screen.findByText("638");
    expect(screen.getByRole("button", { name: /案件检索/ })).toBeInTheDocument();
    expect(screen.getByText(/判赔金额 = 结案原因「判赔」的支付金额合计/)).toBeInTheDocument();
  });
});