/* 08-指标口径（docs/02 §8.4 + plan t08-10）。
   8 项指标口径 v1.0 卡片（key/title/version/definition/footnote/enabled）
   + 版本指针（clean_rule 规则启停快照 / metric 口径版本映射）。
   数据源：useDicts（与 dicts 页同源：后端 versions 指针为保存重跑依据）。 */
import { useDicts } from "@/hooks";
import { Badge, PageError, PageHeader, Spinner } from "@/components/common";
import { BookOpenCheck, GitBranch, Scale } from "lucide-react";

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** 版本指针对象 → 展示摘要：clean_rule {"version","enabled_rules"} → vN + n 条启用；其余回 JSON。 */
function fmtVersions(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    const ver = o.version ? String(o.version) : null;
    const enabled = Array.isArray(o.enabled_rules) ? (o.enabled_rules as unknown[]).length : null;
    if (ver && enabled !== null) return `${ver} · 启用 ${enabled} 条`;
    if (ver) return ver;
  }
  return JSON.stringify(v);
}

export default function MetricsPage() {
  const dicts = useDicts();

  if (dicts.isLoading) return <Spinner label="指标口径加载中…" />;
  if (dicts.isError) return <PageError message={errMsg(dicts.error)} onRetry={() => void dicts.refetch()} />;

  const metrics = dicts.data?.metric_defs ?? [];
  const versions = dicts.data?.versions ?? {};

  return (
    <div>
      <PageHeader
        title="指标口径"
        breadcrumb={<>8 项指标口径 v1.0 固化管理 · 版本指针为保存重跑依据（P0 只读页，编辑走字典配置）</>}
        actions={<Badge outline>口径中心</Badge>}
      />

      {/* 版本指针 */}
      <div className="card card-pad">
        <div className="card-title">
          <GitBranch size={14} /> 版本指针 <span className="sub">同步启停与口径变更自动快照（Setting 存储）</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10, marginTop: 8 }}>
          <div className="card" style={{ padding: 10 }}>
            <div className="f-label">clean_rule（规则启停快照）</div>
            <div style={{ fontWeight: 600, fontSize: 14, marginTop: 4 }}>{fmtVersions(versions.clean_rule)}</div>
            <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>UI 保存重跑依据：启用规则链 = enabled_rules 快照</div>
          </div>
          <div className="card" style={{ padding: 10 }}>
            <div className="f-label">metric（指标口径版本映射）</div>
            <div style={{ fontWeight: 600, fontSize: 14, marginTop: 4 }}>{fmtVersions(versions.metric)}</div>
            <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>current_metric_versions：各指标当前口径 version</div>
          </div>
        </div>
      </div>

      {/* 8 项指标定义卡片 */}
      <div className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <Scale size={14} /> 指标定义（v1.0 固化）
          <span className="sub">统计口径全站唯一来源 · 详情页/总览图表共用</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 10, marginTop: 8 }}>
          {metrics.map((m) => (
            <div key={m.key} className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                <Badge tone={m.enabled ? "blue" : "gray"} dot={false}>{m.key}</Badge>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{m.title}</span>
                <span className="sub" style={{ marginLeft: "auto" }}>{m.version ?? "—"}</span>
              </div>
              <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--text-2)" }}>{m.definition ?? "—"}</div>
              {m.footnote && (
                <div className="muted" style={{ fontSize: 11, borderTop: "1px dashed var(--border)", paddingTop: 6 }}>
                  {m.footnote}
                </div>
              )}
            </div>
          ))}
        </div>
        {metrics.length === 0 && (
          <div className="muted" style={{ padding: 20, textAlign: "center" }}>暂无指标定义（同步管道初始化）</div>
        )}
      </div>

      {/* 口径说明 */}
      <div className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <BookOpenCheck size={14} /> 口径说明
        </div>
        <ul style={{ fontSize: 12.5, lineHeight: 1.9, color: "var(--text-2)", paddingLeft: 18, margin: 0 }}>
          <li>指标口径 v1.0 为设计阶段 G0~G13 审计固化结论，修改需在「字典配置 → 规则预演」验证后重跑清洗管道。</li>
          <li>clean_rule 版本指针每次规则启停自动更新（审计 op_type=api）；metric 指针仅管道重算时刷新。</li>
          <li>所有图表/表格数字均带口径脚注（导出 CSV 可带 footnote 列），与口径中心保持一致。</li>
        </ul>
      </div>
    </div>
  );
}