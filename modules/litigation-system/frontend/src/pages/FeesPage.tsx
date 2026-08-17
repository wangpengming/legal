/* 07-费用看板（docs/02 §4.8 + plan t20 + 原型 07-fees.html）
   four 四值：判赔 / 获赔（支付时间存在近似）/ 支出（台账未接入置待接入）/ 净费用；
   月度判赔金额柱状 + 金额存疑清单（dirty_flags 命中金额字段）。 */
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { EmptyState, PageError, PageHeader, Spinner, StatCard } from "@/components/common";
import { useFees } from "@/hooks";
import { fmtMoney, fmtNum } from "@/lib/format";

const NUM = { textAlign: "right", fontVariantNumeric: "tabular-nums" } as const;

/* 存疑原始金额：可解析为数字则格式化，否则原样展示（如 "66,00?"） */
function rawMoney(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? fmtMoney(n) : String(v);
}

/* 元 → 万元短格式（柱状图标签用） */
const fmtWan = (v: number | null | undefined): string => (v == null ? "—" : `¥${(v / 10000).toFixed(1)}万`);

export default function FeesPage() {
  const navigate = useNavigate();
  const { data: d, isLoading, isError, refetch } = useFees();

  const four = d?.four;
  const monthly = useMemo(() => d?.monthly ?? [], [d]);
  const dubious = useMemo(() => d?.dubious ?? [], [d]);
  const maxM = useMemo(() => monthly.reduce((a, r) => Math.max(a, r.amount ?? 0), 0), [monthly]);

  const recoveredRate =
    four && four.recovered.count != null && four.verdict.count > 0
      ? ((four.recovered.count / four.verdict.count) * 100).toFixed(1)
      : null;

  const verdictAvg =
    four && four.verdict.count > 0 ? (four.verdict.amount ?? 0) / four.verdict.count : null;

  return (
    <>
      <PageHeader
        title="费用看板"
        breadcrumb={<>分析 / 费用看板 · 判赔 / 获赔 / 支出三流分离，全部来自金额字段清洗（R03 金额归一）</>}
        actions={
          dubious.length > 0 ? (
            <span className="badge status-amber" style={{ height: 24 }}>
              <i className="dot" />
              {fmtNum(dubious.length)} 条金额存疑待确认
            </span>
          ) : (
            <span className="badge status-green" style={{ height: 24 }}>
              <i className="dot" />
              无金额存疑
            </span>
          )
        }
      />

      {isLoading ? (
        <Spinner label="聚合费用三流…" />
      ) : isError ? (
        <PageError message="费用看板加载失败" onRetry={refetch} />
      ) : !four ? (
        <EmptyState title="暂无费用数据" desc="同步并清洗金额字段后自动聚合" />
      ) : (
        <>
          {/* KPI 4 卡 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 16 }}>
            <StatCard
              label="累计判赔金额"
              value={<span style={{ color: "var(--danger)", fontSize: 25 }}>{fmtMoney(four.verdict.amount)}</span>}
              delta={`判赔 ${fmtNum(four.verdict.count)} 件 · 均值 ${verdictAvg ? fmtMoney(verdictAvg) : "—"}`}
              hint="判赔金额 = 结案原因「判赔」案件的支付金额合计"
            />
            <StatCard
              label="累计获赔（执行到位）"
              value={
                <span style={{ color: "var(--success)", fontSize: 25 }}>
                  {four.recovered.amount != null ? fmtMoney(four.recovered.amount) : "待接入"}
                </span>
              }
              delta={
                recoveredRate
                  ? `支付到位率 ${recoveredRate}% · ${fmtNum(four.recovered.count ?? 0)} 件`
                  : "支付时间字段缺失，暂无法估算"
              }
              hint={four.recovered.hint}
            />
            <StatCard
              label="累计支出"
              value={<span style={{ fontSize: 25 }}>{four.expense.amount != null ? fmtMoney(four.expense.amount) : "待接入"}</span>}
              delta="费用台账（Phase 2 §2.5）接入后展示律师费/公证费构成"
              hint={four.expense.hint}
            />
            <StatCard
              label="净费用（支出 − 获赔）"
              value={
                <span style={{ color: four.net.amount != null && four.net.amount < 0 ? "var(--success)" : "var(--warning)", fontSize: 25 }}>
                  {four.net.amount != null ? fmtMoney(four.net.amount) : "待接入"}
                </span>
              }
              delta="负值 = 净流入（判赔覆盖支出）"
              hint={four.net.hint}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 14 }}>
            {/* 月度判赔柱状 */}
            <div className="card card-pad">
              <div className="card-title">
                月度判赔金额（支付登记）
                <span className="help" title="按 pay_date 归月；柱高 = 当月判赔支付金额合计">ⓘ</span>
                <span className="legend" style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--muted-2)" }}>
                  <i style={{ width: 10, height: 10, borderRadius: 3, display: "inline-block", background: "var(--danger)" }} />
                  判赔金额
                </span>
              </div>
              {monthly.length === 0 ? (
                <EmptyState title="暂无月度支付记录" desc="判赔案件存在 pay_date 后按月度聚合" />
              ) : (
                <>
                  <div style={{ display: "flex", alignItems: "flex-end", gap: 12, height: 172, padding: "8px 4px 0", overflowX: "auto" }}>
                    {monthly.map((r) => {
                      const h = maxM > 0 && r.amount ? Math.max((r.amount / maxM) * 100, 4) : 4;
                      return (
                        <div key={r.m} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", minWidth: 34, height: "100%", gap: 4 }}>
                          <span style={{ fontSize: 10, color: "var(--muted-2)", whiteSpace: "nowrap" }}>{fmtWan(r.amount)}</span>
                          <div
                            title={`${r.m} · ${r.cnt} 件 · ${fmtMoney(r.amount)}`}
                            style={{
                              width: 22,
                              height: `${h}%`,
                              borderRadius: "4px 4px 0 0",
                              background: "linear-gradient(180deg, var(--danger), color-mix(in srgb, var(--danger) 55%, transparent))",
                            }}
                          />
                          <span style={{ fontSize: 10.5, color: "var(--muted-2)" }}>{r.m.slice(5)}月</span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="footnote">
                    口径：判赔金额 = 结案原因「判赔」且支付时间存在 · 覆盖 {fmtNum(monthly.reduce((a, r) => a + r.cnt, 0))} 件
                  </div>
                </>
              )}
            </div>

            {/* 存疑清单 */}
            <div className="card" style={{ minWidth: 0 }}>
              <div className="card-head" style={{ display: "flex", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                <div className="card-title" style={{ margin: 0 }}>
                  金额存疑清单
                  <span className="help" style={{ marginLeft: 6 }} title="dirty_flags 命中金额类字段的案件（上限 100 条）">ⓘ</span>
                </div>
              </div>
              {dubious.length === 0 ? (
                <EmptyState title="暂无存疑金额" desc="R03 金额归一清洗后无脏标记" />
              ) : (
                <div className="tbl-wrap" style={{ border: "none", borderRadius: 0, maxHeight: 340, overflowY: "auto" }}>
                  <table className="tbl" style={{ width: "100%" }}>
                    <thead>
                      <tr>
                        <th>案号</th>
                        <th style={{ textAlign: "right" }}>标的</th>
                        <th style={{ textAlign: "right" }}>判赔</th>
                        <th>脏标记</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dubious.map((r, i) => {
                        const flags = Array.isArray(r.dirty_flags) ? (r.dirty_flags as string[]) : [];
                        return (
                          <tr key={`${String(r.record_id)}-${i}`} onClick={() => r.record_id && navigate(`/cases/${String(r.record_id)}`)} style={{ cursor: "pointer" }}>
                            <td>
                              {String(r.case_no ?? "—")}
                              {flags.length > 0 && <span className="dirty-mark" style={{ marginLeft: 4 }}>⚠</span>}
                            </td>
                            <td style={NUM}>{rawMoney(r.amount)}</td>
                            <td style={NUM}>{rawMoney(r.pay_amount)}</td>
                            <td>
                              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                                {flags.map((f) => (
                                  <span key={f} className="badge badge-outline" style={{ fontSize: 10.5, padding: "0 6px", margin: 0 }}>
                                    {f}
                                  </span>
                                ))}
                                {flags.length === 0 && <span style={{ fontSize: 11, color: "var(--muted-2)" }}>{String(r.resolve ?? "—")}</span>}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="card-hint" style={{ padding: "10px 16px" }}>
                金额字段清洗管道：R03 金额归一（元）· ⚠ = 存疑标记（单位歧义 / 缺币种）· 行点击进入案件详情
              </div>
            </div>
          </div>
        </>
      )}

      <footer className="footnote" style={{ textAlign: "right", marginTop: 8 }}>
        费用口径 v1.0：判赔 / 获赔 / 支出三流分离 · 获赔 = 支付时间存在近似 · 支出 = 台账未接入 · 数据截至最近同步
      </footer>
    </>
  );
}