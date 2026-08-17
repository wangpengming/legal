/* 06-歌曲维度（docs/02 §4.7 + plan t18-19 + 原型 06-songs.html）
   TOP 涉诉歌曲 = songs×song_case 关联聚合（案件数降序 TOP 50）；
   单曲判赔 = 判赔案件支付金额 ÷ 涉案歌曲槽位（口诀 ¥870 口径）；
   风险规则（简化引擎）：涉案 ≥10 高 / ≥5 中 / 其余低；行点击 → 检索页按歌名打开。 */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, EmptyState, PageError, PageHeader, Spinner, StatCard } from "@/components/common";
import { useSongs } from "@/hooks";
import { fmtMoney, fmtNum } from "@/lib/format";
import type { Tone } from "@/lib/colors";

const NUM = { textAlign: "right", fontVariantNumeric: "tabular-nums" } as const;

function riskOf(n: number): { tone: Tone; label: string } {
  if (n >= 10) return { tone: "red", label: "高" };
  if (n >= 5) return { tone: "amber", label: "中" };
  return { tone: "green", label: "低" };
}

export default function SongsPage() {
  const navigate = useNavigate();
  const [kw, setKw] = useState("");
  const { data: d, isLoading, isError, refetch } = useSongs();

  const songs = d?.songs ?? [];
  const agg = d?.aggregate;
  const top = songs[0];

  const freq = useMemo(() => songs.filter((s) => s.case_count >= 5), [songs]);
  const freqCases = useMemo(() => freq.reduce((a, s) => a + s.case_count, 0), [freq]);
  const totalCases = useMemo(() => songs.reduce((a, s) => a + s.case_count, 0), [songs]);

  /* 风险提示：涉案最多且 ≥5 案的曲目（相对全库单曲判赔对比） */
  const warn = useMemo(() => {
    if (!freq.length || agg === undefined) return null;
    const s = freq[0];
    const avg = s.verdict_amount != null && s.case_count > 0 ? s.verdict_amount / s.case_count : null;
    return { song: s, avg };
  }, [freq, agg]);

  const kwl = kw.trim().toLowerCase();
  const visible = kwl ? songs.filter((s) => [s.song_name, s.artist ?? ""].join(" ").toLowerCase().includes(kwl)) : songs;

  return (
    <>
      <PageHeader
        title="歌曲维度"
        breadcrumb={<>分析 / 歌曲维度 · 歌曲×案件交叉聚合，定位高风险曲目与可复用判例</>}
        actions={
          <button className="btn btn-sm btn-primary" onClick={() => navigate("/ai")}>
            AI 分析风险歌曲
          </button>
        }
      />

      {/* KPI 4 卡 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 16 }}>
        <StatCard
          label="平均单曲判赔"
          value={<span style={{ color: "var(--danger)", fontSize: 25 }}>{agg ? fmtMoney(agg.avg_per_song) : "—"}</span>}
          delta={`按 ${agg ? fmtNum(agg.total_song_slots) : "—"} 个涉案歌曲槽位`}
          hint={`口径 v1.0：判赔案件支付金额合计 ÷ 涉诉歌曲数合计（${d?.metric?.title ?? "口诀 ¥870/首基线"}）`}
        />
        <StatCard
          label="涉诉歌曲槽位"
          value={<span style={{ fontSize: 25 }}>{agg ? fmtNum(agg.total_song_slots) : "—"}</span>}
          delta={`判赔案件 ${agg ? fmtNum(agg.case_count) : "—"} 件（按歌曲口径）`}
          hint="song_count 字段合计（同一案多曲累加）"
        />
        <StatCard
          label="高频歌曲（≥5 案）"
          value={<span style={{ fontSize: 25 }}>{fmtNum(freq.length)}</span>}
          delta={`合计贡献 ${fmtNum(freqCases)} / ${fmtNum(totalCases)} 案 · 集中度 ${totalCases ? ((freqCases / totalCases) * 100).toFixed(1) : "—"}%`}
          hint="同曲被重复起诉数量（批量诉讼集中度信号）"
        />
        <StatCard
          label="TOP 涉诉曲目"
          value={
            <span style={{ fontSize: 19, fontWeight: 600 }}>
              {top ? top.song_name : "—"}
            </span>
          }
          delta={top ? `${fmtNum(top.case_count)} 案 · 均赔 ${fmtMoney((top.verdict_amount ?? 0) / Math.max(top.case_count, 1))}` : "暂无伴奏数据"}
          hint="按涉案件数降序第一"
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 14, alignItems: "flex-start" }}>
        {/* TOP 歌曲列表 */}
        <div className="card">
          <div className="card-head" style={{ display: "flex", alignItems: "center", padding: "12px 16px", gap: 10, borderBottom: "1px solid var(--border)" }}>
            <div className="card-title" style={{ margin: 0 }}>
              TOP 涉诉歌曲
              <span className="help" style={{ marginLeft: 6 }} title="按涉案件数降序 · 点击行在检索页打开关联案件">ⓘ</span>
            </div>
            <input
              className="inp"
              style={{ marginLeft: "auto", width: 190, height: 28, fontSize: 12 }}
              placeholder="筛选歌曲 / 歌手…"
              value={kw}
              onChange={(e) => setKw(e.target.value)}
            />
          </div>
          {isLoading ? (
            <div style={{ padding: 40 }}>
              <Spinner label="聚合歌曲×案件…" />
            </div>
          ) : isError ? (
            <PageError message="歌曲维度加载失败" onRetry={refetch} />
          ) : visible.length === 0 ? (
            <EmptyState title="暂无歌曲数据" desc="同步 DuplexLink 歌曲表与 song_case 关联后自动聚合" />
          ) : (
            <div className="tbl-wrap" style={{ border: "none", borderRadius: 0, maxHeight: 520, overflowY: "auto" }}>
              <table className="tbl" style={{ width: "100%" }}>
                <thead>
                  <tr>
                    <th>歌曲</th>
                    <th>演唱 / 艺人</th>
                    <th style={{ textAlign: "right" }}>涉案</th>
                    <th style={{ textAlign: "right" }}>单曲判赔</th>
                    <th>集中度</th>
                    <th>风险</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((s) => {
                    const risk = riskOf(s.case_count);
                    const avg = s.verdict_amount != null && s.case_count > 0 ? s.verdict_amount / s.case_count : null;
                    return (
                      <tr key={s.song_id} onClick={() => navigate(`/search?q=${encodeURIComponent(s.song_name)}`)} style={{ cursor: "pointer" }}>
                        <td>
                          <span style={{ fontStyle: "italic", marginRight: 8, opacity: 0.6 }}>♪</span>
                          <b style={{ fontSize: 13 }}>{s.song_name}</b>
                        </td>
                        <td style={{ fontSize: 12 }}>{s.artist || "—"}</td>
                        <td style={{ ...NUM, fontWeight: 600 }}>{fmtNum(s.case_count)} 案</td>
                        <td style={NUM}>{avg != null ? fmtMoney(avg) : "—"}</td>
                        <td>
                          <Badge tone={risk.tone} dot={false} outline>
                            {risk.label}
                          </Badge>
                        </td>
                        <td>
                          <Badge tone={risk.tone}>{risk.label === "高" ? "⚠ 高" : risk.label === "中" ? "▲ 中" : "✓ 低"}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="card-hint" style={{ padding: "10px 16px" }}>
            TOP {fmtNum(songs.length)} 展示 · 其余曲目涉诉 ≤2 案 · 点击行 → 检索页按歌名打开关联案件
          </div>
        </div>

        {/* 右侧：风险提示 + 类推判例 */}
        <div style={{ minWidth: 0 }}>
          <div className="card card-pad">
            <div className="card-title">风险提示（规则引擎）</div>
            {warn ? (
              <div className="alert amber" style={{ marginTop: 4 }}>
                <span>⚠</span>
                <span className="grow">
                  <b>高集中度批量风险：</b>「{warn.song.song_name}」涉诉 {fmtNum(warn.song.case_count)} 件，单曲判赔均值{" "}
                  {warn.avg != null ? fmtMoney(warn.avg) : "—"}
                  {agg && warn.avg != null ? `（全库 ${fmtMoney(agg.avg_per_song)}）` : ""}，建议纳入批量应对预案。
                </span>
              </div>
            ) : (
              <EmptyState title="暂无高频风险曲目" desc="涉诉 ≥5 案时自动提示" />
            )}
            <div className="alert blue" style={{ marginTop: 10 }}>
              <span>💡</span>
              <span className="grow">
                <b>类推判例：</b>同曲多案时判赔比例存在地域差异 —— 管辖策略可参考年均判赔走势及对手方画像。
              </span>
              <button className="btn btn-sm" style={{ height: 24, fontSize: 11 }} onClick={() => navigate("/parties")}>
                查看 →
              </button>
            </div>
          </div>
          <div className="card card-pad" style={{ marginTop: 14 }}>
            <div className="card-title">
              单曲判赔口径
              <span className="help" style={{ marginLeft: 6 }} title={d?.metric?.definition ?? undefined}>ⓘ</span>
            </div>
            <div style={{ fontSize: 12, lineHeight: 1.7, color: "var(--muted)" }}>
              {d?.metric?.definition ?? "判赔案件支付金额合计 ÷ 涉诉歌曲数合计（按案平均），与指标口径中心一致。"}
              <div className="sub" style={{ marginTop: 4 }}>版本 {d?.metric?.version ?? "v1.0"} · 数据截至最近同步</div>
            </div>
          </div>
        </div>
      </div>

      <footer className="footnote" style={{ textAlign: "right", marginTop: 8 }}>
        歌曲维度由 DuplexLink 歌曲表 × song_case 关联聚合派生 · 单曲判赔口径 v1.0（口诀 ¥870/首）· 风险规则 = 涉案频次分档
      </footer>
    </>
  );
}