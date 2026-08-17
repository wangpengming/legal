/* 05-多维分析（docs/02 §4.6 + plan t16-17 + 原型 05-analysis.html）
   三维热力矩阵（业务线×年份 / 案由×年份 / 支付主体×状态）+ 热力下钻：
   点击单元格 → 面包屑同步 + 下钻面板（案由分布可二次下钻 + 案件明细）→「在检索中打开」。
   判赔占比口径与指标中心一致（结案原因 = 判赔）；year=-1 脏值后端已剔除。 */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, EmptyState, PageError, PageHeader, Spinner } from "@/components/common";
import { useAnalysis, useAnalysisDrill } from "@/hooks";
import type { AnalysisDim, AnalysisSel } from "@/lib/api";
import { fmtList, fmtMoney, fmtNum } from "@/lib/format";
import { resolveTone } from "@/lib/colors";

/* ---------- 维度切换 ---------- */
const DIMS: { key: AnalysisDim; label: string; desc: string }[] = [
  { key: "bizYear", label: "业务线 × 年份", desc: "行 = 业务线 · 列 = 收案年份" },
  { key: "causeYear", label: "案由 × 年份", desc: "行 = 案由 · 列 = 收案年份" },
  { key: "payerStatus", label: "支付主体 × 状态", desc: "行 = 支付主体 · 列 = 案件状态" },
];

/* ---------- 热力分位色（结对原型 heatClass：≤5/10/20/35 → 12/28/48/72/100% 主色） ---------- */
const HEAT_STEPS: [number, number][] = [
  [5, 12],
  [10, 28],
  [20, 48],
  [35, 72],
  [Infinity, 100],
];
function heatBg(n: number): string {
  if (n <= 0) return "var(--surface-2)";
  const pct = HEAT_STEPS.find(([max]) => n <= max)?.[1] ?? 100;
  return `color-mix(in srgb, var(--primary) ${pct}%, var(--surface))`;
}

const NUM = { textAlign: "right", fontVariantNumeric: "tabular-nums" } as const;

