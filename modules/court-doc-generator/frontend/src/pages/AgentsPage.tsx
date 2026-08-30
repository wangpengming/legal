import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Eye, CheckCircle } from "lucide-react";
import { agentApi, companyApi } from "../lib/api";
import ConfirmDialog from "../components/ConfirmDialog";

export default function AgentsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: agents = [], isLoading } = useQuery({ queryKey: ["agents"], queryFn: agentApi.list });
  const { data: companies = [] } = useQuery({ queryKey: ["companies"], queryFn: companyApi.list });

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", position: "", phone: "", id_card: "", gender: "", company_id: null as number | null, is_default: false });
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const create = useMutation({
    mutationFn: (body: typeof form) => agentApi.create({ ...body, is_default: body.is_default ? 1 : 0, id_card: body.id_card, gender: body.gender }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      setShowForm(false);
      setForm({ name: "", position: "", phone: "", id_card: "", gender: "", company_id: null, is_default: false });
      setError("");
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "保存失败");
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => agentApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
    onError: (err: unknown) => alert(err instanceof Error ? err.message : "删除失败"),
  });

  return (
    <div>
      {confirmDelete !== null && (
        <ConfirmDialog
          title="删除代理人"
          message={`确定删除代理人「${agents.find(a => a.id === confirmDelete)?.name || ""}」吗？\n删除后不可恢复。`}
          confirmText="删除"
          danger={true}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => { remove.mutate(confirmDelete); setConfirmDelete(null); }}
        />
      )}

      <div className="page-header">
        <h1 className="page-title">👤 代理人管理</h1>
        <div className="page-actions">
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            <Plus size={14} /> 添加代理人
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>新增代理人</h3>
          {error && <div className="alert alert-error">{error}</div>}
          <form onSubmit={e => {
            e.preventDefault();
            if (form.name.trim()) {
              setError("");
              create.mutate(form);
            } else {
              setError("请填写代理人姓名");
            }
          }}>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">姓名 *</label>
                <input className="form-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required placeholder="代理人姓名" />
              </div>
              <div className="form-group">
                <label className="form-label">职务</label>
                <input className="form-input" value={form.position} onChange={e => setForm({ ...form, position: e.target.value })} placeholder="如：法务" />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">电话</label>
                <input className="form-input" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="手机号" />
              </div>
              <div className="form-group">
                <label className="form-label">所属公司</label>
                <select className="form-input" value={form.company_id ?? ""} onChange={e => setForm({ ...form, company_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">请选择</option>
                  {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <input type="checkbox" checked={form.is_default} onChange={e => setForm({ ...form, is_default: e.target.checked })} />
              设为默认代理人
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                {create.isPending ? "保存中..." : "保存"}
              </button>
              <button type="button" className="btn" onClick={() => { setShowForm(false); setError(""); }}>取消</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        {isLoading ? <div className="empty">加载中...</div>
          : agents.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">👤</div>
              <div>暂无代理人，点击上方添加</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>姓名</th>
                  <th>职务</th>
                  <th>电话</th>
                  <th>所属公司</th>
                  <th>文件</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {agents.map(a => (
                  <tr key={a.id}>
                    <td>
                      <strong style={{ cursor: "pointer", color: "#007bff" }}
                        onClick={() => navigate(`/agents/${a.id}`)}>
                        {a.name || "—"}
                      </strong>
                      {a.is_default ? <span style={{ fontSize: 11, color: "#28a745", marginLeft: 4 }}>默认</span> : null}
                    </td>
                    <td>{a.position || "—"}</td>
                    <td>{a.phone || "—"}</td>
                    <td>{a.company_name || "—"}</td>
                    <td>
                      <div style={{ display: "flex", gap: 4 }}>
                        <span title="身份证" style={{
                          fontSize: 11, padding: "2px 6px", borderRadius: 4,
                          background: a.id_card ? "#d4edda" : "#fff3cd",
                          color: a.id_card ? "#155724" : "#856404",
                        }}>
                          {a.id_card ? <CheckCircle size={10} /> : null} 身份证
                        </span>
                        <span title="劳动合同" style={{
                          fontSize: 11, padding: "2px 6px", borderRadius: 4,
                          background: a.labor_contract ? "#d4edda" : "#fff3cd",
                          color: a.labor_contract ? "#155724" : "#856404",
                        }}>
                          {a.labor_contract ? <CheckCircle size={10} /> : null} 合同
                        </span>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button
                          className="btn btn-primary"
                          style={{ padding: "4px 10px", fontSize: 12 }}
                          onClick={() => navigate(`/agents/${a.id}`)}
                        >
                          <Eye size={12} /> 查看
                        </button>
                        <button
                          className="btn btn-danger"
                          style={{ padding: "4px 10px", fontSize: 12 }}
                          onClick={() => setConfirmDelete(a.id)}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  );
}
