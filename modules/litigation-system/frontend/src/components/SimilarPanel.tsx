/* F4.2 同质案类推面板（docs/02 §6.2）：案件详情「相似案」Tab 与检索页「找相似」共用。
   POST /similar → SimilarData：目标摘要 + 风险提示卡（结案原因分布 / 判赔区间 P25~P75 / 笔记要点 Top3）
   + 加权 Top10 表（相似度进度条，行展开笔记）+ 权重脚注 + 导出提示卡（MD）。 */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, X } from "lucide-react";
import { Badge, EmptyState, EnumBadge, PageError, Spinner } from "@/components/common";
import { useMetadata, useSimilar } from "@/hooks";
import { downloadBlob, fmtMoney, fmtNum, fmtText } from "@/lib/format";
import { enumTone, resolveTone, type Tone } from "@/lib/colors";

/* F4.2 权重标签（后端 POST /similar 透出的 weights 键） */
const WEIGHT_LABEL: Record<string, string> = {
  cause: "案由",
  biz_line: "业务线",
  resolve: "结案原因",
  amount: "标的",
  defendant: "对手方",
  notes: "笔记",
};

/* 相似度色带：>=70 高 / >=40 中 / 其余 低 */
function simTone(v: number): Tone {
  if (v >= 70) return "green";
  if (v >= 40) return "amber";
  return "gray";
}

const TONE_HEX: Record<Tone, string> = {
  green: "#16a34a",
  red: "#dc2626",
  amber: "#d97706",
  blue: "#2563eb",
  gray: "#94a3b8",
};

function stamp(): string {
  return new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
}

