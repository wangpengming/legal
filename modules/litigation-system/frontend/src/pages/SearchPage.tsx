/* 02-案件检索（docs/02 §4.2 + plan t08-10）。
   TanStack Table 服务端模式：排序/分页/行选择(Shift 区间)/列显隐/密度；
   服务端筛选（关键词 FTS + 枚举 chips 多选 + 年份/标的区间）；
   导出 CSV 显式 {scope:"search"|"case"}（规避后端 ExportRequest.scope 默认 all 导出全量）；
   D1 修复：support_rate null →「—」占位；D2 修复：行数 = meta.total 命中数。 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type PaginationState,
  type RowSelectionState,
  type SortingState,
} from "@tanstack/react-table";
import { useQueryClient } from "@tanstack/react-query";
import { Download, RotateCcw, Save, Settings2, SlidersHorizontal, Tag, Target } from "lucide-react";
import { Drawer } from "@/components/Drawer";
import SimilarPanel from "@/components/SimilarPanel";
import { Badge, EmptyState, EnumBadge, PageError, PageHeader, Spinner, Tooltip } from "@/components/common";
import { useMetadata, useSearch } from "@/hooks";
import { api, type CaseRow, type EnumItem, type SearchFilter, type SearchRequest, type SearchSort } from "@/lib/api";
import { downloadBlob, fmtDate, fmtList, fmtMoney, fmtNum, fmtPct, fmtText } from "@/lib/format";
import { enumTone, resolveTone, statusTone, type Tone } from "@/lib/colors";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- 工具 */

