import { useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Save, X, Upload, FileText, CheckCircle2, AlertCircle, Eye, Info } from "lucide-react";
import { agentApi, companyApi, Agent } from "../lib/api";
import PdfPreviewModal from "../components/PdfPreviewModal";

// 文件配置
const FILE_CONFIGS = [
  { key: "id_card", label: "身份证", desc: "代理人身份证正反面", format: "PDF 格式，建议合并为一页", param: "id_card" },
  { key: "labor_contract", label: "劳动合同", desc: "与公司签订的劳动合同", format: "PDF 格式，盖章原件", param: "labor_contract" },
] as const;

type FileKey = typeof FILE_CONFIGS[number]["key"];

interface FileUploadState {
  uploading: boolean;
  error: string;
  success: string;
}

// 查看模式的文件卡片
function FileViewCard({ label, desc, path, onView }: { label: string; desc: string; path: string; onView: () => void }) {
  const hasFile = !!path;
  return (
    <div style={{
      background: "#f8f9fa",
      padding: 16,
      borderRadius: 8,
      border: hasFile ? "2px solid #28a745" : "1px solid #dee2e6",
      height: "100%",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        {hasFile ? (
          <CheckCircle2 size={16} style={{ color: "#28a745" }} />
        ) : (
          <FileText size={16} style={{ color: "#6c757d" }} />
        )}
        <span style={{ fontWeight: 600, fontSize: 14 }}>{label}</span>
      </div>
      <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 12 }}>{desc}</div>
      {hasFile ? (
        <button className="btn btn-primary" style={{ width: "100%", fontSize: 12 }} onClick={onView}>
          <Eye size={14} /> 查看文件
        </button>
      ) : (
        <div style={{ fontSize: 12, color: "#ffc107", textAlign: "center" }}>未上传</div>
      )}
    </div>
  );
}

