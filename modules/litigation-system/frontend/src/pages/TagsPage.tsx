/* 11-标签管理（docs/02 §6.4 + plan t27~29 + 后端 /tags 8 端点）
   左=标签分组列表（色点/名称/kind/计数）＋新建/改名/合并/删除（删除确认影响 N 案）、批量打标入口；
   右=选中标签下对象明细表（tag-objects 按 target_type 分组计数，案件行点击 → 详情页）；
   预置标签说明面板（§3.11 建议清单）；写操作均经 audit 记审计日志（docs/03 §6.1）。 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GitMerge, Layers, Pencil, Plus, Tag as TagIcon, Trash2 } from "lucide-react";
import { Drawer } from "@/components/Drawer";
import { Badge, EmptyState, EnumBadge, PageError, PageHeader, Spinner } from "@/components/common";
import { useTagMutation, useTagObjects, useTags } from "@/hooks";
import type { TagItem, TagTargetType } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import type { Tone } from "@/lib/colors";

/* 8 色循环（docs/02 §6.4 标签色） */
const TAG_COLORS = ["#4F46E5", "#DC2626", "#D97706", "#059669", "#2563EB", "#7C3AED", "#DB2777", "#0891B2"];

/* §3.11 预置标签建议清单 */
const PRESETS = [
  { name: "版权方—音集协", desc: "按版权方归一实体建标签，检索/占比下沉可直接引用" },
  { name: "高判赔风险", desc: "判赔高于 P75 或带存疑金额字段的敏感案件" },
  { name: "和解优先", desc: "结案原因为和解类的持续跟踪队列" },
  { name: "系列案", desc: "同原告/同曲目批量起诉的系列案件" },
  { name: "终本跟踪", desc: "执行终本后持续跟踪回款状态" },
] as const;

function toast(msg: string, isErr = false): void {
  window.dispatchEvent(new CustomEvent("lt:toast", { detail: isErr ? `⚠️ ${msg}` : msg }));
}
function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
const NUM = { textAlign: "right", fontVariantNumeric: "tabular-nums" } as const;
const COLOR_DOT = { width: 10, height: 10, borderRadius: 99, flexShrink: 0, display: "inline-block" } as const;
const TYPE_LABEL: Record<TagTargetType, string> = { case: "案件", song: "歌曲", party: "对手方", external_case: "外部案例" };

function kindTone(kind: TagItem["kind"]): Tone {
  return kind === "derived" ? "amber" : "blue";
}