function toast(msg: string, isErr = false): void {
  window.dispatchEvent(new CustomEvent("lt:toast", { detail: isErr ? `⚠️ ${msg}` : msg }));
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function stamp(): string {
  return new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
}

/* 数值列（右对齐 tabular-nums，与 tokens.css 约定一致） */
const NUM_KEYS = new Set(["amount", "pay_amount", "per_song_amount", "support_rate", "song_count", "merged_count", "year", "lawyer_fee"]);

/* 枚举色名 → 色点 hex（cause 列色点） */
const DOT: Record<string, string> = { red: "#dc2626", green: "#16a34a", amber: "#d97706", blue: "#2563eb", purple: "#7c3aed", gray: "#94a3b8" };

/* 结案原因胜负色字（口径A 胜集见 docs/02 §2.2） */
const RESOLVE_COLOR: Record<Tone, string> = {
  green: "var(--success)",
  red: "var(--danger)",
  amber: "var(--warning)",
  blue: "var(--primary)",
  gray: "var(--muted)",
};

function dotColor(color: string | null | undefined): string {
  return DOT[color ?? ""] ?? DOT.gray;
}

/** filters 中 {field, op:"in"} 的 values（无则为 []） */
function enumSelected(filters: SearchFilter[], field: string): string[] {
  const f = filters.find((x) => x.field === field && x.op === "in");
  return ((f?.values ?? []) as (string | number)[]).map(String);
}

/** 字段筛选摘要（filter-active-bar 胶囊展示） */
function filterSummary(filters: SearchFilter[], fm: Map<string, string>): { key: string; label: string; text: string }[] {
  const out: { key: string; label: string; text: string }[] = [];
  for (const f of filters) {
    const label = fm.get(f.field) ?? f.field;
    if (f.op === "in") {
      if ((f.values ?? []).length) out.push({ key: `${f.field}|${f.op}`, label, text: `∈ ${String((f.values ?? []).join("、"))}` });
    } else if (f.op === "range") {
      const lo = f.min !== undefined && f.min !== null ? String(f.min) : "—";
      const hi = f.max !== undefined && f.max !== null ? String(f.max) : "—";
      out.push({ key: `${f.field}|${f.op}`, label, text: `${lo} ~ ${hi}` });
    } else if ((f.value !== undefined && f.value !== null && f.value !== "") || (f.values ?? []).length) {
      out.push({ key: `${f.field}|${f.op}`, label, text: String(f.value ?? f.values?.join("、") ?? "") });
    }
  }
  return out;
}

/* ---------------------------------------------------------------- 主体 */

export default function SearchPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const initQ = useMemo(() => searchParams.get("q") ?? "", [searchParams]);

  const { data: meta, isLoading: metaLoading, isError: metaError, refetch: metaRefetch } = useMetadata();

  /* 状态：关键词 / 筛选 / 表格控制 */
  const [q, setQ] = useState(initQ);
  const [appliedQ, setAppliedQ] = useState(initQ);
  const [filters, setFilters] = useState<SearchFilter[]>([]);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 20 });
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [visibleKeys, setVisibleKeys] = useState<string[]>([]);
  const [density, setDensity] = useState<"compact" | "standard">("standard");
  const [panelOpen, setPanelOpen] = useState(true);

  /* 筛选面板输入（Enter/失焦时写入 filters） */
  const [yrFrom, setYrFrom] = useState("");
  const [yrTo, setYrTo] = useState("");
  const [amtMin, setAmtMin] = useState("");
  const [amtMax, setAmtMax] = useState("");

  /* 批量打标 / 列设置 */
  const [tagOpen, setTagOpen] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const [colOpen, setColOpen] = useState(false);
  const [colDraft, setColDraft] = useState<string[]>([]);
  const [exporting, setExporting] = useState(false);
  /* F4.2 找相似：选中恰好 1 件时启用 */
  const [similarId, setSimilarId] = useState<string | null>(null);

  const anchorRef = useRef<string | null>(null);
  /* Shift 区间选择：onClick 处理（MouseEvent 有 shiftKey），抑制随后的 onChange 翻转 */
  const shiftHandledRef = useRef(false);

  const fieldMeta = useMemo(() => new Map((meta?.fields ?? []).map((f) => [f.key, f])), [meta]);
  const labelOf = useMemo(() => new Map((meta?.fields ?? []).map((f) => [f.key, f.label])), [meta]);
  const defaultKeys = useMemo(() => (meta?.fields ?? []).filter((f) => f.in_default).map((f) => f.key), [meta]);

  /* 默认列集（后端 DEFAULT_COLUMNS 18 列 = in_default，metadata 就绪后生效） */
  useEffect(() => {
    if (visibleKeys.length === 0 && defaultKeys.length) setVisibleKeys(defaultKeys);
  }, [defaultKeys, visibleKeys.length]);

  /* 关键词/筛选变化 → 回第 1 页 */
  useEffect(() => {
    setPagination((p) => ({ ...p, pageIndex: 0 }));
  }, [appliedQ, filters]);

  /* 服务端检索（payload 全部透传；D2：行数 = meta.total） */
  const req: SearchRequest = useMemo(
    () => ({
      q: appliedQ || undefined,
      filters,
      sorts: sorting.map((s): SearchSort => ({ field: s.id, desc: s.desc })),
      page: pagination.pageIndex + 1,
      page_size: pagination.pageSize,
      columns: visibleKeys,
    }),
    [appliedQ, filters, sorting, pagination, visibleKeys],
  );
  const { data: res, isLoading, isFetching, isError, refetch } = useSearch(req);
  const rows = res?.data ?? [];
  const total = res?.meta.total ?? 0;
  const selectedIds = useMemo(() => Object.keys(rowSelection).filter((id) => rowSelection[id]), [rowSelection]);

  /* ---------------------------------------------------------------- 筛选操作 */

  const [, setSearchParams] = useSearchParams();
  const applyQ = (v: string) => {
    const t = v.trim();
    setAppliedQ(t);
    setSearchParams(t ? { q: t } : {}, { replace: true });
  };

  const toggleEnum = (field: string, value: string) => {
    setFilters((prev) => {
      const cur = enumSelected(prev, field);
      const set = new Set(cur);
      if (set.has(value)) set.delete(value);
      else set.add(value);
      if (set.size === 0) return prev.filter((f) => !(f.field === field && f.op === "in"));
      return [...prev.filter((f) => !(f.field === field && f.op === "in")), { field, op: "in", values: [...set] }];
    });
  };

  const setRange = (field: string, min: number | undefined, max: number | undefined) => {
    setFilters((prev) => {
      const base = prev.filter((f) => !(f.field === field && f.op === "range"));
      if (min === undefined && max === undefined) return base;
      return [...base, { field, op: "range", ...(min !== undefined ? { min } : {}), ...(max !== undefined ? { max } : {}) }];
    });
  };

  const commitRange = (field: string, from: string, to: string) => {
    if (field === "year") setRange("year", from ? Number(from) : undefined, to ? Number(to) : undefined);
    else setRange("amount", from ? Number(from) : undefined, to ? Number(to) : undefined);
  };

  const resetAll = () => {
    setQ("");
    setAppliedQ("");
    setFilters([]);
    setYrFrom(""); setYrTo(""); setAmtMin(""); setAmtMax("");
    setSorting([]);
    setPagination({ pageIndex: 0, pageSize: 20 });
    setVisibleKeys(defaultKeys);
  };

  const saveView = () => {
    try {
      localStorage.setItem("lt:search-view", JSON.stringify({ q: appliedQ, filters, columns: visibleKeys, savedAt: Date.now() }));
      toast("检索视图已保存（浏览器本地）");
    } catch {
      toast("视图保存失败", true);
    }
  };

  /* ---------------------------------------------------------------- 导出 / 打标 */

  const doExport = async (scope: "search" | "case", ids?: string[], label = "结果") => {
    setExporting(true);
    try {
      const payload: Partial<SearchRequest> & { with_footnote?: boolean } = {
        scope,
        columns: visibleKeys,
        with_footnote: true,
      };
      if (scope === "search") {
        if (appliedQ) payload.q = appliedQ;
        if (filters.length) payload.filters = filters;
      } else if (ids?.length) {
        payload.ids = ids;
      }
      const blob = await api.exportCsv(payload);
      downloadBlob(blob, `litigation_cases_${scope}_${stamp()}.csv`);
      toast(`已导出${label}（${fmtNum(scope === "search" ? total : ids?.length ?? 0)} 件 · CSV 含口径脚注）`);
    } catch (e) {
      toast(errMsg(e), true);
    } finally {
      setExporting(false);
    }
  };

  const doTag = async () => {
    const tag = tagInput.trim();
    if (!tag) {
      toast("请输入标签内容", true);
      return;
    }
    if (!selectedIds.length) {
      toast("请先勾选案件", true);
      return;
    }
    try {
      const r = await api.caseBatch({ ids: selectedIds, action: "tag", tag });
      toast(`已打标 ${r.data?.linked ?? selectedIds.length} 件「${tag}」`);
      setTagOpen(false);
      setTagInput("");
      setRowSelection({});
      void queryClient.invalidateQueries({ queryKey: ["search"] });
    } catch (e) {
      toast(errMsg(e), true);
    }
  };

  /* ---------------------------------------------------------------- 列定义 */

  const columns = useMemo<ColumnDef<CaseRow>[]>(() => {
    const sel: ColumnDef<CaseRow> = {
      id: "__sel",
      size: 36,
      enableSorting: false,
      header: ({ table }) => (
        <input
          type="checkbox"
          checked={table.getIsAllPageRowsSelected()}
          onChange={table.getToggleAllPageRowsSelectedHandler()}
          aria-label="全选本页"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={row.getIsSelected()}
          onClick={(e) => {
            e.stopPropagation();
            const rid = String(row.original.record_id);
            if (e.shiftKey && anchorRef.current) {
              const pageIds = rows.map((r) => String(r.record_id));
              const a = pageIds.indexOf(anchorRef.current);
              const b = pageIds.indexOf(rid);
              if (a >= 0 && b >= 0) {
                const spanIds = pageIds.slice(Math.min(a, b), Math.max(a, b) + 1);
                /* click 先于 change：当前行选中态尚未翻转，据此定目标态 */
                const target = !row.getIsSelected();
                setRowSelection((prev) => {
                  const next = { ...prev };
                  if (target) for (const id of spanIds) next[id] = true;
                  else for (const id of spanIds) delete next[id];
                  return next;
                });
                shiftHandledRef.current = true;
              }
            }
          }}
          onChange={(e) => {
            if (shiftHandledRef.current) {
              shiftHandledRef.current = false;
              return;
            }
            anchorRef.current = String(row.original.record_id);
            row.getToggleSelectedHandler()(e);
          }}
          aria-label="选择行"
        />
      ),
    };

    /* 枚举色映射（11-dicts 驱动 cause 色点 / biz_line 徽章色） */
    const causeColor = new Map((meta?.enums.cause ?? []).map((o) => [o.enum_key, o.color ?? null]));
    const bizColor = new Map((meta?.enums.biz_line ?? []).map((o) => [o.enum_key, o.color ?? null]));

    const make = (k: string): ColumnDef<CaseRow> => {
      const f = fieldMeta.get(k);
      const label = f?.label ?? k;
      const isNum = NUM_KEYS.has(k);
      const cell = ({ row }: { row: { original: CaseRow } }) => {
        const v = row.original[k];
        if (k === "cause" && v !== null && v !== undefined && v !== "") {
          return (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <i style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor(causeColor.get(String(v)) ?? null), flexShrink: 0 }} />
              {fmtText(v)}
            </span>
          );
        }
        if (k === "biz_line" && v !== null && v !== undefined && v !== "") {
          return <EnumBadge tone={enumTone(bizColor.get(String(v)) ?? null)}>{String(v)}</EnumBadge>;
        }
        return renderCell(k, row.original, f?.type, navigate);
      };
      return { id: k, header: label, cell, enableSorting: f?.sortable ?? false, size: isNum ? 96 : undefined };
    };

    return [sel, ...visibleKeys.map(make)];
  }, [visibleKeys, fieldMeta, rows, navigate, meta]);

  /* 行选择状态变更即记录（react-table 回调） */
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, pagination, rowSelection },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    pageCount: Math.max(1, Math.ceil(total / (pagination.pageSize || 1))),
    getRowId: (row) => String(row.record_id),
  });

  /* ---------------------------------------------------------------- 渲染 */

  if (metaError) return <PageError message="元数据加载失败（列/枚举未就绪）" onRetry={() => void metaRefetch()} />;
  if (metaLoading || !meta) return <Spinner label="检索页初始化…" />;

  const activeFilters = filterSummary(filters, labelOf);
  const enumsOf = (field: string): EnumItem[] => meta.enums[field] ?? [];
  const enumOpts = new Set(Object.keys(meta.enums));

  const chipGroup = (field: string) => {
    const opts = enumsOf(field);
    const sel = new Set(enumSelected(filters, field));
    return (
      <div className="filter-group" key={field}>
        <label>{labelOf.get(field) ?? field}</label>
        {opts.length ? (
          <span style={{ display: "flex", flexWrap: "wrap", gap: 4, maxWidth: 420 }}>
            {opts.map((o) => (
              <button
                key={o.enum_key}
                type="button"
                className={cn("chip", sel.has(o.enum_key) && "on")}
                onClick={() => toggleEnum(field, o.enum_key)}
              >
                {o.label ?? o.enum_key}
              </button>
            ))}
          </span>
        ) : (
          <span className="muted" style={{ fontSize: 12 }}>暂无枚举（可经 11-字典配置）</span>
        )}
      </div>
    );
  };

  return (
    <div>
      <PageHeader
        title="案件检索"
        breadcrumb={
          <>
            {appliedQ ? <>关键词「{appliedQ}」 · </> : null}
            共 {fmtNum(total)} 件 · 已选 {selectedIds.length} 件 · 口径 v1.0（D1/D2 已修复）
          </>
        }
        actions={
          <>
            <button type="button" className="btn btn-sm" onClick={saveView} title="保存为本地检索视图">
              <Save size={13} /> 保存视图
            </button>
            <button type="button" className="btn btn-sm" onClick={() => setPanelOpen((v) => !v)}>
              <SlidersHorizontal size={13} /> 筛选面板
            </button>
          </>
        }
      />

      {/* 筛选面板（可折叠；回车/失焦提交区间条件） */}
      {panelOpen && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="filter-bar">
            <div className="filter-group">
              <label>关键词</label>
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && applyQ(q)}
                placeholder="案号 / 当事人 / 歌名…"
                style={{ width: 220 }}
                aria-label="关键词"
              />
            </div>
            <div className="filter-group">
              <label>收案年份</label>
              <input type="number" value={yrFrom} onChange={(e) => setYrFrom(e.target.value)} onBlur={() => commitRange("year", yrFrom, yrTo)} placeholder="从" style={{ width: 64 }} aria-label="年份起" />
              <span className="muted">~</span>
              <input type="number" value={yrTo} onChange={(e) => setYrTo(e.target.value)} onBlur={() => commitRange("year", yrFrom, yrTo)} placeholder="至" style={{ width: 64 }} aria-label="年份止" />
            </div>
            <div className="filter-group">
              <label>标的金额</label>
              <input type="number" value={amtMin} onChange={(e) => setAmtMin(e.target.value)} onBlur={() => commitRange("amount", amtMin, amtMax)} placeholder="最低" style={{ width: 72 }} aria-label="标的最低" />
              <span className="muted">~</span>
              <input type="number" value={amtMax} onChange={(e) => setAmtMax(e.target.value)} onBlur={() => commitRange("amount", amtMin, amtMax)} placeholder="最高" style={{ width: 72 }} aria-label="标的最高" />
            </div>
            {["cause", "biz_line", "case_status", "resolve", "payer"].map((f) => (enumOpts.has(f) ? chipGroup(f) : null))}
          </div>

          {activeFilters.length > 0 && (
            <div className="filter-active-bar">
              {appliedQ && (
                <button type="button" className="chip on" onClick={() => { setQ(""); setAppliedQ(""); }}>
                  关键词：{appliedQ} <span className="x">✕</span>
                </button>
              )}
              {activeFilters.map((a) => (
                <button
                  type="button"
                  className="chip on"
                  key={a.key}
                  onClick={() => setFilters((prev) => prev.filter((f) => f.field !== a.key.split("|")[0]))}
                >
                  {a.label}：{a.text} <span className="x">✕</span>
                </button>
              ))}
              <button type="button" className="btn btn-ghost btn-sm" onClick={resetAll} style={{ height: 24 }}>
                <RotateCcw size={12} /> 重置筛选
              </button>
            </div>
          )}
        </div>
      )}

      {/* 结果工具条 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>
          共 <b>{fmtNum(total)}</b> 件
          {selectedIds.length > 0 && <span style={{ color: "var(--primary)" }}> · 已选 {selectedIds.length} 件</span>}
        </span>
        <span className="grow" />
        <button type="button" className="btn btn-sm" disabled={exporting} onClick={() => void doExport("search", undefined, "当前检索结果")}>
          <Download size={13} /> 导出结果
        </button>
        <button type="button" className="btn btn-sm" disabled={exporting || selectedIds.length === 0} onClick={() => void doExport("case", selectedIds, `选中 ${selectedIds.length} 件`)}>
          <Download size={13} /> 导出选中
        </button>
        <button type="button" className="btn btn-sm btn-primary" disabled={selectedIds.length === 0} onClick={() => setTagOpen(true)}>
          <Tag size={13} /> 批量打标
        </button>
        <button
          type="button"
          className="btn btn-sm"
          disabled={selectedIds.length !== 1}
          onClick={() => setSimilarId(selectedIds[0])}
          title={selectedIds.length !== 1 ? "勾选恰好 1 件案件后启用" : "基于所选案件检索同质案（F4.2）"}
        >
          <Target size={13} /> 找相似
        </button>
        <button type="button" className="btn btn-sm" onClick={() => { setColDraft([...visibleKeys]); setColOpen(true); }}>
          <Settings2 size={13} /> 列设置
        </button>
        <button type="button" className="btn btn-sm" onClick={() => setDensity((d) => (d === "standard" ? "compact" : "standard"))}>
          {density === "standard" ? "紧凑" : "标准"}
          <span style={{ fontSize: 10, opacity: 0.7 }}>密度</span>
        </button>
      </div>

      {/* F4.2 找相似结果面板（勾选 1 件 → 工具条按钮触发） */}
      {similarId && <SimilarPanel caseId={similarId} onClose={() => setSimilarId(null)} />}

      {/* 表格 */}
      {isLoading ? (
        <Spinner label="检索中…" />
      ) : isError ? (
        <PageError message="检索失败" onRetry={() => void refetch()} />
      ) : (
        <div className="tbl-wrap" style={{ maxHeight: "calc(100vh - 330px)" }}>
          <table className="tbl">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => (
                    <th
                      key={h.id}
                      className={NUM_KEYS.has(h.column.id) ? "num" : undefined}
                      style={{ width: h.getSize() || undefined }}
                    >
                      {h.isPlaceholder ? null : (
                        <span
                          style={h.column.getCanSort() ? { cursor: "pointer", userSelect: "none" } : undefined}
                          onClick={h.column.getCanSort() ? h.column.getToggleSortingHandler() : undefined}
                          title={h.column.getCanSort() ? "点击排序" : undefined}
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {h.column.getIsSorted() === "asc" ? " ↑" : h.column.getIsSorted() === "desc" ? " ↓" : ""}
                        </span>
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={table.getHeaderGroups()[0].headers.length} style={{ padding: 32, textAlign: "center", whiteSpace: "normal" }}>
                    <EmptyState icon="🔍" title="无匹配案件" desc="试试调整关键词或筛选条件" />
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className={row.getIsSelected() ? "selected" : undefined}
                    onClick={() => navigate(`/cases/${String(row.original.record_id)}`)}
                    title="点击查看案件详情"
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className={NUM_KEYS.has(cell.column.id) ? "num" : undefined}
                        style={density === "compact" ? { padding: "4px 10px" } : undefined}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 分页 + 口径脚注 */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 2px 0", flexWrap: "wrap" }}>
        <span className="muted" style={{ fontSize: 12 }}>
          {isFetching && !isLoading ? "刷新中…" : `第 ${pagination.pageIndex + 1} / ${table.getPageCount()} 页`}
        </span>
        <span className="muted" style={{ fontSize: 12 }}>
          每页
          <select
            value={pagination.pageSize}
            onChange={(e) => setPagination({ pageIndex: 0, pageSize: Number(e.target.value) })}
            style={{ height: 26, marginLeft: 4, border: "1px solid var(--border)", borderRadius: 6, background: "var(--surface)", padding: "0 6px", color: "var(--text)", outline: "none" }}
            aria-label="每页条数"
          >
            {[20, 50, 100].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </span>
        <span className="grow" />
        <button type="button" className="btn btn-sm" disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}>
          ‹ 上一页
        </button>
        <span style={{ fontSize: 12, fontVariantNumeric: "tabular-nums" }}>{pagination.pageIndex + 1} / {table.getPageCount()}</span>
        <button type="button" className="btn btn-sm" disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}>
          下一页 ›
        </button>
      </div>
      {res?.meta.footnote && (
        <div className="footnote" style={{ marginTop: 8 }}>
          📐 {res.meta.footnote} · 导出 CSV 脚注同源
        </div>
      )}

      {/* 批量打标抽屉 */}
      <Drawer
        title={`批量打标（已选 ${selectedIds.length} 件）`}
        open={tagOpen}
        onClose={() => setTagOpen(false)}
        foot={
          <>
            <button type="button" className="btn" onClick={() => setTagOpen(false)}>取消</button>
            <button type="button" className="btn btn-primary" onClick={() => void doTag()}>
              <Tag size={13} /> 应用打标
            </button>
          </>
        }
      >
        <div style={{ display: "grid", gap: 8 }}>
          <label style={{ fontSize: 12, color: "var(--muted)" }}>标签内容（将写入每条案件的脏标记/备注链路，供清洗规则引用）</label>
          <input
            autoFocus
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void doTag()}
            placeholder="如：批量标记-2024-音集协"
            style={{ height: 34, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", padding: "0 10px", outline: "none", color: "var(--text)" }}
            aria-label="标签内容"
          />
        </div>
      </Drawer>

      {/* 列设置抽屉 */}
      <Drawer
        title="列设置"
        open={colOpen}
        onClose={() => setColOpen(false)}
        foot={
          <>
            <button
              type="button"
              className="btn"
              onClick={() => {
                setColDraft(defaultKeys);
                toast("已恢复默认列（后端 DEFAULT_COLUMNS 18 列）");
              }}
            >
              恢复默认
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                if (colDraft.length === 0) {
                  toast("至少保留 1 列", true);
                  return;
                }
                setVisibleKeys(colDraft);
                setColOpen(false);
              }}
            >
              应用
            </button>
          </>
        }
      >
        <p style={{ fontSize: 12, color: "var(--muted-2)", marginBottom: 12 }}>
          勾选表格显示列（默认 = 后端 DEFAULT_COLUMNS 18 列；排序/导出随之生效）
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 4 }}>
          {(meta.fields ?? []).map((f) => (
            <label key={f.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, padding: "3px 2px", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={colDraft.includes(f.key)}
                onChange={(e) =>
                  setColDraft((prev) => (e.target.checked ? [...prev, f.key] : prev.filter((k) => k !== f.key)))
                }
              />
              <span>{f.label}</span>
              {f.in_default && <span className="badge badge-plain">默认</span>}
            </label>
          ))}
        </div>
      </Drawer>
      <div style={{ height: 8 }} />
    </div>
  );
}

