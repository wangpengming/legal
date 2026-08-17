/* 报告存档页（Phase 3 Mode B）：/reports 列表 + /reports/:id 详情。
   T1~T7 模板由后端 /ai/report-templates 下发；生成走 POST /reports/generate 落库；
   详情渲染 Markdown 正文 + 三源脚注（本地库/案例库/法规），支持导出 MD/HTML 与打印。 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Download, FileText, Plus, Printer, Trash2 } from "lucide-react";
import { Drawer } from "@/components/Drawer";
import { Badge, EmptyState, EnumBadge, PageError, PageHeader, Spinner } from "@/components/common";
import { useAiTemplates, useReportDetail, useReportMutation, useReports } from "@/hooks";
import { downloadBlob, fmtDateTime, fmtNum, fmtText } from "@/lib/format";
import type { AiSources } from "@/lib/api";
import { Markdown } from "@/components/Markdown";

function toast(msg: string, isErr = false): void {
  window.dispatchEvent(new CustomEvent("lt:toast", { detail: isErr ? `⚠️ ${msg}` : msg }));
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function stamp(): string {
  return new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
}

/** 参数摘要（params → "year=2024 · idol=…"） */
function paramSummary(p: Record<string, string> | undefined): string {
  const ks = Object.keys(p ?? {});
  return ks.length ? ks.map((k) => `${k}=${p![k]}`).join(" · ") : "无参数";
}

/* ---------------------------------------------------------------- 导出小工具 */

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function inlineMd(s: string): string {
  let t = escapeHtml(s);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return t;
}

/** 极简 Markdown → 自包含 HTML（标题/表格/列表/引用/代码块/水平线/段落；供导出与打印） */
function mdToHtml(body: string): string {
  const lines = body.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    /* 代码块 */
    if (line.trim().startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        buf.push(lines[i]);
        i++;
      }
      i++;
      out.push(`<pre><code>${escapeHtml(buf.join("\n"))}</code></pre>`);
      continue;
    }
    /* 表格块（首行表头、次行分隔、余为数据行） */
    if (/^\s*\|/.test(line)) {
      const rows: string[][] = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        rows.push(lines[i].split("|").slice(1, -1).map((c) => c.trim()));
        i++;
      }
      const header = rows[0] ?? [];
      const sepIdx = rows[1] && rows[1].every((c) => /^:?-{1,}:?$/.test(c.replace(/\s/g, ""))) ? 1 : -1;
      const bodyRows = sepIdx >= 0 ? rows.slice(2) : rows.slice(1);
      out.push(
        "<table><thead><tr>" +
          header.map((c) => `<th>${inlineMd(c)}</th>`).join("") +
          "</tr></thead><tbody>" +
          bodyRows
            .map((r) => "<tr>" + header.map((_, idx) => `<td>${inlineMd(r[idx] ?? "")}</td>`).join("") + "</tr>")
            .join("") +
          "</tbody></table>",
      );
      continue;
    }
    /* 标题 */
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      out.push(`<h${h[1].length}>${inlineMd(h[2])}</h${h[1].length}>`);
      i++;
      continue;
    }
    /* 引用 */
    if (line.trim().startsWith(">")) {
      out.push(`<blockquote>${inlineMd(line.trim().replace(/^>\s?/, ""))}</blockquote>`);
      i++;
      continue;
    }
    /* 水平线 */
    if (/^(\s*[-*_]\s*){3,}$/.test(line)) {
      out.push("<hr />");
      i++;
      continue;
    }
    /* 无序列表 */
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(`<li>${inlineMd(lines[i].replace(/^\s*[-*]\s+/, ""))}</li>`);
        i++;
      }
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }
    /* 有序列表 */
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(`<li>${inlineMd(lines[i].replace(/^\s*\d+\.\s+/, ""))}</li>`);
        i++;
      }
      out.push(`<ol>${items.join("")}</ol>`);
      continue;
    }
    if (line.trim() === "") {
      out.push("");
      i++;
      continue;
    }
    out.push(`<p>${inlineMd(line)}</p>`);
    i++;
  }
  while (out.length && out[out.length - 1] === "") out.pop();
  return out.join("\n");
}

