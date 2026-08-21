import { useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Save, X, Upload, FileText, CheckCircle2, AlertCircle, Eye, Info } from "lucide-react";
import { companyApi, Company, API_BASE } from "../lib/api";
import PdfPreviewModal from "../components/PdfPreviewModal";

// 文件配置
// fileType: "pdf" = 静态PDF文件, "template" = 动态模板（生成时填充）
const FILE_CONFIGS = [
  { key: "business_license", label: "营业执照", desc: "企业营业执照复印件", fileType: "pdf" as const, param: "business_license" },
  { key: "legal_rep_id_card", label: "法人身份证", desc: "法定代表人身份证正反面", fileType: "pdf" as const, param: "legal_rep_id_card" },
  { key: "legal_rep_cert", label: "法定代表人证明", desc: "法定代表人证明文件", fileType: "pdf" as const, param: "legal_rep_cert" },
  { key: "power_of_attorney", label: "授权委托书", desc: "授权委托书模板", fileType: "template" as const, param: "power_of_attorney" },
  { key: "recommendation", label: "推荐信", desc: "推荐信模板", fileType: "template" as const, param: "recommendation" },
] as const;

type FileKey = typeof FILE_CONFIGS[number]["key"];

interface FileUploadState {
  uploading: boolean;
  error: string;
  success: string;
}

// 查看模式的文件卡片
// fileType: "pdf" = 可查看的PDF文件, "template" = 动态模板
function FileViewCard({ label, desc, path, fileType, onView, onViewTemplate }: { 
  label: string; 
  desc: string; 
  path: string; 
  fileType?: "pdf" | "template"; 
  onView?: () => void;
  onViewTemplate?: () => void;
}) {
  const hasPdf = !!path;
  return (
    <div style={{
      background: "#f8f9fa",
      padding: 16,
      borderRadius: 8,
      border: hasPdf ? "2px solid #28a745" : fileType === "template" ? "2px solid #17a2b8" : "1px solid #dee2e6",
      height: "100%",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        {hasPdf ? (
          <CheckCircle2 size={16} style={{ color: "#28a745" }} />
        ) : fileType === "template" ? (
          <FileText size={16} style={{ color: "#17a2b8" }} />
        ) : (
          <FileText size={16} style={{ color: "#6c757d" }} />
        )}
        <span style={{ fontWeight: 600, fontSize: 14 }}>{label}</span>
      </div>
      <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 12 }}>{desc}</div>
      {hasPdf ? (
        <button className="btn btn-primary" style={{ width: "100%", fontSize: 12 }} onClick={onView}>
          <Eye size={14} /> 查看文件
        </button>
      ) : fileType === "template" ? (
        <button className="btn btn-outline" style={{ width: "100%", fontSize: 12 }} onClick={onViewTemplate}>
          <Eye size={14} /> 查看模板
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
          <div style={{ color: "#495057" }}>支持格式：{config.fileType === "pdf" ? "PDF" : "DOCX"}</div>
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

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const companyId = parseInt(id || "0");

  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState<Partial<Company>>({});
  const [fileStates, setFileStates] = useState<Record<string, FileUploadState>>({});
  const [previewFile, setPreviewFile] = useState<string | null>(null);  // 预览文件路径
  const [previewTitle, setPreviewTitle] = useState<string>("文件预览"); // 预览标题

  const { data: companies = [], isLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: companyApi.list,
  });

  const company = companies.find(c => c.id === companyId);

  const saveMutation = useMutation({
    mutationFn: (data: Partial<Company>) => companyApi.create({
      name: data.name || "",
      credit_code: data.credit_code || "",
      legal_rep_name: data.legal_rep_name || "",
      legal_rep_position: data.legal_rep_position || "",
      legal_rep_id_card: data.legal_rep_id_card || "",
      address: data.address || "",
      phone: data.phone || "",
      business_license_path: data.business_license_path || "",
      legal_rep_id_card_path: data.legal_rep_id_card_path || "",
      legal_rep_cert_path: data.legal_rep_cert_path || "",
      power_of_attorney_path: data.power_of_attorney_path || "",
      recommendation_path: data.recommendation_path || "",
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
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
      await companyApi.uploadFiles(companyId, formData);

      setFileStates(prev => ({
        ...prev,
        [stateKey]: { uploading: false, error: "", success: "上传成功" },
      }));
      qc.invalidateQueries({ queryKey: ["companies"] });

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

  function hasFile(fileKey: FileKey): boolean {
    if (!company) return false;
    const pathKey = `${fileKey}_path`;
    return !!(company as any)[pathKey];
  }

  function getFilePath(fileKey: FileKey): string {
    if (!company) return "";
    const pathKey = `${fileKey}_path`;
    return (company as any)[pathKey] || "";
  }

  function startEditing() {
    if (company) {
      setForm({ ...company });
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

  // 预览模板文件（用 modal）
  function openTemplate(templateName: string) {
    const label = FILE_CONFIGS.find(f => f.key === templateName)?.label || templateName;
    setPreviewTitle(`${label} 模板`);
    // 模板预览用特殊路径格式：templates/<template_name>
    setPreviewFile(`templates/${templateName}`);
  }

  if (isLoading) {
    return <div className="page-container"><div className="empty">加载中...</div></div>;
  }

  if (!company) {
    return (
      <div className="page-container">
        <div className="card">
          <div className="empty">公司不存在</div>
          <button className="btn" onClick={() => navigate("/companies")}>
            <ArrowLeft size={14} /> 返回列表
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* 顶部导航 */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <button className="btn" onClick={() => navigate("/companies")}>
          <ArrowLeft size={14} /> 返回
        </button>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>🏢 {company.name}</h1>
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
                <label className="form-label">公司名称 *</label>
                <input
                  className="form-input"
                  value={form.name || ""}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">统一社会信用代码</label>
                <input
                  className="form-input"
                  value={form.credit_code || ""}
                  onChange={e => setForm({ ...form, credit_code: e.target.value })}
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">法定代表人</label>
                <input
                  className="form-input"
                  value={form.legal_rep_name || ""}
                  onChange={e => setForm({ ...form, legal_rep_name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">职务</label>
                <input
                  className="form-input"
                  value={form.legal_rep_position || ""}
                  onChange={e => setForm({ ...form, legal_rep_position: e.target.value })}
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">地址</label>
                <input
                  className="form-input"
                  value={form.address || ""}
                  onChange={e => setForm({ ...form, address: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">电话</label>
                <input
                  className="form-input"
                  value={form.phone || ""}
                  onChange={e => setForm({ ...form, phone: e.target.value })}
                />
              </div>
            </div>
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
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>公司名称</div>
              <div style={{ fontWeight: 500 }}>{company.name}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>统一社会信用代码</div>
              <div>{company.credit_code || "—"}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>法定代表人</div>
              <div>{company.legal_rep_name || "—"}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>职务</div>
              <div>{company.legal_rep_position || "—"}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>地址</div>
              <div>{company.address || "—"}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "#6c757d", marginBottom: 4 }}>电话</div>
              <div>{company.phone || "—"}</div>
            </div>
          </div>
        )}
      </div>

      {/* 文件区域卡片 */}
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>📎 公司文件</h3>
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
                fileType={fc.fileType}
                onView={path ? () => openFile(path) : undefined}
                onViewTemplate={fc.fileType === "template" ? () => openTemplate(fc.key) : undefined}
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
