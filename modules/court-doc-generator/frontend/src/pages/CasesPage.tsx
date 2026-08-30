import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Zap, Eye, Search, X, Download, Camera, Edit2 } from "lucide-react";
import { caseApi, companyApi, agentApi, generateApi, Case } from "../lib/api";
import { useDebounced } from "../hooks/useDebounced";
import { useFormDraft, draftKey, loadDraft, clearDraft } from "../hooks/useFormDraft";
import PdfPreviewModal from "../components/PdfPreviewModal";
import CaseDetailModal from "../components/CaseDetailModal";
import ConfirmDialog from "../components/ConfirmDialog";
import PresetInput from "../components/PresetInput";
import ScanModal from "../components/ScanModal";

const EMPTY_FORM = {
  case_number: "", court: "", cause: "",
  hearing_date: "", opposing_party: "", our_role: "原告",
  company_id: null as number | null, agent_id: null as number | null,
};

export default function CasesPage() {
  const qc = useQueryClient();
  const workspaceId = sessionStorage.getItem("_ws_id");
  const [showForm, setShowForm] = useState(false);
  // F2：待恢复草稿（检测到未提交草稿时弹确认）
  const [draftPending, setDraftPending] = useState<null | typeof EMPTY_FORM>(null);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [generating, setGenerating] = useState<number | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [previewFile, setPreviewFile] = useState<{ path: string; name: string } | null>(null);
  // 确认弹窗："delete" | "generate" | null
  const [confirm, setConfirm] = useState<{ type: "delete" | "generate"; caseId: number } | null>(null);
  // 案件详情弹窗
  const [detailCase, setDetailCase] = useState<Case | null>(null);
  // 扫描起诉状弹窗
  const [scanOpen, setScanOpen] = useState(false);
  // 编辑中的案件
  const [editingCase, setEditingCase] = useState<Case | null>(null);

  const [form, setForm] = useState(EMPTY_FORM);

  // F2：表单打开期间 1s 防抖保存草稿；关闭/卸载时落盘
  const draftKeyStr = workspaceId ? draftKey(workspaceId, "case-form") : "";
  useFormDraft(draftKeyStr, form, showForm);
  // 打开表单时检测是否有未提交草稿
  useEffect(() => {
    if (!showForm || !draftKeyStr) return;
    const draft = loadDraft<typeof EMPTY_FORM>(draftKeyStr);
    if (draft && (draft.case_number || draft.court || draft.cause || draft.hearing_date || draft.opposing_party)) {
      setDraftPending(draft);
    }
  }, [showForm, draftKeyStr]);

  // 搜索/筛选（防抖搜索词 300ms）
  const [filters, setFilters] = useState({
    search: "", status: "", hearing_from: "", hearing_to: "",
  });
  const debouncedSearch = useDebounced(filters.search, 300);
  const activeFilters = { ...filters, search: debouncedSearch };
  const hasFilters = Object.entries(activeFilters).some(([, v]) => v !== "");
  const [exporting, setExporting] = useState(false);

  const { data: cases = [], isLoading } = useQuery({
    queryKey: ["cases", activeFilters],
    queryFn: () => caseApi.list(activeFilters),
  });
  const { data: companies = [] } = useQuery({ queryKey: ["companies"], queryFn: companyApi.list });
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: agentApi.list });

  const create = useMutation({
    mutationFn: (body: typeof form) => caseApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases"] });
      setShowForm(false);
      setForm(EMPTY_FORM);
      clearDraft(draftKeyStr); // 提交成功即清除草稿
      setFormError("");
      setFormSuccess("案件已创建");
      setTimeout(() => setFormSuccess(""), 3000);
    },
    onError: (err: unknown) => { setFormError(err instanceof Error ? err.message : "保存失败"); },
  });

  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: typeof form }) => caseApi.update(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases"] });
      setEditingCase(null);
      setForm(EMPTY_FORM);
      setFormError("");
      setFormSuccess("案件已更新");
      setTimeout(() => setFormSuccess(""), 3000);
    },
    onError: (err: unknown) => { setFormError(err instanceof Error ? err.message : "更新失败"); },
  });

  const remove = useMutation({
    mutationFn: (id: number) => caseApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases"] }),
    onError: (err: unknown) => alert(err instanceof Error ? err.message : "删除失败"),
  });

  const generate = useMutation({
    mutationFn: ({ case_id, company_id, agent_id }: { case_id: number; company_id: number; agent_id: number }) =>
      generateApi.generate(case_id, company_id, agent_id),
    onSuccess: (data) => {
      setGenerating(null);
      // F-062（v2.2.3）：生成不完整时显性告警，不再假装全部成功
      const missing = data.missing ?? [];
      if (missing.length > 0) {
        const total = data.total_expected ?? 7;
        setResult(
          `⚠️ 生成不完整：${total} 份材料中缺 ${missing.length} 份（${missing.join("、")}）。` +
          `${data.merged_pdf ? "已生成合并 PDF（缺份不在其中），请补充后重新生成。" : "未生成合并 PDF。"}`
        );
        return;
      }
      if (data.merged_pdf) {
        // 提取 output_dir 中 workspaces/ 前缀的相对路径（与 files API 拼接一致）
        const wsIdx = data.output_dir.indexOf("workspaces/");
        const base = wsIdx >= 0 ? data.output_dir.slice(wsIdx) : data.output_dir;
        setPreviewFile({
          name: data.merged_pdf.split("/").pop()!,
          path: base + "/" + data.merged_pdf.split("/").pop(),
        });
        setResult(`✅ 生成完成！共 ${data.files.length} 个文件`);
      } else {
        setResult(`✅ 生成完成！输出目录：${data.output_dir}`);
      }
    },
    onError: (err: unknown) => {
      setGenerating(null);
      setResult(err instanceof Error ? err.message : "生成失败");
    },
  });

  const hasData = companies.length > 0 && agents.length > 0;

  return (
    <div>
      {previewFile && (
        <PdfPreviewModal
          filePath={previewFile.path}
          title={previewFile.name}
          onClose={() => setPreviewFile(null)}
        />
      )}
      {scanOpen && (
        <ScanModal
          open={scanOpen}
          onClose={() => setScanOpen(false)}
          onApply={m => {
            // 扫描结果直接覆盖草稿，避免刚填充完又被旧草稿恢复弹窗打断
            clearDraft(draftKeyStr);
            setDraftPending(null);
            setForm({ ...EMPTY_FORM, ...m });
            setScanOpen(false);
          }}
        />
      )}
      {detailCase && (
        <CaseDetailModal caseItem={detailCase} onClose={() => setDetailCase(null)} />
      )}
      {draftPending && (
        <ConfirmDialog
          title="检测到未提交的草稿"
          message={`之前填写的案件信息尚未提交（案号：${draftPending.case_number || "无"}）。\n要恢复继续填写吗？`}
          confirmText="恢复草稿"
          onCancel={() => { clearDraft(draftKeyStr); setDraftPending(null); }}
          onConfirm={() => { setForm(draftPending); setDraftPending(null); }}
        />
      )}
      {confirm && (
        <ConfirmDialog
          title={confirm.type === "delete" ? "删除案件" : "生成出庭材料"}
          message={
            confirm.type === "delete"
              ? `确定删除案件「${cases.find(c => c.id === confirm.caseId)?.case_number || ""}」吗？\n删除后不可恢复。`
              : (() => {
                  const c = cases.find(x => x.id === confirm.caseId);
                  const coName = c?.company_id ? (companies.find(x => x.id === c.company_id)?.name || "—") : "未绑定公司";
                  const aName = c?.agent_id ? (agents.find(x => x.id === c.agent_id)?.name || "—") : "未绑定代理人";
                  if (!c?.company_id || !c?.agent_id) {
                    return `案件「${c?.case_number || ""}」未绑定公司或代理人。\n请先编辑案件，选择委托公司和代理人后再生成。`;
                  }
                  return `确定要生成案件「${c?.case_number || ""}」的出庭材料吗？\n将使用：公司「${coName}」+ 代理人「${aName}」`;
                })()
          }
          confirmText={confirm.type === "delete" ? "删除" : "确认生成"}
          danger={confirm.type === "delete"}
          onCancel={() => setConfirm(null)}
          onConfirm={() => {
            if (confirm.type === "delete") {
              remove.mutate(confirm.caseId);
            } else {
              const c = cases.find(x => x.id === confirm.caseId);
              if (c?.company_id && c?.agent_id) {
                setGenerating(confirm.caseId);
                setResult(null);
                generate.mutate({ case_id: confirm.caseId, company_id: c.company_id, agent_id: c.agent_id });
              } else {
                setResult("⚠️ 请先编辑案件，绑定委托公司和代理人后再生成");
              }
            }
            setConfirm(null);
          }}
        />
      )}

      <div className="page-header">
        <h1 className="page-title">📋 案件管理</h1>
        <div className="page-actions">
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            <Plus size={14} /> 新建案件
          </button>
        </div>
      </div>

      {result && (
        <div className={`alert ${result.includes("✅") ? "alert-success" : "alert-error"}`} style={{ whiteSpace: "pre-wrap" }}>
          {result}
        </div>
      )}

      {(showForm || editingCase) && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>{editingCase ? "编辑案件" : "新建案件"}</h3>
            {/* 扫描起诉状入口：仅新建时显示 */}
            {!editingCase && (
              <button type="button" className="btn btn-outline" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setScanOpen(true)}>
                <Camera size={12} /> 扫描起诉状填入
              </button>
            )}
          </div>
          {formError && <div className="alert alert-error">{formError}</div>}
          {formSuccess && <div className="alert alert-success">{formSuccess}</div>}
          <form onSubmit={e => {
            e.preventDefault();
            if (!form.case_number.trim()) { setFormError("请填写案号"); return; }
            setFormError("");
            if (editingCase) {
              update.mutate({ id: editingCase.id, body: form });
            } else {
              create.mutate(form);
            }
          }}>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">案号 *</label>
                <input className="form-input" value={form.case_number} onChange={e => setForm({ ...form, case_number: e.target.value })} required placeholder="如：（2026）京0101民初1234号" />
              </div>
              <div className="form-group">
                <label className="form-label">案由</label>
                <PresetInput kind="cause" value={form.cause} onChange={v => setForm({ ...form, cause: v })} placeholder="如：合同" />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">审理法院</label>
                <PresetInput kind="court" value={form.court} onChange={v => setForm({ ...form, court: v })} placeholder="如：北京市朝阳区人民法院" />
              </div>
              <div className="form-group">
                <label className="form-label">开庭日期</label>
                <input className="form-input" type="date" value={form.hearing_date} onChange={e => setForm({ ...form, hearing_date: e.target.value })} />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">我方角色</label>
                <select className="form-input" value={form.our_role} onChange={e => setForm({ ...form, our_role: e.target.value })}>
                  <option>原告</option><option>被告</option><option>第三人</option><option>法院</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">对方当事人</label>
                <input className="form-input" value={form.opposing_party} onChange={e => setForm({ ...form, opposing_party: e.target.value })} placeholder="如：北京XX科技有限公司" />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">委托公司</label>
                <select className="form-input" value={form.company_id ?? ""} onChange={e => setForm({ ...form, company_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">— 选择公司 —</option>
                  {companies.map(co => <option key={co.id} value={co.id}>{co.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">代理人</label>
                <select className="form-input" value={form.agent_id ?? ""} onChange={e => setForm({ ...form, agent_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">— 选择代理人 —</option>
                  {agents.map(a => <option key={a.id} value={a.id}>{a.name}{a.position ? `（${a.position}）` : ""}</option>)}
                </select>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn btn-primary" disabled={create.isPending || update.isPending}>{create.isPending || update.isPending ? "保存中..." : "保存"}</button>
              <button type="button" className="btn" onClick={() => { setShowForm(false); setEditingCase(null); setForm(EMPTY_FORM); }}>取消</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="filter-bar" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
          <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
            <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted, #999)" }} />
            <input
              className="form-input"
              style={{ paddingLeft: 30 }}
              placeholder="搜索案号 / 法院 / 案由..."
              value={filters.search}
              onChange={e => setFilters({ ...filters, search: e.target.value })}
            />
          </div>
          <select
            className="form-input" style={{ width: "auto" }}
            value={filters.status}
            onChange={e => setFilters({ ...filters, status: e.target.value })}
          >
            <option value="">全部状态</option>
            <option value="pending">待处理</option>
            <option value="generated">已生成</option>
            <option value="submitted">已提交</option>
            <option value="closed">已结案</option>
          </select>
          <input
            className="form-input" type="date" style={{ width: "auto" }}
            value={filters.hearing_from}
            onChange={e => setFilters({ ...filters, hearing_from: e.target.value })}
            title="开庭日期起"
          />
          <span className="text-muted text-sm">至</span>
          <input
            className="form-input" type="date" style={{ width: "auto" }}
            value={filters.hearing_to}
            onChange={e => setFilters({ ...filters, hearing_to: e.target.value })}
            title="开庭日期止"
          />
          {hasFilters && (
            <button
              className="btn" style={{ padding: "6px 12px" }}
              onClick={() => setFilters({ search: "", status: "", hearing_from: "", hearing_to: "" })}
            >
              <X size={12} /> 清除
            </button>
          )}
          <button
            className="btn" style={{ padding: "6px 12px" }}
            disabled={exporting}
            onClick={() => {
              setExporting(true);
              caseApi.exportCsv(activeFilters)
                .catch(() => alert("导出失败"))
                .finally(() => setExporting(false));
            }}
            title="导出当前筛选结果为 CSV（Excel 可直接打开）"
          >
            <Download size={12} /> {exporting ? "导出中..." : "导出 CSV"}
          </button>
        </div>

        {isLoading ? <div className="empty">加载中...</div>
          : cases.length === 0 ? <div className="empty"><div className="empty-icon">📋</div>暂无案件</div>
          : (
            <table className="table">
              <thead><tr><th>案号</th><th>公司</th><th>代理人</th><th>法院</th><th>案由</th><th>开庭日期</th><th>操作</th></tr></thead>
              <tbody>
                {cases.map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.case_number}</strong><br/><span className="text-muted text-sm">{c.our_role}</span></td>
                    <td>{companies.find(co => co.id === c.company_id)?.name || <span className="text-muted">—</span>}</td>
                    <td>{agents.find(a => a.id === c.agent_id)?.name || <span className="text-muted">—</span>}</td>
                    <td>{c.court || "—"}</td>
                    <td>{c.cause ? `${c.cause}纠纷` : "—"}</td>
                    <td>{c.hearing_date || "—"}</td>
                    <td style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
                      <button
                        className="btn" style={{ padding: "4px 10px", fontSize: 12 }}
                        onClick={() => setDetailCase(c)}
                        title="查看案件详情与生成记录"
                      >
                        <Eye size={12} /> 查看
                      </button>
                      <button
                        className="btn btn-outline" style={{ padding: "4px 10px", fontSize: 12 }}
                        onClick={() => {
                          setEditingCase(c);
                          setForm({
                            case_number: c.case_number,
                            court: c.court || "",
                            cause: c.cause || "",
                            hearing_date: c.hearing_date || "",
                            opposing_party: c.opposing_party || "",
                            our_role: c.our_role || "原告",
                            company_id: c.company_id ?? null,
                            agent_id: c.agent_id ?? null,
                          });
                        }}
                        title="编辑案件信息"
                      >
                        <Edit2 size={12} /> 编辑
                      </button>
                      {!hasData && (
                        <span className="text-muted text-sm">请先添加公司/代理人</span>
                      )}
                      {hasData && !c.company_id && (
                        <span className="text-muted text-sm">请绑定公司</span>
                      )}
                      {hasData && !c.agent_id && (
                        <span className="text-muted text-sm">请绑定代理人</span>
                      )}
                      {hasData && c.company_id && c.agent_id && (
                        <button
                          className="btn btn-primary" style={{ padding: "4px 10px", fontSize: 12 }}
                          disabled={generating !== null}
                          onClick={() => setConfirm({ type: "generate", caseId: c.id })}
                        >
                          <Zap size={12} /> {generating === c.id ? "生成中..." : "生成"}
                        </button>
                      )}
                      <button
                        className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }}
                        onClick={() => setConfirm({ type: "delete", caseId: c.id })}
                        title="删除案件"
                      >
                        <Trash2 size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </div>
    </div>
  );
}
