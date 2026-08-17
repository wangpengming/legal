/* 04-对手方画像（docs/02 §4.4 + plan t13-15 + 原型 04-parties.html）
   列表 /parties：/stats/parties 被告扁平化聚合（频次/胜负/判赔/异地/业务线/占比）；
   详情 /parties/:name：/stats/party 画像（胜诉率A/年份分布/案由分布/近期案件）。
   胜诉率A 口径与指标中心 win_rate_a 一致（5 类胜诉 resolve），异地 = court 不含「北京」。 */
import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Badge, EmptyState, PageError, PageHeader, Spinner, StatCard } from "@/components/common";
import { useParties, useParty } from "@/hooks";
import type { PartyData, PartySummary } from "@/lib/api";
import { fmtList, fmtMoney, fmtNum, fmtPct } from "@/lib/format";
import { resolveTone } from "@/lib/colors";

/* ---------- 样式常量（结对原型 04：logo 渐变 / 年份柱） ---------- */
const LOGO = { background: "linear-gradient(135deg, var(--primary), #60A5FA)", color: "#fff", display: "grid", placeItems: "center", fontWeight: 700, borderRadius: 10, flexShrink: 0 } as const;
const NUM = { textAlign: "right", fontVariantNumeric: "tabular-nums" } as const;
const BAR = { display: "flex", alignItems: "flex-end", gap: 5, height: 46, marginTop: 8 } as const;
const LEGEND = { display: "flex", gap: 14, fontSize: 11, color: "var(--muted)", marginTop: 10, alignItems: "center" } as const;
const LY_ICON = { width: 8, height: 8, borderRadius: 2, display: "inline-block", marginRight: 5 } as const;

/** 名称 → logo 展示字（去括号后缀后取前 2 字） */
function logoOf(name: string): string {
  return name.replace(/[（(][^）)]*[）)]/g, "").slice(0, 2);
}

