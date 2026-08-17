/* plan 测试计划「前端 Vitest + RTL」：搜索筛选/分页 + 导出口径脚注（02-search）。
   覆盖 D2 口径（行数 = meta.total 命中数）、chips 筛选写参、分页 page 透传、
   导出 payload with_footnote（口径脚注强制携带）。 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SearchPage from "../SearchPage";

const h = vi.hoisted(() => ({
  search: vi.fn(),
  exportCsv: vi.fn(),
  caseBatch: vi.fn(),
  lastReq: undefined as unknown,
  meta: {
    fields: [
      { key: "case_no", label: "案件号", type: "str", filterable: true, sortable: true, in_default: true },
      { key: "cause", label: "案由", type: "str", filterable: true, sortable: true, in_default: true },
      { key: "case_status", label: "状态", type: "str", filterable: true, sortable: true, in_default: true },
    ],
    enums: {
      cause: [{ enum_key: "侵害作品信息网络传播权纠纷", label: "侵害作品信息网络传播权纠纷" }],
      case_status: [{ enum_key: "在办", label: "在办" }],
    },
    rules: [],
    dicts: {},
    metrics: [],
  },
  rows: [
    { record_id: "rec001", case_no: "(2026)京01民初1号", cause: "侵害作品信息网络传播权纠纷", case_status: "在办" },
    { record_id: "rec002", case_no: "(2026)京01民初2号", cause: "著作权权属纠纷", case_status: "已结" },
  ],
}));

vi.mock("@/lib/api", () => ({
  api: { search: h.search, exportCsv: h.exportCsv, caseBatch: h.caseBatch },
}));

vi.mock("@/hooks", () => ({
  useMetadata: () => ({ data: h.meta, isLoading: false, isError: false, refetch: vi.fn() }),
  useSearch: (req: { page: number; page_size: number }) => {
    h.lastReq = req;
    return {
      data: {
        data: h.rows,
        meta: { total: 41, footnote: "命中数 = 检索条件命中案件数（口径 v1.0）", page: req.page, page_size: req.page_size },
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      refetch: vi.fn(),
    };
  },
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/search"]}>
        <SearchPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("02-search：筛选 / 分页 / 导出口径脚注", () => {
  it("D2 口径：行数 = meta.total 命中数（41），表格渲染数据行", async () => {
    renderPage();
    expect(await screen.findByText((t, el) => t === "41" && el?.tagName === "B")).toBeInTheDocument();
    expect(screen.getByText("(2026)京01民初1号")).toBeInTheDocument();
    expect(screen.getByText("(2026)京01民初2号")).toBeInTheDocument();
    /* 口径脚注来自后端 meta.footnote，强制展示 */
    expect(screen.getByText(/命中数 = 检索条件命中案件数/)).toBeInTheDocument();
  });

  it("chips 筛选：点击「在办」→ 请求参数携带 case_status in [在办]", async () => {
    renderPage();
    await screen.findByText((t, el) => t === "41" && el?.tagName === "B");
    fireEvent.click(screen.getByRole("button", { name: "在办" }));
    await waitFor(() =>
      expect(h.lastReq).toMatchObject({ filters: [{ field: "case_status", op: "in", values: ["在办"] }] }),
    );
  });

  it("分页：点击「下一页 → 请求 page 递增（总 41 条 = 3 页）", async () => {
    renderPage();
    await screen.findByText((t, el) => t === "41" && el?.tagName === "B");
    fireEvent.click(screen.getByRole("button", { name: /下一页/ }));
    await waitFor(() => expect(h.lastReq).toMatchObject({ page: 2 }));
  });

  it("导出：payload 强制 with_footnote + scope=search（口径脚注同源）", async () => {
    renderPage();
    await screen.findByText((t, el) => t === "41" && el?.tagName === "B");
    h.lastReq = undefined;
    fireEvent.click(screen.getByRole("button", { name: /导出结果/ }));
    await waitFor(() =>
      expect(h.exportCsv).toHaveBeenCalledWith(expect.objectContaining({ scope: "search", with_footnote: true })),
    );
  });
});