export default function SimilarPanel({ caseId, onClose }: { caseId: string | undefined; onClose?: () => void }) {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useSimilar(caseId);
  const { data: meta } = useMetadata();
  const [openId, setOpenId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  /* 枚举色映射（cause 色点 / biz_line 徽章，与检索页同源 meta.enums） */
  const causeColor = useMemo(
    () => new Map((meta?.enums.cause ?? []).map((o) => [o.enum_key, o.color ?? null])),
    [meta],
  );
  const bizColor = useMemo(
    () => new Map((meta?.enums.biz_line ?? []).map((o) => [o.enum_key, o.color ?? null])),
    [meta],
  );

  if (isLoading) return <Spinner label="同质案类推分析中…" />;
  if (isError || !data) return <PageError message="同质案类推分析失败" onRetry={() => void refetch()} />;

  const target = data.target ?? {};
  const targetNo = fmtText(target.case_no as string | null | undefined) || String(target.record_id ?? "");
  const items = data.items ?? [];
  const risk = data.risk;
  const weights = Object.entries(data.weights ?? {})
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${WEIGHT_LABEL[k] ?? k} ${v}`);
  const maxCnt = Math.max(1, ...(risk?.resolve_dist ?? []).map((d) => d.count ?? 0));

  /* 导出提示卡：目标摘要 + 风险提示 + Top10，Markdown 文本 */
  const doExport = () => {
    if (!data) return;
    setExporting(true);
    try {
      const lines: string[] = [
        `# 同质案类推 · ${targetNo}`,
        "",
        `生成时间：${new Date().toLocaleString("zh-CN")}`,
        `目标案件：${targetNo}｜案由 ${fmtText(target.cause)}｜${fmtText(target.resolve)}｜${fmtText(target.biz_line)}`,
        "",
        "## 风险提示",
      ];
      if (risk) {
        const rd = (risk.resolve_dist ?? []).map((d) => `${fmtText(d.resolve)} ${d.count} 件`).join("；") || "—";
        lines.push(
          `- 结案原因分布：${rd}`,
          `- 判赔区间（n=${fmtNum(risk.pay_range?.n ?? 0)}）：P25 ${fmtMoney(risk.pay_range?.p25)} · P50 ${fmtMoney(risk.pay_range?.p50)} · P75 ${fmtMoney(risk.pay_range?.p75)}`,
        );
        if ((risk.note_points ?? []).length) lines.push(`- 笔记要点：${risk.note_points.slice(0, 3).join("；")}`);
      }
      lines.push("", "## Top10 相似案件", "| 相似度 | 案号 | 案由 | 业务线 | 结案原因 | 标的 | 支付 | 笔记 |", "| --- | --- | --- | --- | --- | --- | --- | --- |");
      for (const it of items) {
        lines.push(
          `| ${it.similarity}% | ${it.case_no ?? "—"} | ${fmtText(it.cause)} | ${fmtText(it.biz_line)} | ${fmtText(it.resolve)} | ${fmtMoney(it.amount)} | ${fmtMoney(it.pay_amount)} | ${it.notes ?? "—"} |`,
        );
      }
      if (weights.length) lines.push("", `> 权重：${weights.join(" / ")}`);
      downloadBlob(new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" }), `similar_${targetNo}_${stamp()}.md`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="card card-pad" style={{ marginBottom: 14 }}>
      {/* 头部：目标摘要 + 操作 */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div className="card-title" style={{ margin: 0 }}>
            🔍 同质案类推
            <span className="sub">F4.2 · 加权 Top{Math.max(items.length, 1)}</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--muted-2)", marginTop: 4 }}>
            <b style={{ color: "var(--text)" }}>{targetNo}</b>
            {target.cause ? ` · ${fmtText(target.cause)}` : ""}
            {target.resolve ? ` · ${fmtText(target.resolve)}` : ""}
            {target.biz_line ? ` · ${fmtText(target.biz_line)}` : ""}
          </div>
        </div>
        <button type="button" className="btn btn-sm" disabled={exporting} onClick={() => void doExport()}>
          <Download size={13} /> 导出提示卡
        </button>
        {onClose && (
          <button type="button" className="btn btn-sm" onClick={onClose} title="关闭相似案面板">
            <X size={13} /> 关闭
          </button>
        )}
      </div>

      {/* 风险提示卡（结案原因分布 / 判赔区间 / 笔记要点） */}
      {risk && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 10, marginTop: 12 }}>
          <div style={{ background: "var(--surface-2)", borderRadius: 8, padding: "10px 12px" }}>
            <div className="footnote" style={{ marginBottom: 6, fontSize: 11, fontWeight: 600 }}>结案原因分布</div>
            {(risk.resolve_dist ?? []).length === 0 ? (
              <span className="footnote">无已结案相似案件</span>
            ) : (
              <div style={{ display: "grid", gap: 5 }}>
                {risk.resolve_dist.map((d) => (
                  <div key={d.resolve} style={{ display: "grid", gridTemplateColumns: "86px 1fr 36px", gap: 6, alignItems: "center" }}>
                    <span style={{ fontSize: 11.5, color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {fmtText(d.resolve)}
                    </span>
                    <span className="track">
                      <span className="fill" style={{ width: `${(d.count / maxCnt) * 100}%`, background: TONE_HEX[resolveTone(d.resolve)] }} />
                    </span>
                    <span style={{ fontSize: 11, textAlign: "right", color: "var(--muted-2)" }}>{fmtNum(d.count)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ background: "var(--surface-2)", borderRadius: 8, padding: "10px 12px" }}>
            <div className="footnote" style={{ marginBottom: 6, fontSize: 11, fontWeight: 600 }}>判赔区间（金额型相似案）</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
              {(["p25", "p50", "p75"] as const).map((k, i) => (
                <div key={k}>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>P{25 + i * 25}</div>
                  <div style={{ fontSize: 13.5, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{fmtMoney(risk.pay_range?.[k])}</div>
                </div>
              ))}
            </div>
            <div className="footnote" style={{ marginTop: 6 }}>样本 {fmtNum(risk.pay_range?.n ?? 0)} 件（已结案且有金额）</div>
          </div>

          <div style={{ background: "var(--surface-2)", borderRadius: 8, padding: "10px 12px" }}>
            <div className="footnote" style={{ marginBottom: 6, fontSize: 11, fontWeight: 600 }}>笔记要点 Top3</div>
            {(risk.note_points ?? []).length === 0 ? (
              <span className="footnote">相似案件暂无共享笔记要点</span>
            ) : (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {risk.note_points.slice(0, 3).map((p, i) => (
                  <Badge key={i} tone="blue" dot={false}>{p}</Badge>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Top10 相似案件表 */}
      <div className="card-title" style={{ margin: "14px 0 8px" }}>
        Top{Math.max(items.length, 1)} 相似案件
        <span className="sub">相似度 0~100（F4.2 加权）· 点击行展开笔记</span>
      </div>
      {items.length === 0 ? (
        <EmptyState icon="🗂" title="无相似案件" desc="当前案件未匹配到可类推的同质案件" />
      ) : (
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 110 }}>相似度</th>
                <th>案号</th>
                <th>案由</th>
                <th>业务线</th>
                <th>结案原因</th>
                <th className="num">标的</th>
                <th className="num">支付</th>
                <th>笔记</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <RenderRow
                  key={it.record_id}
                  it={it}
                  open={openId === it.record_id}
                  onToggle={() => setOpenId(openId === it.record_id ? null : it.record_id)}
                  onOpenCase={() => navigate(`/cases/${String(it.record_id)}`)}
                  causeDot={causeColor.get(String(it.cause)) ?? null}
                  bizTone={enumTone(bizColor.get(String(it.biz_line)) ?? null)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 权重脚注 */}
      {weights.length > 0 && (
        <div className="footnote" style={{ marginTop: 10 }}>
          ⚖️ 相似度权重：{weights.join(" / ")} · 数据源于案件主表（F4.2）
        </div>
      )}
    </div>
  );
}

/* ---- 相似案件行（含展开笔记区） ---- */
function RenderRow({
  it,
  open,
  onToggle,
  onOpenCase,
  causeDot,
  bizTone,
}: {
  it: { record_id: string; case_no: string | null; cause: string | null; resolve: string | null; biz_line: string | null; amount: number | null; pay_amount: number | null; similarity: number; notes: string | null };
  open: boolean;
  onToggle: () => void;
  onOpenCase: () => void;
  causeDot: string | null;
  bizTone: Tone;
}) {
  const sim = Math.min(100, Math.max(0, it.similarity));
  const noms = it.notes?.trim();
  return (
    <>
      <tr onClick={onToggle} title={it.notes?.trim() ? "点击展开/收起笔记" : "点击查看详情"}>
        <td>
          <span className="sup" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="track" style={{ flex: 1, maxWidth: 64 }}>
              <span className="fill" style={{ width: `${sim}%`, background: TONE_HEX[simTone(sim)] }} />
            </span>
            <span className="val" style={{ color: TONE_HEX[simTone(sim)], fontWeight: 600 }}>{fmtNum(sim)}%</span>
          </span>
        </td>
        <td>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onOpenCase();
            }}
            style={{ border: 0, background: "transparent", padding: 0, cursor: "pointer", color: "var(--primary)", fontSize: 12.5, fontWeight: 500 }}
            title="查看案件详情"
          >
            {it.case_no ?? "—"}
          </button>
        </td>
        <td>
          {it.cause ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <i style={{ width: 6, height: 6, borderRadius: "50%", background: TONE_HEX[enumTone(causeDot)] ?? causeDot ?? "#94a3b8", flexShrink: 0 }} />
              {fmtText(it.cause)}
            </span>
          ) : (
            "—"
          )}
        </td>
        <td>{it.biz_line ? <EnumBadge tone={bizTone}>{it.biz_line}</EnumBadge> : "—"}</td>
        <td>
          <Badge tone={resolveTone(it.resolve)}>{fmtText(it.resolve) || "—"}</Badge>
        </td>
        <td className="num">{fmtMoney(it.amount)}</td>
        <td className="num">{fmtMoney(it.pay_amount)}</td>
        <td style={{ maxWidth: 180 }}>
          <span style={{ fontSize: 11.5, color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>
            {noms ?? "—"}
          </span>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={8} style={{ background: "var(--surface-2)", padding: "8px 12px", fontSize: 12.5, color: "var(--muted)" }}>
            <b style={{ color: "var(--text)" }}>办案笔记：</b>
            {noms ?? "该案未记录笔记"}
          </td>
        </tr>
      )}
    </>
  );
}