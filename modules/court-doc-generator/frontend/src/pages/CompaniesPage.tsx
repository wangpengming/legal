import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Eye, FileText, CheckCircle2 } from "lucide-react";
import { companyApi, Company } from "../lib/api";
import ConfirmDialog from "../components/ConfirmDialog";

// 文件配置（用于显示状态）
const FILE_CONFIGS = [
  { key: "business_license", label: "营业执照" },
  { key: "legal_rep_id_card", label: "法人身份证" },
  { key: "legal_rep_cert", label: "法定代表人证明" },
  { key: "power_of_attorney", label: "授权委托书" },
  { key: "recommendation", label: "推荐信" },
] as const;

type FileKey = typeof FILE_CONFIGS[number]["key"];

export default function CompaniesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: companies = [], isLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: companyApi.list,
  });

  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [form, setForm] = useState<Omit<Company, "id">>({
    name: "", credit_code: "", legal_rep_name: "",
    legal_rep_position: "", legal_rep_id_card: "", address: "", phone: "",
    business_license_path: "", legal_rep_id_card_path: "", legal_rep_cert_path: "",
    power_of_attorney_path: "", recommendation_path: "",
  });

  const create = useMutation({
    mutationFn: (body: Omit<Company, "id">) => companyApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      setShowForm(false);
      resetForm();
      setError("");
    },
    onError: (err: unknown) => { setError(err instanceof Error ? err.message : "保存失败"); },
  });

  const remove = useMutation({
    mutationFn: (id: number) => companyApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
    onError: (err: unknown) => alert(err instanceof Error ? err.message : "删除失败"),
  });

  function resetForm() {
    setForm({
      name: "", credit_code: "", legal_rep_name: "", legal_rep_position: "",
      legal_rep_id_card: "", address: "", phone: "",
      business_license_path: "", legal_rep_id_card_path: "", legal_rep_cert_path: "",
      power_of_attorney_path: "", recommendation_path: "",
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setError("请填写公司名称"); return; }
    setError("");
    create.mutate(form);
  }

  function hasFile(company: Company, fileKey: FileKey): boolean {
    const pathKey = `${fileKey}_path`;
    return !!(company as any)[pathKey];
  }

  return (
    <div>
      {confirmDelete !== null && (
        <ConfirmDialog
          title="删除公司"
          message={`确定删除公司「${companies.find(c => c.id === confirmDelete)?.name || ""}」吗？\n删除后不可恢复，且使用该公司的案件可能受影响。`}
          confirmText="删除"
          danger={true}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => { remove.mutate(confirmDelete); setConfirmDelete(null); }}
        />
      )}

      <div className="page-header">
        <h1 className="page-title">🏢 公司管理</h1>
        <div className="page-actions">
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            <Plus size={14} /> 添加公司
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>新增公司</h3>
          {error && <div className="alert alert-error">{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">公司名称 *</label>
                <input className="form-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required placeholder="例：北京雷石天地电子技术股份有限公司" />
              </div>
              <div className="form-group">
                <label className="form-label">统一社会信用代码</label>
                <input className="form-input" value={form.credit_code} onChange={e => setForm({ ...form, credit_code: e.target.value })} placeholder="18位代码" />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">法定代表人</label>
                <input className="form-input" value={form.legal_rep_name} onChange={e => setForm({ ...form, legal_rep_name: e.target.value })} placeholder="姓名" />
              </div>
              <div className="form-group">
                <label className="form-label">职务</label>
                <input className="form-input" value={form.legal_rep_position} onChange={e => setForm({ ...form, legal_rep_position: e.target.value })} placeholder="如：总经理" />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">地址</label>
                <input className="form-input" value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} placeholder="注册地址" />
              </div>
              <div className="form-group">
                <label className="form-label">电话</label>
                <input className="form-input" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="联系电话" />
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                {create.isPending ? "保存中..." : "保存"}
              </button>
              <button type="button" className="btn" onClick={() => { setShowForm(false); resetForm(); }}>取消</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        {isLoading ? <div className="empty">加载中...</div>
          : companies.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">🏢</div>
              <div>暂无公司，点击上方添加</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>法定代表人</th>
                  <th>职务</th>
                  <th>文件</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {companies.map(c => (
                  <tr key={c.id}>
                    <td>
                      <strong style={{ cursor: "pointer", color: "#007bff" }}
                        onClick={() => navigate(`/companies/${c.id}`)}>
                        {c.name}
                      </strong>
                    </td>
                    <td>{c.legal_rep_name || "—"}</td>
                    <td>{c.legal_rep_position || "—"}</td>
                    <td>
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {FILE_CONFIGS.map(fc => {
                          const has = hasFile(c, fc.key);
                          return (
                            <span
                              key={fc.key}
                              title={fc.label}
                              style={{
                                fontSize: 11,
                                padding: "2px 6px",
                                borderRadius: 4,
                                background: has ? "#d4edda" : "#fff3cd",
                                color: has ? "#155724" : "#856404",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 2,
                              }}
                            >
                              {has ? <CheckCircle2 size={10} /> : <FileText size={10} />}
                              {fc.label}
                            </span>
                          );
                        })}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button
                          className="btn btn-primary"
                          style={{ padding: "4px 10px", fontSize: 12 }}
                          onClick={() => navigate(`/companies/${c.id}`)}
                        >
                          <Eye size={12} /> 查看
                        </button>
                        <button
                          className="btn btn-danger"
                          style={{ padding: "4px 10px", fontSize: 12 }}
                          onClick={() => setConfirmDelete(c.id)}
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