/** 自包含打印样式（A4 阅读排版） */
function printSheet(title: string, bodyHtml: string): string {
  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<style>
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; max-width: 840px; margin: 0 auto; padding: 32px 24px; color: #1f2328; line-height: 1.7; }
  h1 { font-size: 22px; border-bottom: 2px solid #d0d7de; padding-bottom: 8px; }
  h2 { font-size: 18px; margin-top: 24px; }
  h3, h4 { font-size: 15px; margin-top: 18px; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
  th, td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }
  th { background: #f6f8fa; font-weight: 600; }
  blockquote { border-left: 3px solid #d0d7de; margin: 10px 0; padding: 4px 12px; color: #57606a; background: #f6f8fa; }
  pre { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 10px; overflow-x: auto; font-size: 12.5px; }
  code { background: #f6f8fa; border-radius: 4px; padding: 1px 5px; font-size: 12.5px; }
  pre code { background: transparent; padding: 0; }
  hr { border: 0; border-top: 1px solid #d0d7de; margin: 20px 0; }
  ul, ol { padding-left: 22px; }
  .meta { color: #57606a; font-size: 12.5px; margin-bottom: 18px; }
</style>
</head>
<body>
<h1>${escapeHtml(title)}</h1>
<div class="meta">生成时间 ${new Date().toLocaleString("zh-CN")} · 诉讼平台报告存档导出</div>
${bodyHtml}
</body>
</html>`;
}

/* ---------------------------------------------------------------- 三源脚注（详情页复用 AI 对话口径） */

function SourcesFoot({ sources }: { sources?: AiSources }) {
  const [opened, setOpened] = useState<Record<string, boolean>>({});
  const triple: [string, "local" | "cases" | "law", string][] = [
    ["📂 本地库", "local", "FTS5 案件检索 + 歌名关联兜底"],
    ["⚖️ 案例库", "cases", "external_cases 包含匹配"],
    ["📜 法规", "law", "法规常量库关键词命中"],
  ];
  const allMissing = !sources || triple.every(([, key]) => !sources[key] || sources[key].hits === 0);
  if (allMissing) {
    return (
      <div className="alert amber" style={{ fontSize: 12.5 }}>
        <span>本报告来源脚注为空：未检索到本地案件 / 外部案例 / 法规命中（结论基于全量统计口径，请人工核查补充来源）。</span>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
      {triple.map(([label, key, note]) => {
        const src = sources?.[key];
        const missing = !src || src.hits === 0;
        const openedKey = !!opened[key];
        return (
          <div key={key} style={{ fontSize: 12.5 }}>
            <button
              type="button"
              onClick={() => setOpened((prev) => ({ ...prev, [key]: !openedKey }))}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                border: 0,
                background: "transparent",
                cursor: missing ? "default" : "pointer",
                padding: "3px 0",
                color: "var(--text)",
                fontSize: 12.5,
                textAlign: "left",
                flexWrap: "wrap",
              }}
              aria-expanded={openedKey}
            >
              <span>{label}</span>
              {missing ? (
                <span className="footnote" style={{ color: "var(--muted-2)" }}>缺源：网上判决（请人工核查）</span>
              ) : (
                <>
                  <Badge tone="blue" dot={false}>{src.hits} 条</Badge>
                  <span className="footnote">{note}</span>
                  <span className="footnote" style={{ marginLeft: "auto" }}>{openedKey ? "收起 ▴" : "展开 ▾"}</span>
                </>
              )}
            </button>
            {!missing && openedKey && (
              <div className="footnote" style={{ margin: "4px 0 6px 26px" }}>{src?.note}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------------- 主体 */

export default function ReportsPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const reportId = id && /^\d+$/.test(id) ? Number(id) : null;

  /* 列表态（详情态下查询发出但未渲染，成本可忽略） */
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const listQuery = useReports(page, 10, filter || undefined);
  const { data: templates } = useAiTemplates();

  /* 详情态 */
  const detailQuery = useReportDetail(reportId ?? undefined);

  /* 生成向导 */
  const [wizardOpen, setWizardOpen] = useState(false);
  const [tmplKey, setTmplKey] = useState<string | null>(null);
  const [paramVals, setParamVals] = useState<Record<string, string>>({});

  const { generate, remove } = useReportMutation();

  const doGenerate = async () => {
    if (!tmplKey) return;
    try {
      const r = await generate.mutateAsync({ template_key: tmplKey, params: paramVals, created_by: "local" });
      const rid = r.data?.id;
      toast(`已生成并落库报告 #${rid}`);
      setWizardOpen(false);
      if (rid != null) navigate(`/reports/${rid}`);
    } catch (e) {
      toast(errMsg(e), true);
    }
  };

  const doRemove = async (rid: number) => {
    if (!window.confirm(`确定删除报告 #${rid}？（删除后不可恢复）`)) return;
    try {
      const r = await remove.mutateAsync(rid);
      toast(`已删除报告 #${r.data?.id ?? rid}`);
      if (reportId === rid) navigate("/reports");
    } catch (e) {
      toast(errMsg(e), true);
    }
  };

  /* ---------------------------------------------------------------- 详情分支 */
  if (reportId != null) {
    if (detailQuery.isLoading) return <Spinner label="报告加载中…" />;
    if (detailQuery.isError || !detailQuery.data) {
      return <PageError message="报告加载失败" onRetry={() => void detailQuery.refetch()} />;
    }
    const detail = detailQuery.data;
    const exportMd = () => {
      if (!detail.body) return;
      downloadBlob(new Blob([detail.body], { type: "text/markdown;charset=utf-8" }), `report_${reportId}_${stamp()}.md`);
      toast("已导出 Markdown");
    };
    const exportHtml = () => {
      if (!detail.body) return;
      const html = printSheet(detail.title, mdToHtml(detail.body));
      downloadBlob(new Blob([html], { type: "text/html;charset=utf-8" }), `report_${reportId}_${stamp()}.html`);
      toast("已导出 HTML");
    };
    const doPrint = () => {
      if (!detail.body) return;
      const url = URL.createObjectURL(new Blob([printSheet(detail.title, mdToHtml(detail.body))], { type: "text/html;charset=utf-8" }));
      const w = window.open(url, "_blank");
      if (!w) {
        URL.revokeObjectURL(url);
        toast("浏览器拦截了新窗口，请改用「导出 HTML」", true);
        return;
      }
      window.setTimeout(() => {
        w.focus();
        w.print();
      }, 400);
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    };
    return (
      <div>
        <PageHeader
          title={`报告存档 · #${reportId}`}
          breadcrumb={fmtText(detail.title)}
          actions={<>
            <button type="button" className="btn btn-sm" onClick={() => navigate("/reports")}><ArrowLeft size={13} /> 返回列表</button>
            <button type="button" className="btn btn-sm" onClick={exportMd}><Download size={13} /> 导出 MD</button>
            <button type="button" className="btn btn-sm" onClick={exportHtml}>导出 HTML</button>
            <button type="button" className="btn btn-sm" onClick={doPrint}><Printer size={13} /> 打印</button>
            <button type="button" className="btn btn-sm" onClick={() => void doRemove(reportId)}><Trash2 size={13} /> 删除</button>
          </>}
        />
        <div className="card card-pad">
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
            <EnumBadge tone="blue">{detail.template_key}</EnumBadge>
            <span className="muted" style={{ fontSize: 12.5 }}>
              {fmtDateTime(detail.created_at)} · {detail.created_by ?? "系统"} · {paramSummary(detail.params)}
            </span>
          </div>
          <SourcesFoot sources={detail.sources} />
          <div style={{ marginTop: 12 }}>
            <Markdown text={detail.body ?? ""} />
          </div>
        </div>
      </div>
    );
  }

  /* ---------------------------------------------------------------- 列表分支 */
  const total = listQuery.data?.meta?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 10));

  return (
    <div>
      <PageHeader
        title="报告存档"
        breadcrumb="Mode B · T1~T7 统计报告生成与归档（结论均带三源脚注）"
        actions={<>
          <button type="button" className="btn btn-sm btn-primary" onClick={() => setWizardOpen(true)}>
            <Plus size={13} /> 新建报告
          </button>
        </>}
      />

      {/* 模板筛选 chips */}
      <div className="seg" role="tablist" aria-label="模板筛选" style={{ marginBottom: 14 }}>
        <button type="button" role="tab" aria-selected={filter === ""} className={filter === "" ? "seg-item active" : "seg-item"} onClick={() => setFilter("")}>
          全部
        </button>
        {(templates ?? []).map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={filter === t.key} className={filter === t.key ? "seg-item active" : "seg-item"} onClick={() => { setFilter(t.key); setPage(1); }}>
            {t.title}
          </button>
        ))}
      </div>

      {listQuery.isLoading ? (
        <Spinner label="报告列表加载中…" />
      ) : listQuery.isError ? (
        <PageError message="报告列表加载失败" onRetry={() => void listQuery.refetch()} />
      ) : (listQuery.data?.list.length ?? 0) === 0 ? (
        <EmptyState icon={<FileText size={28} />} title="暂无报告" desc="通过「新建报告」选择 T1~T7 模板生成并落库" />
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {(listQuery.data?.list ?? []).map((r) => (
            <div key={r.id} className="card-pad" style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <EnumBadge tone="blue">{r.template_key}</EnumBadge>
              <div style={{ flex: 1, minWidth: 220 }}>
                <div style={{ fontWeight: 600, fontSize: 13.5 }}>{fmtText(r.title)}</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                  {fmtDateTime(r.created_at)} · {r.created_by ?? "系统"} · {paramSummary(r.params)}
                </div>
              </div>
              <button type="button" className="btn btn-sm" onClick={() => navigate(`/reports/${r.id}`)}>查看</button>
              <button type="button" className="btn btn-sm" onClick={() => void doRemove(r.id)}><Trash2 size={13} /> 删除</button>
            </div>
          ))}
        </div>
      )}

      {/* 分页 */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, fontSize: 12.5 }}>
        <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>上一页</button>
        <span className="muted">第 {page} / {totalPages} 页 · 共 {fmtNum(total)} 份报告</span>
        <button type="button" className="btn btn-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>下一页</button>
      </div>

      {/* 生成向导 */}
      <Drawer
        title="生成新报告（Mode B · T1~T7 模板）"
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        foot={<>
          <button type="button" className="btn btn-sm" onClick={() => setWizardOpen(false)}>取消</button>
          <button type="button" className="btn btn-sm btn-primary" disabled={!tmplKey} onClick={() => void doGenerate()}>生成并落库</button>
        </>}
      >
        <div style={{ display: "grid", gap: 8 }}>
          {(templates ?? []).length === 0 && <div className="empty" style={{ padding: "24px 0" }}>模板加载中或后端未配置 report-templates…</div>}
          {(templates ?? []).map((t) => (
            <label
              key={t.key}
              className="card-pad"
              style={{
                display: "flex",
                gap: 10,
                cursor: "pointer",
                borderRadius: 8,
                border: tmplKey === t.key ? "1px solid var(--primary)" : "1px solid var(--border)",
                background: tmplKey === t.key ? "var(--primary-soft)" : "var(--surface-2)",
              }}
            >
              <input
                type="radio"
                name="tmpl"
                checked={tmplKey === t.key}
                onChange={() => {
                  setTmplKey(t.key);
                  setParamVals({});
                }}
              />
              <div style={{ display: "grid", gap: 3, flex: 1 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>
                  {t.title} <span className="raw-ico" title="模板 key">{t.key}</span>
                </span>
                <span className="muted" style={{ fontSize: 12 }}>{t.description}</span>
                <span className="footnote" style={{ fontSize: 11.5 }}>产出：{t.output}</span>
                {tmplKey === t.key && t.params.length > 0 && (
                  <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                    {t.params.map((p) => (
                      <label key={p} className="f-label" style={{ display: "grid", gap: 3 }}>
                        {p}
                        <input
                          value={paramVals[p] ?? ""}
                          onChange={(e) => setParamVals((v) => ({ ...v, [p]: e.target.value }))}
                          placeholder={`${p}（可留空，由后端取全量默认）`}
                          style={{ width: "100%" }}
                        />
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </label>
          ))}
        </div>
      </Drawer>
    </div>
  );
}