/* 09-AI 对话工作台（docs/02 §3.10 + §6.1 + G10 验收）
   Mode A：意图三分类 → 三源交叉检索（local/cases/law）→ Markdown 回答 + 三源脚注折叠区
            （任一源 hits=0 显示缺源灰字，不静默隐藏）+ 追问 chips（intent 规则，最多 3 个）；
   Mode B：报告意图识别 → T1~T7 模板参数抽取 → 后端 render_report 落库，卡片提供报告存档跳转；
   会话：localStorage 持久化（按日期分组历史）+「导出本对话(MD)」；消息 Markdown 渲染（/reports 复用组件）。 */
import { useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDown, Download, FileText, MessageSquare, Plus, RefreshCw, Send, Sparkles } from "lucide-react";
import { EmptyState, PageHeader } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { useAiChat, useAiTemplates } from "@/hooks";
import type { AiChatResult, AiMode, AiSources } from "@/lib/api";
import { downloadBlob, fmtDateTime } from "@/lib/format";

/* ---------- 会话持久化（localStorage） ---------- */
export interface ChatMsg {
  role: "user" | "ai";
  content: string;
  ts: number;
  meta?: Pick<AiChatResult, "intent" | "used_query" | "sources" | "footnote" | "evidence" | "law_hits" | "report_id" | "template_key" | "title" | "mode">;
}
export interface AiSession {
  id: string;
  title: string;
  ts: number;
  msgs: ChatMsg[];
}
const LS_KEY = "lt:ai-sessions-v1";
function loadSessions(): AiSession[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? (JSON.parse(raw) as AiSession[]) : [];
  } catch {
    return [];
  }
}
function saveSessions(s: AiSession[]): void {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(s.slice(0, 50)));
  } catch {
    /* 存储满则静默放弃，不影响对话 */
  }
}
const dayGroup = (ts: number): string => {
  const d = new Date(ts);
  const t = new Date();
  const same = (x: number) =>
    `${new Date(t).toDateString()}===${new Date(x).toDateString()}`;
  if (same(ts) === same(t.getTime())) return "今天";
  const y = new Date(t.getTime() - 86_400_000);
  return same(ts) === same(y.getTime()) ? "昨天" : `${d.getFullYear()}年${d.getMonth() + 1}月`;
};

/* ---------- Mode A 追问 chips（intent 规则，最多 3 个） ---------- */
function chipsFor(intent: string | undefined, q: string): string[] {
  if (intent === "query_doc") return ["看这件案件的关联歌曲", "找同案由系列案", "生成案件全景报告（T1）"];
  if (intent === "report") return ["生成 T2 胜诉率分析报告", "生成 T6 同步健康报告", "生成 T7 口径复核报告"];
  if (/歌|曲/.test(q)) return ["看这首歌的高频被告", "看这首歌的判赔分布", "生成歌曲使用统计（T5）"];
  return ["按年份看近三年趋势", "按业务线拆分统计", "看判赔金额分布"];
}