/* ---------------------------------------------------------------- 单元格渲染 */

function renderCell(
  k: string,
  row: CaseRow,
  type: string | undefined,
  navigate: ReturnType<typeof useNavigate>,
) {
  const v = row[k];
  const dirty = Array.isArray(row.dirty_flags) ? row.dirty_flags.length > 0 : !!row.dirty_flags;

  switch (k) {
    case "case_no": {
      const id = String(row.record_id ?? "");
      return (
        <span className={dirty ? "dirty-mark" : undefined}>
          <span
            className="link"
            style={{ color: "var(--primary)", fontWeight: 500, textDecoration: "none", cursor: "pointer" }}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/cases/${id}`);
            }}
            title={`${fmtText(v)}${dirty ? "（含脏标记）" : ""}`}
          >
            {fmtText(v)}
          </span>
        </span>
      );
    }
    case "record_id":
      return <span className="muted" style={{ fontSize: 11 }}>{fmtText(v)}</span>;
    case "support_rate": {
      /* D1 修复：null →「—」占位（后端公式未覆盖的仅清洗值） */
      if (v === null || v === undefined || v === "") return <span className="muted">—</span>;
      const n = typeof v === "number" ? v : Number(v);
      if (!Number.isFinite(n)) return <span className="muted">—</span>;
      const pct = Math.abs(n) <= 1 ? n * 100 : n;
      const ratio = Math.min(100, Math.max(0, pct)) / 100;
      return (
        <span className="sup" title={`对方诉求支持率 ${fmtPct(n)}（公式值）`}>
          <span className="track">
            <span className="fill" style={{ width: `${ratio * 100}%` }} />
          </span>
          <span className="val">{fmtPct(n)}</span>
        </span>
      );
    }
    case "defendant":
    case "court":
    case "artist": {
      const arr = Array.isArray(v) ? (v as unknown[]).map(String) : typeof v === "string" && v ? [v] : [];
      if (!arr.length) return <span className="muted">—</span>;
      if (arr.length > 2) {
        return (
          <Tooltip label={arr.join("、")}>
            <span>
              {arr.slice(0, 2).join("、")}
              <span className="badge badge-plain" style={{ marginLeft: 4 }}>+{arr.length - 2}</span>
            </span>
          </Tooltip>
        );
      }
      return <span title={arr.join("、")}>{arr.join("、")}</span>;
    }
    /* cause / biz_line 由列闭包渲染（枚举色驱动），此处跳过 */
    case "case_status":
      return v === null || v === "" ? <span className="muted">—</span> : (
        <Badge tone={statusTone(String(v))}>{String(v)}</Badge>
      );
    case "resolve":
      return v === null || v === "" ? <span className="muted">—</span> : (
        <span style={{ color: RESOLVE_COLOR[resolveTone(String(v))], fontWeight: 500 }}>{String(v)}</span>
      );
    case "song_count": {
      const n = typeof v === "number" ? v : Number(v);
      if (!Number.isFinite(n) || v === null || v === undefined) return <span className="muted">—</span>;
      return <span className="badge badge-plain">{fmtNum(n)}</span>;
    }
    case "dirty_flags":
      return dirty ? <span className="dirty-mark" style={{ color: "var(--warning)", fontWeight: 600 }}>脏</span> : <span className="muted">—</span>;
    case "amount":
    case "pay_amount":
    case "per_song_amount":
    case "lawyer_fee":
      return v === null || v === undefined || v === "" ? <span className="muted">—</span> : <span className="money">{fmtMoney(v)}</span>;
    case "accept_date":
    case "court_date":
    case "close_date":
    case "pay_date":
    case "doc1_date":
    case "doc2_date":
    case "synced_at":
      return fmtDate(v);
    case "year":
    case "merged_count":
      return v === null || v === undefined ? <span className="muted">—</span> : <span>{fmtNum(v)}</span>;
    default:
      return <span>{fmtByDefault(v, type)}</span>;
  }
}

/* 兜底：按字段类型格式化（json → 列表 join） */
function fmtByDefault(v: unknown, type: string | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  if (type === "json") return fmtList(v);
  if (type === "num") return fmtNum(v);
  if (type === "date") return fmtDate(v);
  return fmtText(v);
}

