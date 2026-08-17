/* 11-字典与规则（docs/02 §8.5 + plan t08-10）。
   ① 脏标记清洗台：adopt（写入 CompanyMap+清标记）/ ignore（仅审计），key=record_id:field
   ② 规则启停：rule_toggle 同步 clean_rule_version.enabled_rules 指针（保存重跑前提）
   ③ 枚举维护：enum upsert，aliases 为 {原始选项: 规范值} 合并追加
   ④ 规则预演：dicts/test 内存执行启用规则链，不落库不审计
   所有写操作后 invalidate dicts/dirty-items/metadata 三键。 */
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Beaker, Eraser, ListChecks, Pencil, Save, ShieldCheck, Sparkles, ToggleLeft, ToggleRight } from "lucide-react";
import { Alert, Badge, EmptyState, EnumBadge, PageError, PageHeader, Spinner } from "@/components/common";
import { Drawer } from "@/components/Drawer";
import { useDicts, useDirtyItems } from "@/hooks";
import { api, type DictTestResult, type DirtyItem, type EnumItem } from "@/lib/api";
import { enumTone } from "@/lib/colors";
import { fmtText } from "@/lib/format";

function toast(msg: string, isErr = false): void {
  window.dispatchEvent(new CustomEvent("lt:toast", { detail: isErr ? `⚠️ ${msg}` : msg }));
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

const COLOR_OPTIONS = ["", "green", "teal", "amber", "orange", "red", "blue", "purple", "gray"];
const TF_LABEL: Record<string, string> = { defendant: "被告", plaintiff: "原告", court: "法院", payer: "付款方", artist: "艺人" };

/* trace.reason 为审计 detail 解析得到的 {reason:...} 内层对象，扁平化为 hover 文本 */
function traceReason(t: { rule_tag?: string | null; reason?: unknown }): string {
  const r = t.reason;
  if (typeof r === "string") return r;
  if (r && typeof r === "object") {
    const inner = (r as { reason?: unknown }).reason;
    if (typeof inner === "string") return inner;
  }
  return t.rule_tag ?? "规则命中";
}

export default function DictsPage() {
  const qc = useQueryClient();
  const dicts = useDicts();
  const dirty = useDirtyItems();

  /* 清洗台输入（key → 规范值） */
  const [dvals, setDvals] = useState<Record<string, string>>({});
  /* 枚举编辑抽屉 */
  const [editing, setEditing] = useState<{ field: string; item: EnumItem } | null>(null);
  const [eLabel, setELabel] = useState("");
  const [eColor, setEColor] = useState("");
  const [eAliases, setEAliases] = useState("");
  /* 预演 */
  const [testText, setTestText] = useState("");
  const [testRes, setTestRes] = useState<DictTestResult[] | null>(null);
  /* 防重复点击 */
  const [busy, setBusy] = useState<string | null>(null);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["dicts"] });
    void qc.invalidateQueries({ queryKey: ["dirty-items"] });
    void qc.invalidateQueries({ queryKey: ["metadata"] });
  };

  const doWrite = async (key: string, okMsg: string): Promise<boolean> => {
    setBusy(key);
    try {
      const payload = dictWritePayload(key);
      await api.dictWrite(payload);
      toast(okMsg);
      invalidate();
      return true;
    } catch (e) {
      toast(errMsg(e), true);
      return false;
    } finally {
      setBusy(null);
    }
  };

  /* 由 busy key 反推 payload：rule_toggle 用 rule_tag；enum 用抽屉表单 */
  const dictWritePayload = (key: string): Parameters<typeof api.dictWrite>[0] => {
    if (key.startsWith("rule:")) {
      return { action: "rule_toggle", rule_tag: key.slice(5) }; // 不带 enabled → 后端翻转
    }
    if (editing) {
      let aliases: Record<string, string> | undefined;
      const t = eAliases.trim();
      if (t) {
        try {
          const parsed = JSON.parse(t) as unknown;
          if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) throw new Error("non-object");
          aliases = parsed as Record<string, string>;
        } catch {
          throw new Error("aliases 需为 JSON 对象，如 {\"原告撤诉(重复)\": \"原告撤诉\"}");
        }
      }
      return {
        action: "enum",
        field: editing.field,
        enum_key: editing.item.enum_key,
        label: eLabel.trim() || undefined,
        color: eColor || undefined,
        aliases,
      };
    }
    throw new Error(`未知操作：${key}`);
  };

  const openEdit = (field: string, item: EnumItem) => {
    setEditing({ field, item });
    setELabel(item.label ?? "");
    setEColor(item.color ?? "");
    setEAliases(JSON.stringify(item.aliases ?? {}, null, 2));
  };

  const doDirty = async (key: string, action: "adopt" | "ignore") => {
    const value = dvals[key]?.trim();
    if (action !== "ignore" && !value) {
      toast("请输入规范值（原始值上方可直接修改）", true);
      return;
    }
    setBusy(`dirty:${key}`);
    try {
      await api.dictDirtyAction(key, { action, value });
      toast(action === "ignore" ? "已忽略（仅审计，标记保留）" : `已采纳「${value}」写入 CompanyMap 并清除脏标记`);
      invalidate();
    } catch (e) {
      toast(errMsg(e), true);
    } finally {
      setBusy(null);
    }
  };

  const doTest = async () => {
    const samples = testText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => JSON.parse(l) as Record<string, unknown>);
    if (samples.length === 0) {
      toast("请先粘贴样本（每行一个 JSON 对象）", true);
      return;
    }
    setBusy("test");
    try {
      const r = await api.dictTest({ samples });
      setTestRes(r.data);
      toast(`预演完成：${r.data.length} 条样本（不落库不审计）`);
    } catch (e) {
      setTestRes(null);
      toast(errMsg(e), true);
    } finally {
      setBusy(null);
    }
  };

  if (dicts.isLoading || dirty.isLoading) return <Spinner label="字典与规则加载中…" />;
  if (dicts.isError) return <PageError message={errMsg(dicts.error)} onRetry={() => void dicts.refetch()} />;

  const { enums, rules, company_map } = dicts.data ?? { enums: {} as Record<string, EnumItem[]>, rules: [], company_map: [] };
  const items = (dirty.data ?? []) as DirtyItem[];
  const fieldNames = Object.keys(enums);

  return (
    <div>
      <PageHeader
        title="字典与规则"
        breadcrumb={<>枚举维护（aliases 别名合并）· 规则启停（版本指针）· 脏标记清洗台 · 预演不落库</>}
        actions={<Badge outline>P0 内少数写操作页</Badge>}
      />

      {/* ① 脏标记清洗台 */}
      <div className="card card-pad">
        <div className="card-title">
          <Eraser size={14} /> 脏标记清洗台
          <span className="sub">
            {items.length} 处待处置（adopt 写 CompanyMap{`「原始值→规范值」`}并清除标记；ignore 仅审计保留标记）
          </span>
        </div>
        {items.length === 0 ? (
          <EmptyState icon={<Sparkles size={20} />} title="无脏标记" desc="同步管道未标记脏数据，或已全部处置" />
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>案件</th>
                  <th>案号</th>
                  <th>字段</th>
                  <th>原始值 → 规范值</th>
                  <th>规则追溯</th>
                  <th style={{ width: 210 }}>处置</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => {
                  const k = it.key;
                  const val = dvals[k] ?? it.raw_value ?? "";
                  return (
                    <tr key={k}>
                      <td className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>{it.record_id}</td>
                      <td>{it.case_no ?? "—"}</td>
                      <td><span className="badge badge-plain" title={it.field}>{TF_LABEL[it.field] ?? it.field}</span></td>
                      <td style={{ minWidth: 220 }}>
                        <input
                          value={val}
                          onChange={(e) => setDvals((p) => ({ ...p, [k]: e.target.value }))}
                          placeholder={it.raw_value ?? "（无原始值）"}
                          style={{ width: "100%" }}
                        />
                      </td>
                      <td className="muted" style={{ fontSize: 11, maxWidth: 180 }}>
                        {it.trace.length === 0 ? "—" : (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                            {it.trace.map((t, i) => (
                              <span key={i} title={`${t.rule_tag ?? "?"}：${traceReason(t)}`}>
                                <Badge tone="amber" dot={false}>{t.rule_tag ?? "?"}</Badge>
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            disabled={busy === `dirty:${k}`}
                            onClick={() => void doDirty(k, "adopt")}
                          >
                            采纳/改名
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm"
                            disabled={busy === `dirty:${k}`}
                            onClick={() => void doDirty(k, "ignore")}
                          >
                            忽略
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ② 清洗规则 */}
      <div className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <ShieldCheck size={14} /> 清洗规则 <span className="sub">启停写审计 + 同步版本指针（enabled_rules 快照）</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>规则</th>
                <th>版本</th>
                <th>目标字段</th>
                <th>类型</th>
                <th>匹配 → 替换</th>
                <th>优先级</th>
                <th>状态</th>
                <th style={{ width: 90 }}>启停</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => {
                const key = `rule:${r.rule_tag}`;
                return (
                  <tr key={r.rule_tag}>
                    <td><Badge tone="blue" dot={false}>{r.rule_tag}</Badge></td>
                    <td className="muted">{r.version ?? "—"}</td>
                    <td>{r.target_field ?? "—"}</td>
                    <td className="muted">{r.rule_type ?? "—"}</td>
                    <td className="muted" style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.pattern ?? "—"}<span style={{ color: "var(--muted-2)" }}> → </span>{r.replacement ?? "—"}
                    </td>
                    <td className="num">{r.priority}</td>
                    <td><Badge tone={r.enabled ? "green" : "gray"}>{r.enabled ? "启用" : "停用"}</Badge></td>
                    <td>
                      <button
                        type="button"
                        className="icon-btn"
                        title={r.enabled ? "停用（保存重跑依据）" : "启用"}
                        disabled={busy === key}
                        onClick={() => void doWrite(key, `${r.rule_tag} 已${r.enabled ? "停用" : "启用"}`)}
                      >
                        {r.enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {rules.some((r) => !r.description) ? null : (
          <div style={{ marginTop: 8, fontSize: 11.5, color: "var(--muted-2)" }}>
            说明：{rules.map((r) => `${r.rule_tag}:${r.description}`).join("；")}
          </div>
        )}
      </div>

      {/* ③ 枚举字典 */}
      <div className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <ListChecks size={14} /> 枚举字典 <span className="sub">按字段分组 · 编辑为 upsert（aliases 合并追加）</span>
        </div>
        {fieldNames.length === 0 ? (
          <EmptyState icon={<ListChecks size={20} />} title="暂无枚举" desc="同步管道按元数据初始化枚举字典" />
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {fieldNames.map((f) => (
              <div key={f} className="card" style={{ padding: 10 }}>
                <div className="f-label" style={{ marginBottom: 6 }}>{f}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {enums[f].map((e) => (
                    <span key={e.enum_key} className="badge badge-plain" style={{ gap: 6, paddingRight: 4 }}>
                      <EnumBadge tone={enumTone(e.color)}>{e.label}</EnumBadge>
                      <span className="muted" style={{ fontSize: 11 }}>{e.enum_key}</span>
                      {e.aliases && Object.keys(e.aliases).length > 0 && (
                        <span className="sub" title={JSON.stringify(e.aliases)}>{Object.keys(e.aliases).length} 别名</span>
                      )}
                      <button type="button" className="icon-btn" style={{ width: 20, height: 20 }} title="编辑" onClick={() => openEdit(f, e)}>
                        <Pencil size={12} />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 公司归一（只读） */}
      <div className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          公司归一映射 <span className="sub">CompanyMap：清洗管道 + 人工采纳共用（只读展示）</span>
        </div>
        {company_map.length === 0 ? (
          <div className="muted" style={{ fontSize: 12.5 }}>暂无映射</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="tbl">
              <thead>
                <tr><th>原始值</th><th>规范值</th><th>来源</th><th>状态</th></tr>
              </thead>
              <tbody>
                {company_map.map((c) => (
                  <tr key={c.id}>
                    <td>{c.company_raw}</td>
                    <td><Badge tone="blue" dot={false}>{c.canonical}</Badge></td>
                    <td className="muted">{c.source ?? "—"}</td>
                    <td><Badge tone={c.enabled ? "green" : "gray"}>{c.enabled ? "启用" : "停用"}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ④ 规则预演 */}
      <div className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <Beaker size={14} /> 规则预演 <span className="sub">每行一个 JSON 样本 → 内存执行启用规则链（R01~R08/R10）不落库</span>
        </div>
        <textarea
          value={testText}
          onChange={(e) => setTestText(e.target.value)}
          rows={4}
          spellCheck={false}
          placeholder={'{"record_id": "test_1", "defendant_raw": "北京字节跳动科技有限公司"}\n{"representative_raw": "张三（北京观韬中茂律所）"}'
          }
          style={{ width: "100%", fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
          <button type="button" className="btn btn-sm btn-primary" disabled={busy === "test"} onClick={() => void doTest()}>
            <Beaker size={12} /> 运行预演
          </button>
          <span className="muted" style={{ fontSize: 11.5 }}>试算命中事件预览（保存重跑前验证）</span>
        </div>
        {testRes && (
          <div style={{ marginTop: 10 }}>
            <Alert kind="amber">预演为内存执行，不落库不审计；命中即 dirty_flags 字段级标记。</Alert>
            {testRes.map((tr) => (
              <div key={tr.index} className="card" style={{ marginTop: 8, padding: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <span className="muted" style={{ fontSize: 11 }}>#{tr.index}</span>
                  <span className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>{tr.record_id}</span>
                  <Badge tone={tr.changed ? "amber" : "green"}>{tr.changed ? "有变更" : "未命中"}</Badge>
                  {tr.error && <Badge tone="red">错误</Badge>}
                </div>
                {tr.error ? (
                  <div className="alert red" style={{ marginTop: 6 }}><span className="grow">{fmtText(tr.error)}</span></div>
                ) : (
                  <>
                    {tr.dirty_flags.length > 0 && (
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
                        {tr.dirty_flags.map((f) => <Badge key={f} tone="red" dot={false}>脏:{f}</Badge>)}
                      </div>
                    )}
                    {tr.events.length > 0 && (
                      <table className="tbl" style={{ marginTop: 6 }}>
                        <thead>
                          <tr><th>规则</th><th>字段</th><th>动作</th><th>旧值 → 新值</th></tr>
                        </thead>
                        <tbody>
                          {tr.events.map((ev, i) => (
                            <tr key={i}>
                              <td><Badge tone="blue" dot={false}>{ev.rule_tag ?? "?"}</Badge></td>
                              <td>{ev.field ?? "—"}</td>
                              <td className="muted">{ev.action ?? "—"}</td>
                              <td className="muted" style={{ maxWidth: 320 }}>
                                <span style={{ textDecoration: "line-through" }}>{String(ev.old_value ?? "")}</span>
                                <span style={{ color: "var(--muted-2)" }}> → </span>
                                <span style={{ color: "var(--success)" }}>{String(ev.new_value ?? "")}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 枚举编辑抽屉 */}
      <Drawer
        title={`编辑枚举：${editing?.field}/${editing?.item.enum_key ?? ""}`}
        open={!!editing}
        onClose={() => setEditing(null)}
        foot={
          <button
            type="button"
            className="btn btn-sm btn-primary"
            disabled={busy === "enum-save"}
            onClick={() => void (async () => {
              if (await doWrite("enum-save", `已保存 ${editing?.item.enum_key}（aliases 合并追加）`)) setEditing(null);
            })()}
          >
            <Save size={12} /> 保存
          </button>
        }
      >
        {editing && (
          <div style={{ display: "grid", gap: 10 }}>
            <div>
              <div className="f-label">规范值（enum_key）</div>
              <input value={editing.item.enum_key} disabled />
              <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>enum_key 为唯一键，如需改名请删除后重建</div>
            </div>
            <div>
              <div className="f-label">显示名（label）</div>
              <input value={eLabel} onChange={(e) => setELabel(e.target.value)} placeholder="显示名" />
            </div>
            <div>
              <div className="f-label">颜色（color）</div>
              <select value={eColor} onChange={(e) => setEColor(e.target.value)} style={{ width: "100%" }}>
                {COLOR_OPTIONS.map((c) => (
                  <option key={c || "none"} value={c}>{c || "（默认/不改）"}</option>
                ))}
              </select>
            </div>
            <div>
              <div className="f-label">别名映射（aliases JSON，{`{原始选项: 规范值}`} 合并追加）</div>
              <textarea
                value={eAliases}
                onChange={(e) => setEAliases(e.target.value)}
                rows={5}
                spellCheck={false}
                style={{ width: "100%", fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}
              />
            </div>
            <Alert kind="blue">清空 label/color 提交 = 保持不变；aliases 空 = 跳过合并。</Alert>
          </div>
        )}
      </Drawer>
    </div>
  );
}