function toast(msg: string, isErr = false): void {
  window.dispatchEvent(new CustomEvent("lt:toast", { detail: isErr ? `⚠️ ${msg}` : msg }));
}
function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export default function AiPage() {
  const nav = useNavigate();
  const [mode, setMode] = useState<AiMode>("A");
  const [sessions, setSessions] = useState<AiSession[]>(loadSessions);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [openSrc, setOpenSrc] = useState<Record<string, boolean>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const chat = useAiChat();
  const { data: templates } = useAiTemplates();

  const active = sessions.find((s) => s.id === activeId) ?? null;
  const modeB = mode === "B";

  const patchSession = (sid: string, fn: (s: AiSession) => AiSession) => {
    setSessions((prev) => {
      const next = prev.map((s) => (s.id === sid ? fn(s) : s));
      saveSessions(next);
      return next;
    });
  };

  const newSession = () => {
    const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    setSessions((prev) => {
      const next = [{ id, title: "新对话", ts: Date.now(), msgs: [] }, ...prev];
      saveSessions(next);
      return next;
    });
    setActiveId(id);
    setInput("");
  };
  if (!activeId && sessions.length === 0 && !sending) newSession();

  const pushMsg = (sid: string, msg: ChatMsg) => {
    patchSession(sid, (s) => {
      const msgs = [...s.msgs, msg];
      return { ...s, ts: Date.now(), title: s.title === "新对话" && msg.role === "user" ? msg.content.slice(0, 22) : s.title, msgs };
    });
  };

  const doSend = async (question?: string) => {
    const q = (question ?? input).trim();
    if (!q || sending) return;
    if (!activeId) return;
    const modes = modeB ? "B" : "A";
    pushMsg(activeId, { role: "user", content: q, ts: Date.now() });
    setInput("");
    setSending(true);
    try {
      const r = await chat.mutateAsync({ mode: modes as AiMode, question: q, session_id: activeId });
      pushMsg(activeId, {
        role: "ai",
        content: r.answer,
        ts: Date.now(),
        meta: {
          mode: r.mode,
          intent: r.intent,
          used_query: r.used_query,
          sources: r.sources,
          footnote: r.footnote,
          evidence: r.evidence,
          law_hits: r.law_hits,
          report_id: r.report_id,
          template_key: r.template_key,
          title: r.title,
        },
      });
      if (r.mode === "B" && r.report_id != null) {
        toast(`报告已生成：「${r.title}」→ 报告存档`);
      }
    } catch (e) {
      pushMsg(activeId, { role: "ai", content: `> 回答生成失败：${errMsg(e)}\n\n请重试，或换一种问法。`, ts: Date.now() });
    } finally {
      setSending(false);
      window.setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }), 60);
    }
  };

  const exportMd = () => {
    if (!active || active.msgs.length === 0) {
      toast("当前会话无内容可导出", true);
      return;
    }
    const lines: string[] = [`# AI 对话记录（${modeB ? "Mode B" : "Mode A"}）`, "", `> 会话：${active.title} · 导出 ${fmtDateTime(Date.now())}`, ""];
    for (const m of active.msgs) {
      lines.push(m.role === "user" ? `**Q**: ${m.content}` : `**A**:`, "", m.content, "");
      if (m.role === "ai" && m.meta?.footnote) lines.push(`> 来源：${m.meta.footnote}`, "");
    }
    lines.push("> AI 结论仅供内部参考，不构成法律意见。");
    downloadBlob(new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" }), `ai_chat_${Date.now()}.md`);
    toast("已导出本对话（Markdown）");
  };

  const insertFilter = () => {
    try {
      const raw = localStorage.getItem("lt:search-view");
      if (!raw) {
        toast("未找到已保存的检索视图", true);
        return;
      }
      const v = JSON.parse(raw) as { q?: string; filters?: Record<string, unknown> };
      const seg = [`q=${v.q ?? ""}`];
      if (v.filters) {
        for (const [k, val] of Object.entries(v.filters)) {
          if (val != null && val !== "") seg.push(`${k}=${typeof val === "object" ? JSON.stringify(val) : val}`);
        }
      }
      setInput((prev) => (prev ? prev + " " : "") + `（当前筛选：${seg.join(" · ")}）`);
    } catch {
      toast("读取检索视图失败", true);
    }
  };

  const bots: [typeof MessageSquare, string, string][] = modeB
    ? [
        [FileText, "模式 B 报告生成", "输入报告意图（如「生成 T2 胜诉率分析报告」），后端匹配 T1~T7 模板并落库"],
      ]
    : [
        [MessageSquare, "模式 A 三源问答", "意图分类 → local（FTS5 案件）/ cases（外部案例库）/ law（法规库）交叉检索，结论强制带来源"],
      ];

  return (
    <div style={{ display: "grid", gap: 16, height: "calc(100vh - 140px)", minHeight: 520 }}>
      <PageHeader
        title="AI 法律数据助手"
        breadcrumb="Mode A 三源问答 · Mode B T1~T7 报告生成（规则内核 v2，G10 结论强制带来源）"
        actions={
          <>
            <span className="badge badge-plain" style={{ fontWeight: 600 }}>Beta</span>
            <span className="footnote" style={{ alignSelf: "center" }}>会话保存在本地浏览器</span>
          </>
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 14, minHeight: 0, flex: 1 }}>
        {/* ── 左：会话历史 ── */}
        <div className="card" style={{ display: "flex", flexDirection: "column", padding: 0, minHeight: 0 }}>
          <div className="card-pad" style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-primary" style={{ flex: 1 }} onClick={newSession}>
              <Plus size={13} /> 新会话
            </button>
            <button type="button" className="btn" title="导出本对话(MD)" onClick={exportMd} disabled={!active}>
              <Download size={13} />
            </button>
          </div>
          <div style={{ flex: 1, overflow: "auto", borderTop: "1px solid var(--border)", display: "grid", alignContent: "start" }}>
            {sessions.length === 0 && <EmptyState icon="💬" title="暂无会话" desc="点击「新会话」开始提问" />}
            {Object.entries(
              sessions.reduce<Record<string, AiSession[]>>((acc, s) => {
                const g = dayGroup(s.ts);
                (acc[g] ??= []).push(s);
                return acc;
              }, {}),
            ).map(([g, list]) => (
              <div key={g}>
                <div className="footnote" style={{ padding: "8px 14px 4px" }}>{g}</div>
                {list.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setActiveId(s.id)}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      padding: "8px 14px",
                      border: 0,
                      background: s.id === activeId ? "var(--surface-2)" : "transparent",
                      cursor: "pointer",
                      color: "var(--text)",
                      fontSize: 12.5,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {s.title}
                    <span className="footnote" style={{ display: "block", fontSize: 11 }}>{s.msgs.length} 条消息</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* ── 右：对话主区 ── */}
        <div className="card" style={{ display: "flex", flexDirection: "column", padding: 0, minHeight: 0 }}>
          {/* 工具条：模式切换 + 操作 */}
          <div className="card-pad" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", borderBottom: "1px solid var(--border)" }}>
            <div className="seg" role="tablist" aria-label="AI 模式">
              {(["A", "B"] as AiMode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={mode === m ? "seg-item active" : "seg-item"}
                  onClick={() => setMode(m)}
                  role="tab"
                  aria-selected={mode === m}
                >
                  Mode {m}
                </button>
              ))}
            </div>
            <span className="footnote">{bots[0][1]}：{bots[0][2]}</span>
            <span style={{ flex: 1 }} />
            <button type="button" className="btn btn-sm" onClick={insertFilter}>
              <ArrowDown size={12} /> 插入筛选
            </button>
            <button type="button" className="btn btn-sm" onClick={exportMd} disabled={!active}>
              <Download size={12} /> 导出 MD
            </button>
          </div>

          {/* 消息流 */}
          <div ref={scrollRef} style={{ flex: 1, overflow: "auto", display: "grid", gap: 14, alignContent: "start", padding: 16 }}>
            {(!active || active.msgs.length === 0) && (
              <div style={{ display: "grid", gap: 8, justifyItems: "center", padding: "40px 12px" }}>
                <div style={{ fontSize: 26 }}><Sparkles size={26} style={{ color: "var(--primary)" }} /></div>
                <div style={{ fontWeight: 600 }}>{modeB ? "Mode B · 报告生成工作台" : "Mode A · 三源问答工作台"}</div>
                <div className="footnote" style={{ textAlign: "center", maxWidth: 460 }}>
                  {modeB
                    ? "输入报告意图（模板 T1~T7）：「生成 T2 胜诉率分析报告」「对手方 A 公司画像报告」… 产物自动落入 /reports 存档。"
                    : "直接提问，如：「音集协近两年判赔情况如何？」「查(2023)京0105民初8888号」——回答基于本地库/外部案例/法规三源，未命中源会显式缺源提示。"}
                </div>
                {!modeB && (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
                    {["音集协近两年判赔情况如何？", "哪首歌被起诉次数最多？", "胜诉率口径 A 是什么？"].map((c) => (
                      <button key={c} type="button" className="chip" onClick={() => setInput(c)}>{c}</button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {active?.msgs.map((m, mi) =>
              m.role === "user" ? (
                <div key={mi} style={{ display: "flex", justifyContent: "flex-end" }}>
                  <div style={{ maxWidth: "86%", padding: "9px 14px", borderRadius: "12px 12px 2px 12px", background: "var(--primary)", color: "var(--primary-fg)", fontSize: 13.5, lineHeight: 1.6 }}>
                    {m.content}
                  </div>
                </div>
              ) : (
                <AiBubble
                  key={mi}
                  msg={m}
                  openSrc={openSrc}
                  setOpenSrc={setOpenSrc}
                  onChip={(c) => void doSend(c)}
                  onReport={() => m.meta?.report_id != null && nav(`/reports/${m.meta.report_id}`)}
                />
              ),
            )}
            {sending && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted)", fontSize: 13 }}>
                <RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> 正在检索三源并生成回答…
              </div>
            )}
          </div>

          {/* 输入区 */}
          <div style={{ borderTop: "1px solid var(--border)", padding: 12, display: "grid", gap: 8 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void doSend();
                  }
                }}
                rows={2}
                placeholder={modeB ? "输入报告意图，如：生成 T2 胜诉率分析报告（近两年·音集协）…" : "输入问题，Enter 发送 / Shift+Enter 换行…"}
                style={{ flex: 1, border: "1px solid var(--border)", borderRadius: 10, background: "var(--surface)", padding: "8px 12px", outline: "none", color: "var(--text)", fontSize: 13.5, resize: "none" }}
              />
              <button type="button" className="btn btn-primary" style={{ height: 40, padding: "0 16px" }} disabled={sending || !input.trim()} onClick={() => void doSend()}>
                <Send size={14} /> 发送
              </button>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="footnote">AI 结论仅供内部参考，不构成法律意见</span>
              {modeB && (
                <span className="footnote">
                  报告模板：
                  {templates?.slice(0, 4).map((t) => (
                    <button key={t.key} type="button" className="chip" style={{ marginLeft: 6 }} onClick={() => setInput(`生成 ${t.key} ${t.title}`)}>
                      {t.key}·{t.title.slice(0, 6)}
                    </button>
                  ))}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------- AI 消息气泡：Markdown + 三源脚注 + chips ---------- */
function AiBubble({
  msg,
  openSrc,
  setOpenSrc,
  onChip,
  onReport,
}: {
  msg: ChatMsg;
  openSrc: Record<string, boolean>;
  setOpenSrc: (f: (prev: Record<string, boolean>) => Record<string, boolean>) => void;
  onChip: (c: string) => void;
  onReport: () => void;
}) {
  const meta = msg.meta;
  const sources: AiSources | undefined = meta?.sources;
  const chips = useMemo(() => chipsFor(meta?.intent, meta?.used_query ?? ""), [meta?.intent, meta?.used_query]);
  const triple: [string, "local" | "cases" | "law", string][] = [
    ["📂 本地库", "local", "FTS5 案件检索 + 歌名关联兜底"],
    ["⚖️ 案例库", "cases", "external_cases 包含匹配"],
    ["📜 法规", "law", "法规常量库关键词命中"],
  ];

  return (
    <div style={{ display: "flex", justifyContent: "flex-start" }}>
      <div style={{ maxWidth: "92%", display: "grid", gap: 8 }}>
        <div style={{ padding: "10px 14px", borderRadius: "12px 12px 12px 2px", background: "var(--surface-2)", border: "1px solid var(--border)" }}>
          <Markdown text={msg.content} />

          {meta?.used_query && meta.used_query !== msg.content && (
            <div className="footnote" style={{ marginTop: 8 }}>
              整句未命中，已自动聚焦检索词：<code style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, padding: "0 5px" }}>{meta.used_query}</code>
            </div>
          )}

          {/* 三源脚注折叠区（G10：任一源 0 命中 → 缺源灰字，不静默隐藏） */}
          {sources && (
            <div style={{ marginTop: 10, borderTop: "1px dashed var(--border)", paddingTop: 8, display: "grid", gap: 6 }}>
              {triple.map(([label, key, note]) => {
                const src = sources[key];
                const missing = !src || src.hits === 0;
                const openKey = `${msg.ts}:${key}`;
                const opened = !!openSrc[openKey];
                return (
                  <div key={key} style={{ fontSize: 12.5 }}>
                    <button
                      type="button"
                      onClick={() => setOpenSrc((prev) => ({ ...prev, [openKey]: !opened }))}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        width: "100%",
                        border: 0,
                        background: "transparent",
                        cursor: "pointer",
                        padding: "3px 0",
                        color: "var(--text)",
                        fontSize: 12.5,
                        textAlign: "left",
                        flexWrap: "wrap",
                      }}
                      aria-expanded={opened}
                    >
                      <span>{label}</span>
                      {missing ? (
                        <span className="footnote" style={{ color: "var(--muted-2)" }}>缺源：网上判决（请人工核查）</span>
                      ) : (
                        <>
                          <BadgeTone tone="blue">{src.hits} 条</BadgeTone>
                          <span className="footnote">{note}</span>
                          <span className="footnote" style={{ marginLeft: "auto" }}>{opened ? "收起 ▴" : "展开 ▾"}</span>
                        </>
                      )}
                    </button>
                    {!missing && opened && (
                      <div style={{ margin: "4px 0 6px 26px", display: "grid", gap: 4, fontSize: 12.5 }}>
                        {key === "local" && <LocalEvidence evidence={meta?.evidence} />}
                        {key === "law" && <LawList lawHits={meta?.law_hits} />}
                        {key === "cases" && <div className="footnote">外部案例明细见上方回答中的「外部案例」表格（cases 源）。</div>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Mode B 报告卡片 */}
          {meta?.mode === "B" && meta.report_id != null && (
            <div className="alert blue" style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <FileText size={14} />
              <span style={{ fontSize: 13 }}>报告已落库：<b>{meta.title}</b>（模板 {meta.template_key}）</span>
              <button type="button" className="btn btn-sm" style={{ marginLeft: "auto" }} onClick={onReport}>
                查看报告存档 →
              </button>
            </div>
          )}
        </div>

        {/* chips 追问 */}
        {meta && chips.slice(0, 3).length > 0 && meta.mode !== "B" && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", paddingLeft: 4 }}>
            {chips.slice(0, 3).map((c) => (
              <button key={c} type="button" className="chip" onClick={() => onChip(c)}>{c}</button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BadgeTone({ tone, children }: { tone: "blue" | "amber" | "green" | "red" | "gray"; children: ReactNode }) {
  const bg: Record<string, { background: string; color: string }> = {
    blue: { background: "var(--primary-soft)", color: "var(--primary)" },
    amber: { background: "var(--warning-soft)", color: "var(--warning)" },
    green: { background: "var(--success-soft)", color: "var(--success)" },
    red: { background: "var(--danger-soft)", color: "var(--danger)" },
    gray: { background: "var(--surface-2)", color: "var(--muted)" },
  };
  return <span className="badge-outline" style={{ ...bg[tone], border: 0, fontSize: 11.5, padding: "1px 7px" }}>{children}</span>;
}

function LocalEvidence({ evidence }: { evidence?: Record<string, unknown>[] }) {
  if (!evidence?.length) return <div className="footnote">暂无证据卡片</div>;
  const keys = ["case_no", "biz_line", "cause", "resolve", "amount", "pay_amount", "case_status"];
  const label: Record<string, string> = {
    case_no: "案号", biz_line: "业务线", cause: "案由", resolve: "结案原因",
    amount: "标的", pay_amount: "支付额", case_status: "状态",
  };
  return (
    <div style={{ overflow: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k} style={{ textAlign: "left", padding: "4px 7px", borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" }}>{label[k]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {evidence.slice(0, 5).map((c, i) => (
            <tr key={i}>
              {keys.map((k) => (
                <td key={k} style={{ padding: "4px 7px", borderBottom: "1px solid var(--border)" }}>
                  {k === "amount" || k === "pay_amount" ? (typeof c[k] === "number" ? `¥${Number(c[k]).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}` : "—") : (c[k] == null ? "—" : String(c[k]))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LawList({ lawHits }: { lawHits?: { law: string; article: string; text: string }[] }) {
  if (!lawHits?.length) return <div className="footnote">暂无法规命中</div>;
  return (
    <div style={{ display: "grid", gap: 4 }}>
      {lawHits.slice(0, 4).map((l, i) => (
        <div key={i} style={{ fontSize: 12.5 }}>
          <b>{l.law} {l.article}</b>：{l.text.slice(0, 90)}…
        </div>
      ))}
    </div>
  );
}