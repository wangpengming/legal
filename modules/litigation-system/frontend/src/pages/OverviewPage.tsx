/* 01-态势总览（docs/02 §4.1 + plan t08-10：638/312/48.9%/42/¥1,284,600 + 8 业务线 + 判赔趋势 + KPI 跳转）。
   数据源：/stats/overview（kpis 8 项指标 + trend + bizline + upcoming_court + summary 摘要）。
   判赔趋势 ECharts 双轴（收案柱 + 判赔金额线），canvas 颜色经 themeColors() 随主题重算。 */
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, CalendarDays, ChevronRight, RefreshCw } from "lucide-react";
import type { EChartsOption } from "echarts";
import { Chart } from "@/components/Chart";
import { Badge, PageError, PageHeader, Spinner, StatCard, SyncBar } from "@/components/common";
import { useDirtyItems, useOverview, useSyncStatus } from "@/hooks";
import { fmtDate, fmtMoney, fmtNum, fmtPct } from "@/lib/format";
import { PALETTE, resolveTone, themeColors, TONE_CLASS } from "@/lib/colors";
import { useUiStore } from "@/stores/ui";

/* 开庭倒计时 → 徽章（今天红 / 7 天内琥珀 / 其余灰） */
function courtBadge(ms: number | null): { label: string; cls: string } {
  if (ms === null || ms === undefined) return { label: "已排期", cls: "badge-plain" };
  const days = Math.ceil((ms - Date.now()) / 86_400_000);
  if (days <= 0) return { label: "今日开庭", cls: TONE_CLASS.red };
  if (days <= 7) return { label: `${days} 天后`, cls: TONE_CLASS.amber };
  return { label: `${days} 天后`, cls: TONE_CLASS.gray };
}

/* 开庭日程行（原型 01 schedule-item 结构，样式内联——components.css 未迁移此组件） */
const SCH = {
  item: { display: "flex", alignItems: "center", gap: 12, padding: "10px 2px", borderBottom: "1px solid var(--border)", cursor: "pointer" } as const,
  date: { width: 62, textAlign: "center", borderRadius: 8, background: "var(--surface-2)", padding: "5px 0", flexShrink: 0 } as const,
  month: { fontSize: 11, color: "var(--muted)" },
  day: { fontSize: 16, fontWeight: 600, fontVariantNumeric: "tabular-nums" as const },
  main: { flex: 1, minWidth: 0 },
  title: { fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const },
  meta: { fontSize: 11, color: "var(--muted-2)", marginTop: 2, display: "flex", gap: 6, alignItems: "center" },
};