// 编辑模式的上传卡片
function FileUploadCard({ config, isEditing, fileState, onUpload }: {
  config: typeof FILE_CONFIGS[number];
  isEditing: boolean;
  fileState: FileUploadState;
  onUpload: (file: File) => void;
}) {
  const [showTip, setShowTip] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!isEditing) return null;

  return (
    <div style={{
      background: "#f8f9fa",
      padding: 16,
      borderRadius: 8,
      border: "1px solid #dee2e6",
      height: "100%",
      position: "relative",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <FileText size={16} style={{ color: "#6c757d" }} />
        <span style={{ fontWeight: 600, fontSize: 14 }}>{config.label}</span>
        <button
          className="btn"
          style={{ padding: "2px 6px", marginLeft: "auto" }}
          onClick={() => setShowTip(!showTip)}
          title="查看说明"
        >
          <Info size={14} style={{ color: "#17a2b7" }} />
        </button>
      </div>

      {showTip && (
        <div style={{
          background: "#e7f5ff",
          border: "1px solid #74c0fc",
          borderRadius: 6,
          padding: 10,
          marginBottom: 12,
          fontSize: 12,
        }}>
          <div style={{ fontWeight: 500, marginBottom: 4, color: "#1864ab" }}>{config.desc}</div>
          <div style={{ color: "#495057" }}>格式：{config.format}</div>
        </div>
      )}

      <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 12 }}>{config.desc}</div>

      {fileState.error && (
        <div style={{ fontSize: 12, color: "#dc3545", marginBottom: 8 }}>
          <AlertCircle size={12} /> {fileState.error}
        </div>
      )}
      {fileState.success && (
        <div style={{ fontSize: 12, color: "#28a745", marginBottom: 8 }}>
          <CheckCircle2 size={12} /> {fileState.success}
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        style={{ display: "none" }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
        }}
      />
      <button
        className="btn btn-primary"
        style={{ width: "100%", fontSize: 12 }}
        disabled={fileState.uploading}
        onClick={() => inputRef.current?.click()}
      >
        <Upload size={14} />
        {fileState.uploading ? "上传中..." : "上传文件"}
      </button>
    </div>
  );
}

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const agentId = parseInt(id || "0");

  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState<Partial<Agent>>({});
  const [fileStates, setFileStates] = useState<Record<string, FileUploadState>>({});
  const [previewFile, setPreviewFile] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string>("文件预览");

  const { data: agents = [], isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: agentApi.list,
  });
  const { data: companies = [] } = useQuery({
    queryKey: ["companies"],
    queryFn: companyApi.list,
  });

  const agent = agents.find(a => a.id === agentId);

  const saveMutation = useMutation({
    mutationFn: (data: Partial<Agent>) => agentApi.create({
      name: data.name || "",
      position: data.position || "",
      phone: data.phone || "",
      company_id: data.company_id || null,
      is_default: data.is_default ? 1 : 0,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      setIsEditing(false);
    },
  });

  async function handleFileUpload(fileKey: FileKey, file: File) {
    const stateKey = `${fileKey}`;
    setFileStates(prev => ({
      ...prev,
      [stateKey]: { uploading: true, error: "", success: "" },
    }));

    try {
      const formData = new FormData();
      const config = FILE_CONFIGS.find(f => f.key === fileKey);
      formData.append(config?.param || fileKey, file);

      const wsId = sessionStorage.getItem("_ws_id") || "";
      const res = await fetch(`/api/v1/agents/${agentId}/upload`, {
        method: "PUT",
        headers: { "X-Workspace-Id": wsId },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "上传失败");
      }

      setFileStates(prev => ({
        ...prev,
        [stateKey]: { uploading: false, error: "", success: "上传成功" },
      }));
      qc.invalidateQueries({ queryKey: ["agents"] });

      setTimeout(() => {
        setFileStates(prev => ({
          ...prev,
          [stateKey]: { uploading: false, error: "", success: "" },
        }));
      }, 3000);
    } catch (err) {
      setFileStates(prev => ({
        ...prev,
        [stateKey]: {
          uploading: false,
          error: err instanceof Error ? err.message : "上传失败",
          success: "",
        },
      }));
    }
  }

  function getFileState(fileKey: string): FileUploadState {
    return fileStates[fileKey] || { uploading: false, error: "", success: "" };
  }

  function getFilePath(fileKey: string): string {
    if (!agent) return "";
    return (agent as any)[fileKey] || "";
  }

  function startEditing() {
    if (agent) {
      setForm({ ...agent });
      setIsEditing(true);
    }
  }

  function cancelEditing() {
    setIsEditing(false);
    setForm({});
  }

  // 预览 PDF 文件（用 modal）
  function openFile(path: string) {
    if (path) {
      // 转换路径为相对路径（统一格式：workspaces/...）
      let rel: string;
      if (path.includes("/workspaces/")) {
        // 绝对路径：提取 workspaces/... 部分
        rel = path.replace(/.*\/workspaces\//, "workspaces/");
      } else if (path.startsWith("data/workspaces/")) {
        // 相对路径（带 data/ 前缀）：去掉 data/ 前缀
        rel = path.replace(/^data\//, "");
      } else {
        // 其他情况直接使用
        rel = path;
      }
      setPreviewTitle("文件预览");
      setPreviewFile(rel);
    }
  }

  if (isLoading) {
    return <div className="page-container"><div className="empty">加载中...</div></div>;
  }

  if (!agent) {
    return (
      <div className="page-container">
        <div className="card">
          <div className="empty">代理人不存在</div>
          <button className="btn" onClick={() => navigate("/agents")}>
            <ArrowLeft size={14} /> 返回列表
          </button>
        </div>
      </div>
    );
  }

  const companyName = companies.find(c => c.id === agent.company_id)?.name;

  return (
    <div className="page-container">
      {/* 顶部导航 */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <button className="btn" onClick={() => navigate("/agents")}>
          <ArrowLeft size={14} /> 返回
        </button>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>👤 {agent.name}</h1>
        <span style={{ fontSize: 13, color: "#6c757d" }}>{agent.position || "代理人"}</span>
        {!isEditing ? (
          <button className="btn btn-primary" onClick={startEditing}>
            <Edit2 size={14} /> 编辑
          </button>
        ) : (
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={cancelEditing}>
              <X size={14} /> 取消
            </button>
          </div>
        )}
      </div>

      {/* 基本信息卡片 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>📋 基本信息</h3>

        {isEditing ? (
          <>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">姓名 *</label>
                <input
                  className="form-input"
                  value={form.name || ""}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">职务</label>
                <input
                  className="form-input"
                  value={form.position || ""}
                  onChange={e => setForm({ ...form, position: e.target.value })}
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">电话</label>
                <input
                  className="form-input"
                  value={form.phone || ""}
                  onChange={e => setForm({ ...form, phone: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">所属公司</label>
                <select
                  className="form-input"
                  value={form.company_id ?? ""}
                  onChange={e => setForm({ ...form, company_id: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">请选择</option>
                  {companies.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
              <input
                type="checkbox"
                checked={!!form.is_default}
                onChange={e => setForm({ ...form, is_default: e.target.checked ? 1 : 0 })}
              />
              设为默认代理人
            </label>
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button
                className="btn btn-primary"
                disabled={saveMutation.isPending || !form.name}
                onClick={() => saveMutation.mutate(form)}
              >
                <Save size={14} /> {saveMutation.isPending ? "保存中..." : "保存"}
              </button>
            </div>
          </>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>姓名</div>
              <div style={{ fontWeight: 500 }}>{agent.name}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>职务</div>
              <div>{agent.position || "—"}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>电话</div>
              <div>{agent.phone || "—"}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>所属公司</div>
              <div>{companyName || "—"}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>默认代理人</div>
              <div>{agent.is_default ? "✅ 是" : "否"}</div>
            </div>
          </div>
        )}
      </div>

      {/* 文件区域卡片 */}
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>📎 代理人文件</h3>
          {!isEditing && (
            <span style={{ fontSize: 12, color: "#6c757d" }}>（点击"编辑"后上传文件）</span>
          )}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
          {FILE_CONFIGS.map(fc => {
            const path = getFilePath(fc.key);
            const state = getFileState(fc.key);

            return isEditing ? (
              <FileUploadCard
                key={fc.key}
                config={fc}
                isEditing={isEditing}
                fileState={state}
                onUpload={(file) => handleFileUpload(fc.key, file)}
              />
            ) : (
              <FileViewCard
                key={fc.key}
                label={fc.label}
                desc={fc.desc}
                path={path}
                onView={() => openFile(path)}
              />
            );
          })}
        </div>
      </div>

      {/* PDF 预览 Modal */}
      {previewFile && (
        <PdfPreviewModal
          filePath={previewFile}
          title={previewTitle}
          onClose={() => setPreviewFile(null)}
        />
      )}
    </div>
  );
}