export default function AnalysisPage() {
  const navigate = useNavigate();
  const [dim, setDim] = useState<AnalysisDim>("bizYear");
  const [sel, setSel] = useState<AnalysisSel>({});
  const { data: m, isLoading, isError, refetch } = useAnalysis(dim);
  const { data: drill, isFetching: drillFetching } = useAnalysisDrill(dim, sel);

  /* 维度切换 → 清空下钻 */
  const switchDim = (k: AnalysisDim) => {
    setDim(k);
    setSel({});
  };

  const crumbs = useMemo(() => {
    const out = [
      <button key="all" className="link" style={{ color: "var(--primary)", cursor: "pointer" }} onClick={() => setSel({})}>全部</button>,
    ];
    if (sel.x) {
      out.push(<span key="s0" style={{ margin: "0 6px", color: "var(--muted)" }}>/</span>);
      out.push(
        <button key="x" className="link" style={{ color: "var(--primary)", cursor: "pointer" }} onClick={() => setSel({ x: sel.x })}>{sel.x}</button>,
      );
    }
    if (sel.col) {
      out.push(<span key="s1" style={{ margin: "0 6px", color: "var(--muted)" }}>/</span>);
      out.push(
        <button key="col" className="link" style={{ color: "var(--primary)", cursor: "pointer" }} onClick={() => setSel({ x: sel.x, col: sel.col })}>{sel.col}</button>,
      );
    }
    if (sel.cause) {
      out.push(<span key="s2" style={{ margin: "0 6px", color: "var(--muted)" }}>/</span>);
      out.push(<b key="cause" style={{ color: "var(--text)" }}>{sel.cause}</b>);
    }
    return out;
  }, [sel]);

  const drillTitle = useMemo(() => {
    if (!sel.x) return "";
    const parts = [sel.x, sel.col ? `${sel.col} 年` : "全部年份", sel.cause].filter(Boolean);
    return `${parts.join(" · ")} · ${drillFetching ? "…" : `${fmtNum(drill?.total ?? 0)} 件案件`}`;
  }, [sel, drill, drillFetching]);

  const maxRowW = useMemo(() => (m ? m.rows.reduce((a, r) => Math.max(a, r.length), 6) : 6), [m]);

  return (
    <>
      <PageHeader
        title="多维分析"
        breadcrumb={<>分析 / 多维分析 · 下钻协议：点击单元格 → 面包屑同步 → 案由分布 → 案件明细</>}
        actions={
          <div style={{ display: "flex", gap: 6 }}>
            {DIMS.map((d) => (
              <button
                key={d.key}
                className={`btn btn-sm ${dim === d.key ? "btn-primary" : ""}`}
                style={{ fontSize: 12.5 }}
                onClick={() => switchDim(d.key)}
                title={d.desc}
              >
                {d.label}
              </button>
            ))}
          </div>
        }
      />

      {/* 面包屑 */}
      <div className="crumb-path" style={{ display: "flex", alignItems: "center", fontSize: 12.5, marginBottom: 10, flexWrap: "wrap" }}>
        {crumbs}
        {!sel.x && (
          <span className="sub" style={{ marginLeft: 6 }}>未选择维度 → 点击上方热力单元格下钻</span>
        )}
      </div>

      {isLoading ? (
        <Spinner label="聚合三维矩阵…" />
      ) : isError ? (
        <PageError message="多维分析加载失败" onRetry={refetch} />
      ) : !m || m.rows.length === 0 ? (
        <EmptyState title="暂无分析数据" desc="同步案件后自动聚合三维矩阵" />
      ) : (
        <>
          {/* 热力图 */}
          <div className="card card-pad">
            <div className="card-title">
              案件数热力（n = 案件数 · p = 判赔占比）
              <span className="help" title="颜色深浅 = 案件数密度（h1~h5 分位）">ⓘ</span>
              <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--muted-2)" }}>
                <i style={{ width: 10, height: 10, borderRadius: 3, display: "inline-block", background: "color-mix(in srgb, var(--primary) 12%, var(--surface))" }} />
                少
                <i style={{ width: 10, height: 10, borderRadius: 3, display: "inline-block", background: "color-mix(in srgb, var(--primary) 48%, var(--surface))" }} />
                中
                <i style={{ width: 10, height: 10, borderRadius: 3, display: "inline-block", background: "var(--primary)" }} />
                多
              </span>
            </div>
            <div className="tbl-wrap">
              <table className="tbl" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ width: "max-content", minWidth: `calc(${maxRowW}ch * 1.05)` }}>{m.row_label} ＼ {m.col_label}</th>
                    {m.cols.map((c) => (
                      <th key={c} style={{ textAlign: "center", width: 84 }}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {m.rows.map((r, ri) => (
                    <tr key={r}>
                      <td style={{ fontWeight: 500, whiteSpace: "nowrap" }}>{r}</td>
                      {m.cols.map((c, ci) => {
                        const cell = m.cells[ri]?.[ci];
                        if (!cell || cell.case_count === 0) {
                          return (
                            <td key={c} style={{ padding: 4, textAlign: "center" }}>
                              <div style={{ minHeight: 40, borderRadius: 8 }} title={`${r} · ${c} · 0 件`} />
                            </td>
                          );
                        }
                        const rate = cell.verdict_count > 0 ? (cell.verdict_count / cell.case_count) * 100 : 0;
                        const active = sel.x === r && sel.col === c;
                        return (
                          <td key={c} style={{ padding: 4, textAlign: "center" }}>
                            <div
                              className="hcell"
                              title={`${r} · ${c} · ${cell.case_count} 件 · 判赔 ${rate.toFixed(0)}%`}
                              onClick={() => setSel((prev) => ({ x: r, col: c, ...(prev.cause && prev.x === r ? { cause: prev.cause } : {}) }))}
                              style={{
                                minHeight: 40,
                                display: "grid",
                                placeItems: "center",
                                borderRadius: 8,
                                cursor: "pointer",
                                background: heatBg(cell.case_count),
                                outline: active ? "2px solid var(--text)" : "none",
                                outlineOffset: 1,
                              }}
                            >
                              <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{cell.case_count}</span>
                              <span style={{ fontSize: 9.5, opacity: 0.78 }}>{rate.toFixed(0)}%赔</span>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="footnote">
              聚合口径：{m.row_label} = 字段精确匹配 · {m.col_label} = {m.col_label === "年份" ? "收案年份" : "状态字段"} · 判赔占比 = 结案原因「判赔」· 覆盖 {fmtNum(m.total_cases)} 案 · 口径 v1.0
            </div>
          </div>

          {/* 下钻面板 */}
          {sel.x && (
            <div className="drill-panel" style={{ marginTop: 14 }}>
              <div className="card card-pad">
                <div className="card-title">{drillTitle}</div>
                {drillFetching ? (
                  <Spinner label="下钻明细加载中…" />
                ) : drill && drill.items.length === 0 ? (
                  <EmptyState title="该组合下暂无案件" desc="可点击面包屑回退一级调整下钻条件" />
                ) : (
                  <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
                    {/* 案由分布（二次下钻） */}
                    <div style={{ flex: 1, minWidth: 260 }}>
                      <div className="stat-label" style={{ marginBottom: 8, fontSize: 12 }}>
                        按案由分布（点击切换下钻）
                      </div>
                      {drill && drill.causes.length === 0 ? (
                        <div className="sub" style={{ fontSize: 12 }}>行即案由，无需二次下钻</div>
                      ) : (
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 6 }}>
                          {(drill?.causes ?? []).map((cau) => {
                            const active = sel.cause === cau.cause;
                            return (
                              <div
                                key={cau.cause}
                                onClick={() =>
                                  setSel((prev) => ({
                                    x: prev.x,
                                    col: prev.col,
                                    cause: active ? undefined : cau.cause,
                                  }))
                                }
                                title={cau.cause}
                                style={{
                                  padding: "8px 10px",
                                  borderRadius: 8,
                                  background: heatBg(cau.case_count),
                                  cursor: "pointer",
                                  outline: active ? "2px solid var(--text)" : "none",
                                  outlineOffset: 1,
                                  fontSize: 12,
                                }}
                              >
                                <b style={{ fontVariantNumeric: "tabular-nums" }}>{fmtNum(cau.case_count)}</b>
                                <span className="sub" style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {cau.cause}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* 案件明细 */}
                    <div style={{ flex: 1.4, minWidth: 400 }}>
                      <div className="stat-label" style={{ marginBottom: 8, fontSize: 12 }}>
                        案件明细（{fmtNum(drill!.total)} 件 · 单击行查看详情）
                      </div>
                      <div className="tbl-wrap" style={{ border: "none", borderRadius: 0 }}>
                        <table className="tbl" style={{ width: "100%" }}>
                          <thead>
                            <tr>
                              <th>案号</th>
                              <th>对方</th>
                              <th>标的</th>
                              <th>判赔</th>
                              <th>结案原因</th>
                            </tr>
                          </thead>
                          <tbody>
                            {drill!.items.map((it) => (
                              <tr key={it.record_id} onClick={() => navigate(`/cases/${it.record_id}`)} style={{ cursor: "pointer" }}>
                                <td>{it.case_no || "—"}</td>
                                <td>{it.defendant && it.defendant.length ? fmtList(it.defendant) : "—"}</td>
                                <td style={NUM}>{fmtMoney(it.amount)}</td>
                                <td style={NUM}>{it.pay_amount != null ? fmtMoney(it.pay_amount) : "—"}</td>
                                <td><Badge tone={resolveTone(it.resolve)}>{it.resolve ?? "—"}</Badge></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
                <div className="card-hint" style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  下钻条件已序列化：
                  <code style={{ background: "var(--surface-2)", padding: "2px 8px", borderRadius: 6, fontSize: 11.5 }}>
                    /analysis?dim={dim}&amp;x={encodeURIComponent(sel.x || "")}&amp;col={sel.col || ""}{sel.cause ? `&amp;cause=${encodeURIComponent(sel.cause)}` : ""}
                  </code>
                  <button
                    className="btn btn-sm btn-ghost"
                    style={{ height: 24, fontSize: 11, marginLeft: "auto" }}
                    onClick={() => navigate(`/search?q=${encodeURIComponent(sel.cause || sel.x || "")}`)}
                  >
                    在检索中打开 →
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
      <footer className="footnote" style={{ textAlign: "right", marginTop: 8 }}>
        多维分析由案件 35 字段按维度聚合派生 · 判赔/年份口径见脚注 · 数据截至最近同步
      </footer>
    </>
  );
}