export default function TagsPage() {
  const nav = useNavigate();
  const { data: tags, isPending, isError, refetch } = useTags();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  /* 批量打标抽屉 */
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchName, setBatchName] = useState("");
  const [batchType, setBatchType] = useState<TagTargetType>("case");
  const [batchIds, setBatchIds] = useState("");
  /* 管理抽屉（改名/改色/描述/合并/删除） */
  const [manage, setManage] = useState<TagItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editColor, setEditColor] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [mergeInto, setMergeInto] = useState("");
  const [confirming, setConfirming] = useState(false);

  const mut = useTagMutation();
  const { data: objs } = useTagObjects(selectedId ?? undefined);
  const activeId = selectedId ?? tags?.[0]?.id ?? null;
  const active = tags?.find((t) => t.id === activeId) ?? null;

  const openManage = (t: TagItem) => {
    setManage(t);
    setEditName(t.name);
    setEditColor(t.color ?? "");
    setEditDesc(t.description ?? "");
    setMergeInto("");
    setConfirming(false);
  };

  const doCreate = () => {
    const name = newName.trim();
    if (!name) {
      toast("请输入标签名称", true);
      return;
    }
    mut.create.mutate(
      { name, kind: "manual", color: TAG_COLORS[(tags?.length ?? 0) % TAG_COLORS.length], description: null },
      {
        onSuccess: (r) => {
          const t = r.data;
          setNewName("");
          setSelectedId(t.id);
          toast(`已创建标签「${t.name}」`);
        },
        onError: (e) => toast(errMsg(e), true),
      },
    );
  };

  const doSave = () => {
    if (!manage) return;
    mut.update.mutate(
      { id: manage.id, name: editName.trim() || manage.name, color: editColor || null, description: editDesc.trim() || null },
      {
        onSuccess: (r) => {
          toast(`已保存「${r.data.name}」`);
          setManage(null);
        },
        onError: (e) => toast(errMsg(e), true),
      },
    );
  };

  const doMerge = () => {
    if (!manage || !mergeInto) return;
    mut.merge.mutate(
      { from_id: manage.id, into_id: Number(mergeInto) },
      {
        onSuccess: (r) => {
          const m = r.data;
          toast(`已将「${manage.name}」并入「${m.into_name}」（迁移 ${m.moved_links} 条关联）`);
          setManage(null);
          if (selectedId === manage.id) setSelectedId(m.into_id);
        },
        onError: (e) => toast(errMsg(e), true),
      },
    );
  };

  const doDelete = () => {
    if (!manage) return;
    mut.remove.mutate(manage.id, {
      onSuccess: () => {
        toast(`已删除标签「${manage.name}」`);
        if (selectedId === manage.id) setSelectedId(null);
        setManage(null);
      },
      onError: (e) => toast(errMsg(e), true),
    });
  };

  const doBatch = () => {
    const name = batchName.trim();
    const ids = batchIds.split(/[,\n，；;]/).map((s) => s.trim()).filter(Boolean);
    if (!name) {
      toast("请输入标签名称", true);
      return;
    }
    if (!ids.length) {
      toast("请输入至少一个对象 ID", true);
      return;
    }
    mut.batch.mutate(
      { tag_name: name, target_type: batchType, target_ids: ids },
      {
        onSuccess: (r) => {
          const b = r.data;
          toast(`批量打标完成：新增 ${b.new_links} 条关联（共 ${b.targets} 个对象）→「${b.tag_name}」`);
          setBatchOpen(false);
          setBatchName("");
          setBatchIds("");
          setSelectedId(b.tag_id);
        },
        onError: (e) => toast(errMsg(e), true),
      },
    );
  };

  const caseObjs = (objs?.objects ?? []).filter((o) => o.target_type === "case");
  const byType = objs?.by_type ?? ({} as Record<TagTargetType, number>);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <PageHeader
        title="标签管理"
        breadcrumb="M4 标签体系 · 案件/歌曲/对手方统一打标与派生标签"
        actions={
          <>
            <button type="button" className="btn" onClick={() => setBatchOpen(true)}>
              <TagIcon size={13} /> 批量打标
            </button>
            <span className="footnote" style={{ alignSelf: "center" }}>写操作均记 audit_logs 审计</span>
          </>
        }
      />

      {isPending && <Spinner label="加载标签…" />}
      {isError && <PageError message="标签列表加载失败" onRetry={() => void refetch()} />}
      {!isPending && !isError && (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 14, alignItems: "start" }}>
          {/* ── 左：标签分组列表 ── */}
          <div className="card" style={{ padding: 0 }}>
            <div className="card-pad" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="card-title"><Layers size={14} /> 标签分组（{fmtNum(tags?.length ?? 0)}）</span>
              <span className="footnote">kind=人工/派生</span>
            </div>
            <div style={{ display: "grid", maxHeight: 420, overflow: "auto", borderTop: "1px solid var(--border)" }}>
              {(tags ?? []).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSelectedId(t.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 9,
                    padding: "9px 14px",
                    border: 0,
                    borderBottom: "1px solid var(--border)",
                    cursor: "pointer",
                    textAlign: "left",
                    fontSize: 13,
                    background: t.id === activeId ? "var(--surface-2)" : "transparent",
                    color: "var(--text)",
                  }}
                >
                  <i style={{ ...COLOR_DOT, background: t.color ?? "#94A3B8" }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.name}</span>
                  <EnumBadge tone={kindTone(t.kind)}>{t.kind === "derived" ? "派生" : "人工"}</EnumBadge>
                  <span className="footnote" style={NUM}>{(t.link_count ?? 0)} 项</span>
                  <span
                    role="button"
                    title="管理：改名/改色/合并/删除"
                    onClick={(e) => {
                      e.stopPropagation();
                      openManage(t);
                    }}
                    style={{ display: "grid", placeItems: "center", width: 22, height: 22, borderRadius: 6, color: "var(--muted)", cursor: "pointer" }}
                  >
                    <Pencil size={12} />
                  </span>
                </button>
              ))}
              {(tags ?? []).length === 0 && <EmptyState title="暂无标签" desc="可在下方新建，或在详情页/检索页打标" />}
            </div>
            <div className="card-pad" style={{ display: "flex", gap: 8, borderTop: "1px solid var(--border)" }}>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doCreate()}
                placeholder="新标签名称（如：高判赔风险）"
                style={{ flex: 1, height: 32, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", padding: "0 10px", outline: "none", color: "var(--text)", fontSize: 13 }}
              />
              <button type="button" className="btn btn-primary" style={{ height: 32 }} onClick={doCreate}>
                <Plus size={13} /> 新建
              </button>
            </div>
          </div>

          {/* ── 右：选中标签对象明细 ── */}
          <div style={{ display: "grid", gap: 14 }}>
            <div className="card">
              <div className="card-pad" style={{ display: "grid", gap: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <i style={{ ...COLOR_DOT, width: 12, height: 12, background: active?.color ?? "#94A3B8" }} />
                  <span className="card-title" style={{ fontSize: 15 }}>{active?.name ?? "未选择标签"}</span>
                  {active && <EnumBadge tone={kindTone(active.kind)}>{active.kind === "derived" ? "派生标签" : "人工标签"}</EnumBadge>}
                  {active && active.link_count != null && <Badge tone="gray">{fmtNum(active.link_count)} 项关联</Badge>}
                </div>
                {active?.description && <div className="help">{active.description}</div>}
                {active && (
                  <div className="footnote" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                    {(Object.keys(byType) as TagTargetType[]).map((k) => (
                      <span key={k}>{(byType[k] ?? 0) > 0 && `${TYPE_LABEL[k]} ${byType[k]} 项`}</span>
                    ))}
                    {Object.values(byType).every((n) => !n) && <span>暂无关联对象</span>}
                  </div>
                )}
              </div>
              <div className="tbl-wrap" style={{ borderTop: "1px solid var(--border)" }}>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>对象名称</th>
                      <th>类型</th>
                      <th>关联时间</th>
                      <th style={NUM}>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {caseObjs.length === 0 && (
                      <tr>
                        <td colSpan={4}>
                          <EmptyState icon="🏷" title="暂无案件关联" desc="在检索页勾选案件批量打标，或标签合并/删除会更新此处" />
                        </td>
                      </tr>
                    )}
                    {caseObjs.map((o) => (
                      <tr key={`${o.target_type}:${o.target_id}`} onClick={() => nav(`/cases/${o.target_id}`)} style={{ cursor: "pointer" }}>
                        <td style={{ color: "var(--primary)" }}>{o.name}</td>
                        <td><EnumBadge tone="blue">案件</EnumBadge></td>
                        <td className="footnote">{o.linked_at ? new Date(o.linked_at).toLocaleString("zh-CN") : "—"}</td>
                        <td style={NUM}>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              void mut.link.mutateAsync({ tag_id: activeId!, target_type: "case", target_id: o.target_id, link: false }).then(() => toast("已移除关联"));
                            }}
                          >
                            移除
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 预置标签说明面板 + 审计说明 */}
            <div className="alert blue" style={{ display: "grid", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
                <Layers size={14} /> 预置标签建议（docs/03 §3.11）
              </div>
              <div style={{ display: "grid", gap: 6, fontSize: 12.5 }}>
                {PRESETS.map((p) => (
                  <div key={p.name} style={{ display: "flex", gap: 8 }}>
                    <span style={{ whiteSpace: "nowrap", fontWeight: 600 }}>{p.name}</span>
                    <span style={{ color: "var(--muted)" }}>{p.desc}</span>
                  </div>
                ))}
              </div>
              <div className="footnote">提示：新建标签后可在检索页勾选案件（工具条标签按钮）或本案页「知识区」打标；改名/合并/删除均记录操作审计（docs/03 §6.1）。</div>
            </div>
          </div>
        </div>
      )}

      {/* 批量打标抽屉 */}
      <Drawer
        title="批量打标（tagBatch）"
        open={batchOpen}
        onClose={() => setBatchOpen(false)}
        foot={
          <>
            <button type="button" className="btn" onClick={() => setBatchOpen(false)}>取消</button>
            <button type="button" className="btn btn-primary" onClick={() => void doBatch()}>
              <TagIcon size={13} /> 执行打标
            </button>
          </>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "grid", gap: 6 }}>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>标签名称（不存在自动创建人工标签）</label>
            <input
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              placeholder="如：高判赔风险"
              style={{ height: 34, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", padding: "0 10px", outline: "none", color: "var(--text)" }}
            />
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>对象类型</label>
            <select
              value={batchType}
              onChange={(e) => setBatchType(e.target.value as TagTargetType)}
              style={{ height: 34, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", padding: "0 10px", outline: "none", color: "var(--text)" }}
            >
              {(Object.keys(TYPE_LABEL) as TagTargetType[]).map((k) => (
                <option key={k} value={k}>{TYPE_LABEL[k]}</option>
              ))}
            </select>
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>对象 ID 列表（逗号/换行/分号分隔）</label>
            <textarea
              value={batchIds}
              onChange={(e) => setBatchIds(e.target.value)}
              rows={5}
              placeholder={batchType === "case" ? "案件 record_id，如：CASE-0001, CASE-0002…" : "对象 ID（含空白分隔）"}
              style={{ border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", padding: "8px 10px", outline: "none", color: "var(--text)", fontSize: 13, resize: "vertical" }}
            />
          </div>
          <div className="footnote">与检索页「勾选案件→批量打标」等价，但支持案件/歌曲/对手方/外部案例四类对象。</div>
        </div>
      </Drawer>

      {/* 标签管理抽屉：改名/改色/描述/合并/删除 */}
      <Drawer
        title={manage ? `管理标签「${manage.name}」` : "标签管理"}
        open={manage != null}
        onClose={() => setManage(null)}
        foot={
          <>
            <button type="button" className="btn" onClick={() => setManage(null)}>取消</button>
            <button type="button" className="btn btn-primary" onClick={doSave} disabled={!editName.trim()}>
              保存修改
            </button>
          </>
        }
      >
        {manage && (
          <div style={{ display: "grid", gap: 14 }}>
            <div style={{ display: "grid", gap: 6 }}>
              <label style={{ fontSize: 12, color: "var(--muted)" }}>标签名称</label>
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                style={{ height: 34, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", padding: "0 10px", outline: "none", color: "var(--text)" }}
              />
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              <label style={{ fontSize: 12, color: "var(--muted)" }}>标签颜色（8 色循环，留空使用默认灰）</label>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                {TAG_COLORS.map((c) => (
                  <i
                    key={c}
                    onClick={() => setEditColor(c)}
                    style={{
                      ...COLOR_DOT,
                      width: 20,
                      height: 20,
                      background: c,
                      cursor: "pointer",
                      outline: editColor === c ? "2px solid var(--primary)" : "1px solid var(--border)",
                      outlineOffset: 2,
                    }}
                  />
                ))}
                {editColor && <span className="footnote" onClick={() => setEditColor("")} style={{ cursor: "pointer" }}>清除</span>}
              </div>
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              <label style={{ fontSize: 12, color: "var(--muted)" }}>描述</label>
              <input
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                placeholder="标签用途说明"
                style={{ height: 34, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", padding: "0 10px", outline: "none", color: "var(--text)" }}
              />
            </div>

            {/* 合并 */}
            <div style={{ display: "grid", gap: 6, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              <label style={{ fontSize: 12, color: "var(--muted)" }}>
                <GitMerge size={12} style={{ verticalAlign: -2 }} /> 合并到其他标签（本标签关联迁移过去）
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <select
                  value={mergeInto}
                  onChange={(e) => setMergeInto(e.target.value)}
                  style={{ flex: 1, height: 34, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", padding: "0 10px", outline: "none", color: "var(--text)" }}
                >
                  <option value="">选择目标标签…</option>
                  {(tags ?? []).filter((t) => t.id !== manage.id).map((t) => (
                    <option key={t.id} value={t.id}>{t.name}（{t.link_count ?? 0} 项）</option>
                  ))}
                </select>
                <button type="button" className="btn" onClick={doMerge} disabled={!mergeInto}>
                  合并
                </button>
              </div>
            </div>

            {/* 删除（两级确认，显示影响 N 案） */}
            <div style={{ display: "grid", gap: 6, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              <label style={{ fontSize: 12, color: "var(--muted)" }}>危险区</label>
              {confirming ? (
                <div className="alert red" style={{ display: "grid", gap: 8 }}>
                  <div style={{ fontSize: 13 }}>
                    确定删除「{manage.name}」？将解除其关联的 <b>{fmtNum(manage.link_count ?? 0)}</b> 项对象（案件/歌曲/对手方）且不可恢复。
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button type="button" className="btn btn-danger" onClick={doDelete}>确认删除</button>
                    <button type="button" className="btn" onClick={() => setConfirming(false)}>取消</button>
                  </div>
                </div>
              ) : (
                <button type="button" className="btn" style={{ borderColor: "var(--danger)", color: "var(--danger)" }} onClick={() => setConfirming(true)}>
                  <Trash2 size={13} /> 删除标签（影响 {fmtNum(manage.link_count ?? 0)} 项关联）
                </button>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}