/* ---------- 对抗历程年份柱（柱高 = 案件数；红 = 含判赔） ---------- */
function YearBars({ years }: { years: PartyData["years"] }) {
  if (!years.length) return <EmptyState title="暂无对抗历程数据" />;
  const maxY = Math.max(...years.map((y) => y.case_count), 1);
  return (
    <>
      <div style={BAR}>
        {years.map((y) => (
          <i
            key={y.year}
            title={`${y.year} 年 ${y.case_count} 件${y.verdict_amount > 0 ? ` · 判赔 ${fmtMoney(y.verdict_amount)}` : ""}`}
            style={{
              flex: 1,
              height: `${Math.max((y.case_count / maxY) * 100, 2)}%`,
              background:
                y.verdict_amount > 0
                  ? "linear-gradient(180deg, var(--danger), color-mix(in srgb, var(--danger) 45%, transparent))"
                  : "linear-gradient(180deg, var(--primary), color-mix(in srgb, var(--primary) 45%, transparent))",
              borderRadius: "3px 3px 0 0",
              minHeight: 3,
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", gap: 5, fontSize: 10, color: "var(--muted-2)", marginTop: 3 }}>
        {years.map((y) => (
          <span key={y.year} style={{ flex: 1, textAlign: "center" }}>{y.year}</span>
        ))}
      </div>
      <div style={LEGEND}>
        <span><i style={{ ...LY_ICON, background: "var(--danger)" }} />含判赔年份</span>
        <span><i style={{ ...LY_ICON, background: "var(--primary)" }} />无判赔年份</span>
      </div>
    </>
  );
}

/* ---------- 案由分布条 ---------- */
function CauseList({ causes }: { causes: PartyData["causes"] }) {
  if (!causes.length) return <EmptyState title="暂无案由分布" />;
  const maxC = causes[0].case_count || 1;
  return (
    <div style={{ display: "grid", gap: 10, marginTop: 4 }}>
      {causes.map((c) => (
        <div key={c.cause}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 4 }}>
            <span>{c.cause} <span style={{ color: "var(--muted)" }}>· {fmtNum(c.case_count)} 件</span></span>
            {c.verdict_amount > 0 && <span style={{ color: "var(--danger)", fontVariantNumeric: "tabular-nums" }}>判赔 {fmtMoney(c.verdict_amount)}</span>}
          </div>
          <div style={{ height: 5, borderRadius: 99, background: "var(--surface-2)", overflow: "hidden" }}>
            <div
              style={{
                width: `${(c.case_count / maxC) * 100}%`,
                height: "100%",
                borderRadius: 99,
                background: c.verdict_amount > 0 ? "var(--danger)" : "var(--primary)",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- 列表视图：/parties ---------- */
function PartyList() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useParties(20);
  if (isLoading) return <Spinner label="聚合对手方…" />;
  if (isError) return <PageError message="对手方聚合加载失败" onRetry={refetch} />;
  const items = data?.items ?? [];
  return (
    <>
      <PageHeader
        title="对手方画像"
        breadcrumb={<>分析 / 对手方画像</>}
        actions={<span style={{ fontSize: 12.5, color: "var(--muted-2)" }}>单击行查看主体画像 · 口径见脚注</span>}
      />
      {items.length === 0 ? (
        <EmptyState title="暂无对手方数据" desc="同步案件后自动聚合" />
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            <StatCard label="对手方主体" value={fmtNum(data!.total_parties)} sub="被告 JSON 数组扁平化去重" />
            <StatCard label="覆盖案件" value={fmtNum(data!.covered_cases)} sub="参与聚合的案件总数" />
            <StatCard
              label="Top 判赔对手"
              value={items[0] ? items[0].name : "—"}
              hint={items[0] ? `${items[0].case_count} 件 · 判赔 ${fmtMoney(items[0].verdict_amount)}` : undefined}
              sub={items[0] ? `${fmtNum(items[0].case_count)} 件 · 判赔 ${fmtMoney(items[0].verdict_amount)}` : undefined}
            />
          </div>
          <div className="card card-pad mt12">
            <div className="card-title">
              对手方 Top {items.length}
              <span className="sub">按案件数 / 判赔额降序</span>
            </div>
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>对手方</th>
                    <th>案件数</th>
                    <th>胜诉率A</th>
                    <th>判赔件数</th>
                    <th>判赔金额</th>
                    <th>异地案件</th>
                    <th>年份跨度</th>
                    <th>业务线</th>
                    <th>占全库</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((p: PartySummary) => (
                    <tr key={p.name} onClick={() => navigate(`/parties/${encodeURIComponent(p.name)}`)} style={{ cursor: "pointer" }} title="查看画像">
                      <td>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                          <i style={{ ...LOGO, width: 30, height: 30, fontSize: 13, borderRadius: 8 }}>{logoOf(p.name)}</i>
                          <span>{p.name}</span>
                        </span>
                      </td>
                      <td style={NUM}>{fmtNum(p.case_count)}</td>
                      <td style={NUM}>{fmtPct(p.win_rate_a)}</td>
                      <td style={NUM}>{fmtNum(p.verdict_count)}</td>
                      <td style={NUM}>{fmtMoney(p.verdict_amount)}</td>
                      <td style={NUM}>{p.offsite_count > 0 ? <span style={{ color: "var(--danger)" }}>{fmtNum(p.offsite_count)}</span> : "0"}</td>
                      <td style={NUM}>{p.first_year && p.last_year ? `${p.first_year}–${p.last_year}` : "—"}</td>
                      <td style={{ maxWidth: 200 }}>{fmtList(p.biz_lines)}</td>
                      <td style={NUM}>{fmtPct(p.share)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="footnote">
              主体清单 = 被告 JSON 数组扁平化聚合 · 胜诉率A = 胜诉类结案/(胜诉+判赔)已结 · 异地 = 法院不含「北京」 · 占全库 = 该主体案件数/全部案件 · 口径 v1.0
            </div>
          </div>
        </>
      )}
    </>
  );
}

/* ---------- 详情视图：/parties/:name ---------- */
function PartyDetail({ name, onBack }: { name: string; onBack: () => void }) {
  const navigate = useNavigate();
  const { data: d, isLoading, isError, refetch } = useParty(name);
  if (isLoading) return <Spinner label={`加载 ${name} 画像…`} />;
  if (isError) return <PageError message={`对手方「${name}」画像加载失败`} onRetry={refetch} />;
  if (!d) return <EmptyState title="未找到该对手方" desc="可能已被清洗规则合并" action={<button className="btn btn-sm" onClick={onBack}>返回列表</button>} />;

  const years = d.years ?? [];
  const firstYear = years.length ? Math.min(...years.map((y) => y.year)) : null;
  const lastYear = years.length ? Math.max(...years.map((y) => y.year)) : null;
  const recent = d.cases ?? [];
  const bizSet = new Set(recent.map((c) => c.biz_line).filter((b): b is string => !!b));
  const avgVerdict = d.verdict_count > 0 ? d.verdict_amount / d.verdict_count : null;
  const offsiteShare = d.total > 0 ? d.offsite_count / d.total : null;

  return (
    <>
      <PageHeader
        title={d.name}
        breadcrumb={
          <>
            <a className="link" style={{ color: "var(--primary)", cursor: "pointer" }} onClick={(e) => { e.preventDefault(); onBack(); }}>对手方画像</a>
            <span style={{ margin: "0 6px", color: "var(--muted)" }}>/</span>
            <b>画像详情</b>
          </>
        }
        actions={
          <button className="btn btn-sm" onClick={onBack}>
            <ArrowLeft size={13} style={{ verticalAlign: -2, marginRight: 4 }} />
            返回列表
          </button>
        }
      />

      {/* 头卡 */}
      <div className="card" style={{ display: "flex", gap: 16, alignItems: "center", padding: 20, marginBottom: 12 }}>
        <div style={{ ...LOGO, width: 52, height: 52, fontSize: 22, borderRadius: 12 }}>{logoOf(d.name)}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 19, fontWeight: 600, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            {d.name}
            <Badge tone="red">主要诉讼对手方</Badge>
            <Badge tone="blue">批量系列案发起方</Badge>
          </div>
          <div style={{ display: "flex", gap: 16, fontSize: 12.5, color: "var(--muted)", marginTop: 5, flexWrap: "wrap" }}>
            <span>我方案件 <b style={{ color: "var(--text)", fontVariantNumeric: "tabular-nums" }}>{fmtNum(d.total)}</b> 件</span>
            {firstYear && <span>首次交锋 <b style={{ color: "var(--text)" }}>{firstYear}</b>{lastYear !== null && lastYear !== firstYear ? `（近年 ${lastYear}）` : ""}</span>}
            <span>关联业务线 {bizSet.size ? fmtList(Array.from(bizSet)) : "—"}</span>
            <span>异地案件 <b style={{ color: d.offsite_count > 0 ? "var(--danger)" : "var(--text)", fontVariantNumeric: "tabular-nums" }}>{fmtNum(d.offsite_count)}</b> 件</span>
          </div>
        </div>
      </div>

      {/* 对抗指标 4 卡 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <StatCard
          label={<>胜诉率（口径A）<span className="help" title="胜诉类结案数 /(胜诉类+判赔)已结 · 与指标中心 win_rate_a 同口径">ⓘ</span></>}
          value={<span style={{ fontSize: 26 }}>{fmtPct(d.win_rate_a)}</span>}
          sub="已结胜负口径 v1.0"
        />
        <StatCard
          label="判赔案件"
          value={<span style={{ fontSize: 26 }}>{fmtNum(d.verdict_count)} 件</span>}
          hint="结案原因=判赔 的案件数"
          sub={`累计判赔 ${fmtMoney(d.verdict_amount)}`}
        />
        <StatCard
          label="案均判赔"
          value={<span style={{ fontSize: 26 }}>{avgVerdict ? fmtMoney(avgVerdict) : "—"}</span>}
          hint="判赔总额 ÷ 判赔件数"
          sub="均值口径"
        />
        <StatCard
          label="异地审理"
          value={<span style={{ fontSize: 26 }}>{fmtNum(d.offsite_count)} 件</span>}
          hint="异地 = court 数组不含「北京」"
          sub={`占比 ${fmtPct(offsiteShare)}`}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: 12, marginTop: 12 }}>
        {/* 左列：对抗历程 + 案由分布 */}
        <div style={{ display: "grid", gap: 12 }}>
          <div className="card card-pad">
            <div className="card-title">
              对抗历程（按年聚合）
              <span className="sub">柱高 = 当年案件数 · 红 = 含判赔</span>
            </div>
            <YearBars years={years} />
          </div>
          <div className="card card-pad">
            <div className="card-title">
              案由分布
              <span className="sub">按案件数降序</span>
            </div>
            <CauseList causes={d.causes ?? []} />
          </div>
        </div>

        {/* 右列：近期案件 */}
        <div className="card card-pad">
          <div className="card-title">
            近期案件
            <span className="sub">最新 {Math.min(recent.length, 8)} 条 · 单击查看案件详情</span>
          </div>
          {recent.length === 0 ? (
            <EmptyState title="暂无案件" />
          ) : (
            <div className="tbl-wrap" style={{ border: "none", borderRadius: 0 }}>
              <table className="tbl" style={{ width: "100%" }}>
                <thead>
                  <tr>
                    <th>案号</th>
                    <th>业务线</th>
                    <th>标的</th>
                    <th>支持率</th>
                    <th>结案原因</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.slice(0, 8).map((c) => {
                    const s01 = c.support_rate != null ? (c.support_rate > 1 ? c.support_rate / 100 : c.support_rate) : null;
                    return (
                      <tr key={c.record_id} onClick={() => navigate(`/cases/${c.record_id}`)} style={{ cursor: "pointer" }}>
                        <td>{c.case_no || "—"}</td>
                        <td>{c.biz_line ?? "—"}</td>
                        <td style={NUM}>{fmtMoney(c.amount)}</td>
                        <td>
                          {s01 == null ? (
                            <span className="sup">
                              <span className="track"><span className="fill" style={{ width: 0, background: "var(--surface-2)" }} /></span>
                              <span className="val">—</span>
                            </span>
                          ) : (
                            <span className="sup" title={`支持率 ${fmtPct(s01)}`}>
                              <span className="track">
                                <span className="fill" style={{ width: `${Math.min(s01 * 100, 100)}%`, background: s01 > 0.15 ? "var(--warning)" : "var(--success)" }} />
                              </span>
                              <span className="val">{fmtPct(s01)}</span>
                            </span>
                          )}
                        </td>
                        <td><Badge tone={resolveTone(c.resolve)}>{c.resolve ?? "—"}</Badge></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* 策略提示（数据驱动） */}
      <div className="alert amber" style={{ marginTop: 12 }}>
        <span className="grow">
          <b>策略提示（基于 {fmtNum(d.total)} 案聚合）：</b>
          {offsiteShare && offsiteShare > 0 ? (
            <>
              该主体 <b>{fmtPct(offsiteShare)}</b> 案件在非北京法院审理（{fmtNum(d.offsite_count)}/{fmtNum(d.total)} 件），异地法院对集体管理类诉求的支持率存在差异，可对比评估管辖策略。
            </>
          ) : (
            <>该主体全部案件由北京法院审理，管辖策略空间有限，建议聚焦案由与授权链条抗辩。</>
          )}
        </span>
      </div>
      <footer className="footnote" style={{ textAlign: "right", marginTop: 8 }}>
        对手方画像由 35 字段中相关字段聚合派生 · 胜诉率A/异地口径见指标卡提示 · 数据截至最近同步
      </footer>
    </>
  );
}

export default function PartiesPage() {
  const { name: rawName } = useParams();
  const navigate = useNavigate();
  /* 路由参数 react-router 已解码，防双解码失败（实体名含 % 等） */
  const name = useMemo(() => {
    if (!rawName) return undefined;
    try {
      return decodeURIComponent(rawName);
    } catch {
      return rawName;
    }
  }, [rawName]);
  return name ? <PartyDetail name={name} onBack={() => navigate("/parties")} /> : <PartyList />;
}