export default function OverviewPage() {
  const navigate = useNavigate();
  const theme = useUiStore((s) => s.theme); // 订阅主题，图表重算
  const { data, isLoading, isError, refetch } = useOverview();
  const sync = useSyncStatus();
  const dirty = useDirtyItems();

  const kpis = data?.kpis ?? [];
  const open = kpis.find((k) => k.key === "open_count");
  const cycle = kpis.find((k) => k.key === "cycle");
  const summary = data?.summary;
  const total = summary?.total_cases ?? 0;
  const acmc = summary?.acmc_cases ?? 0;
  const pct = total > 0 ? acmc / total : null;

  const dirtyCount = (dirty.data ?? []).length;
  const syncOk = sync.data && !sync.data.running;
  const syncState = syncOk ? "ok" : sync.data?.running ? "err" : "warn";

  const trend = useMemo(() => data?.trend ?? [], [data]);
  const chartOption = useMemo<EChartsOption>(() => {
    const c = themeColors();
    const years = trend.map((t) => String(t.year ?? "—"));
    return {
      color: [PALETTE[0], PALETTE[4]],
      grid: { left: 6, right: 6, top: 30, bottom: 0, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { data: ["收案", "判赔金额"], top: 0, itemWidth: 14, textStyle: { color: c.muted, fontSize: 11 } },
      xAxis: {
        type: "category",
        data: years,
        axisLine: { lineStyle: { color: c.border } },
        axisTick: { show: false },
        axisLabel: { color: c.muted },
      },
      yAxis: [
        {
          type: "value",
          name: "件",
          nameTextStyle: { color: c.muted, fontSize: 10 },
          axisLabel: { color: c.muted },
          splitLine: { lineStyle: { color: c.border, type: "dashed" } },
        },
        {
          type: "value",
          name: "万元",
          nameTextStyle: { color: c.muted, fontSize: 10 },
          axisLabel: { color: c.muted, formatter: (v: number) => `${(v / 10000).toFixed(0)}` },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "收案",
          type: "bar",
          data: trend.map((t) => t.case_count),
          barMaxWidth: 22,
          itemStyle: { borderRadius: [3, 3, 0, 0] },
        },
        {
          name: "判赔金额",
          type: "line",
          yAxisIndex: 1,
          data: trend.map((t) => t.verdict_amount ?? 0),
          smooth: true,
          symbolSize: 6,
          lineStyle: { width: 2 },
        },
      ],
    };
  }, [trend, theme]);

  if (isLoading) return <Spinner label="态势总览加载中…" />;
  if (isError || !data) return <PageError message="overview 数据加载失败" onRetry={() => void refetch()} />;

  const bizMax = Math.max(...data.bizline.map((b) => b.case_count), 1);

  return (
    <div>
      <PageHeader
        title="态势总览"
        breadcrumb={
          <>
            数字卡：全库 / 音集协 / 在办 / 本月新收 · 判赔累计 · 平均结案周期；下方：判赔趋势 / 业务线 / 开庭日程
          </>
        }
        actions={
          <button className="btn btn-primary btn-sm" onClick={() => navigate("/search")}>
            案件检索 →
          </button>
        }
      />

      {sync.data && (
        <SyncBar kind={syncState} icon={<RefreshCw size={13} />}>
          {sync.data.running ? (
            <>同步进行中（job #{sync.data.running_job_id ?? "—"}）…</>
          ) : (
            <>上次同步 {sync.data.last ? `${sync.data.last.type} · ${sync.data.last.status} · ${fmtNum(sync.data.last.total)} 条` : "从未同步"}</>
          )}
          <span className="muted" style={{ marginLeft: 14 }}>
            下一次 {sync.data.next_at ?? "未排期"}
          </span>
          {dirtyCount > 0 && (
            <span className="grow" style={{ textAlign: "right", fontWeight: 500 }}>
              <AlertTriangle size={12} style={{ verticalAlign: "-2px", marginRight: 4 }} />
              {dirtyCount} 项脏数据待确认
              <a style={{ marginLeft: 6, color: "inherit", textDecoration: "underline" }} onClick={(e) => { e.preventDefault(); navigate("/dicts"); }}>
                清洗台 →
              </a>
            </span>
          )}
        </SyncBar>
      )}

      {/* 基线 4 卡：全库 / 音集协 / 在办 / 本月新收 */}
      <div className="stat-row">
        <StatCard
          label="全库案件"
          value={fmtNum(total)}
          hint="全表案件数，与检索页命中数一致（口径 v1.0）"
          onClick={() => navigate("/search")}
          sub="检索可全字段过滤"
        />
        <StatCard
          label="音集协系列案"
          value={fmtNum(acmc)}
          hint="原告/被告含「音集协」的案件"
          onClick={() => navigate("/search?q=%E9%9F%B3%E9%9B%86%E5%8D%8F")}
          sub={
            <>
              <span className="badge badge-plain" style={{ marginRight: 4 }}>占比 {pct === null ? "—" : fmtPct(pct)}</span>
              原告 = 音集协
            </>
          }
        />
        <StatCard
          label="在办案件"
          value={fmtNum(open?.value)}
          hint={open?.definition}
          onClick={() => navigate("/search")}
        />
        <StatCard
          label="本月新收"
          value={fmtNum(summary?.monthly_new)}
          hint="本月（收案日期）新收案件数"
          onClick={() => navigate("/search")}
          sub={`${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")} 新收`}
        />
      </div>

      {/* 金额/周期 2 卡 */}
      <div className="stat-row">
        <StatCard
          label="判赔累计"
          value={fmtMoney(summary?.verdict_total)}
          hint="结案原因=判赔 的支付金额合计（口径 v1.0）"
          onClick={() => navigate("/search?q=%E5%88%A4%E8%B5%94")}
          sub="结案=判赔 · 支付金额合计"
        />
        <StatCard
          label="平均结案周期"
          value={cycle?.value === null || cycle?.value === undefined ? "—" : `${fmtNum(cycle.value)} 天`}
          hint={cycle?.definition}
          onClick={() => navigate("/search")}
          sub="口径 v1.0 · 已结案件"
        />
      </div>

      <div className="grid-2">
        <div className="col">
          {/* 判赔趋势（ECharts 双轴） */}
          <div className="card card-pad">
            <div className="card-title">
              判赔趋势
              <span className="sub">按收案年份 · 收案件数 + 判赔金额</span>
            </div>
            {trend.length ? (
              <Chart option={chartOption} height={236} />
            ) : (
              <div className="empty" style={{ padding: "40px 0" }}>暂无趋势数据</div>
            )}
            <div className="footnote">📐 判赔金额 = 结案原因「判赔」的支付金额合计（元）· 口径 v1.0 · 版本见 08 页</div>
          </div>

          {/* 待人工确认 */}
          <div className="card card-pad">
            <div className="card-title">
              待人工确认
              <Badge tone={dirtyCount > 0 ? "amber" : "green"}>{dirtyCount > 0 ? `${dirtyCount} 项` : "已清零"}</Badge>
              <span className="help" title="清洗引擎无法自动决策的脏值，需人工采纳/忽略">ⓘ</span>
              <span className="sub">
                <a
                  className="link"
                  onClick={(e) => { e.preventDefault(); navigate("/dicts"); }}
                  style={{ color: "var(--primary)", cursor: "pointer" }}
                >
                  清洗台 →
                </a>
              </span>
            </div>
            {dirty.data && dirty.data.length > 0 ? (
              <table className="tbl">
                <thead>
                  <tr>
                    <th>案件号</th>
                    <th>字段</th>
                    <th>原始值</th>
                    <th>末次规则</th>
                    <th style={{ textAlign: "right" }}>追溯</th>
                  </tr>
                </thead>
                <tbody>
                  {dirty.data.slice(0, 5).map((d, i) => (
                    <tr key={`${d.record_id}-${d.field}-${i}`}>
                      <td className="muted">{d.case_no ?? d.record_id}</td>
                      <td>{d.field}</td>
                      <td className="muted">{d.raw_value ?? "—"}</td>
                      <td>{d.trace.length ? (d.trace[d.trace.length - 1].rule_tag ?? "—") : "—"}</td>
                      <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{d.trace.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty">✅ 暂无待确认脏数据</div>
            )}
          </div>
        </div>

        <div className="col">
          {/* 业务线构成 */}
          <div className="card card-pad">
            <div className="card-title">
              业务线构成
              <span className="sub">{data.bizline.length} 条</span>
            </div>
            <div>
              {data.bizline.map((b) => (
                <div key={b.biz_line} className="row" style={{ marginBottom: 9 }}>
                  <span style={{ width: 74, fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{b.biz_line}</span>
                  <div className="progress grow">
                    <i style={{ width: `${(b.case_count / bizMax) * 100}%` }} />
                  </div>
                  <span style={{ width: 30, textAlign: "right", fontSize: 12, fontVariantNumeric: "tabular-nums" }}>{fmtNum(b.case_count)}</span>
                  <span style={{ width: 44, textAlign: "right", fontSize: 11, color: "var(--muted-2)", fontVariantNumeric: "tabular-nums" }}>{fmtPct(b.case_count / total)}</span>
                </div>
              ))}
            </div>
            <div className="footnote">📐 占比 = 各业务线案件数 / 全库案件数</div>
          </div>

          {/* 开庭日程 */}
          <div className="card card-pad">
            <div className="card-title">
              <CalendarDays size={14} />
              开庭日程
              <span className="sub">{data.upcoming_court.length} 场</span>
            </div>
            {data.upcoming_court.length ? (
              <div>
                {data.upcoming_court.slice(0, 7).map((c) => {
                  const b = courtBadge(c.court_date);
                  const d = fmtDate(c.court_date);
                  return (
                    <div key={c.record_id} style={SCH.item} onClick={() => navigate(`/cases/${c.record_id}`)}>
                      <div style={SCH.date}>
                        <div style={SCH.month}>{d === "—" ? "—" : d.slice(5, 7)}月</div>
                        <div style={SCH.day}>{d === "—" ? "——" : d.slice(8, 10)}</div>
                      </div>
                      <div style={SCH.main}>
                        <div style={SCH.title}>{c.case_no ?? c.record_id}</div>
                        <div style={SCH.meta}>
                          <span>{c.year ? `${c.year} 年` : ""}</span>
                          <span className={TONE_CLASS[resolveTone(c.resolve)]}>{c.resolve ?? "—"}</span>
                        </div>
                      </div>
                      <div style={{ flexShrink: 0 }}>
                        <span className={`badge ${b.cls}`}>{b.label}</span>
                      </div>
                      <ChevronRight size={14} style={{ flexShrink: 0, color: "var(--muted-2)" }} />
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty">暂无已排期开庭</div>
            )}
            <div className="footnote">📐 开庭 = 未来 20 天窗口（court_date ≥ now）· 点击进入案件详情</div>
          </div>
        </div>
      </div>

      <div className="footnote">
        <AlertTriangle size={12} />
        指标口径 v1.0（8 项，见 08 页）：{kpis.map((k) => k.title).join(" / ")}。数字与检索页/口径中心/导出 CSV 脚注同源。
      </div>
      <div style={{ height: 8 }} />
    </div>
  );
}