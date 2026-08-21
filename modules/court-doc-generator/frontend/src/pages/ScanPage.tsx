import { useState, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { Camera, Upload, Copy, Check } from "lucide-react";

interface ScanResult {
  text: string;
  fields: Record<string, string | null>;
  error: string | null;
}

async function scanUpload(file: File): Promise<ScanResult> {
  const wsId = sessionStorage.getItem("_ws_id") || "";
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/v1/scan/scan", {
    method: "POST",
    headers: { "X-Workspace-Id": wsId },
    body: form,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || data.detail || "扫描失败");
  return data as ScanResult;
}

export default function ScanPage() {
  const [url, setUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [rawText, setRawText] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scanUrl = useMutation({
    mutationFn: async (url: string): Promise<ScanResult> => {
      const wsId = sessionStorage.getItem("_ws_id") || "";
      const res = await fetch("/api/v1/scan/scan-url", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Workspace-Id": wsId },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || data.detail || "扫描失败");
      return data as ScanResult;
    },
    onError: (err: unknown) => alert(err instanceof Error ? err.message : "扫描失败"),
  });

  const scanFile = useMutation({
    mutationFn: scanUpload,
    onError: (err: unknown) => alert(err instanceof Error ? err.message : "扫描失败"),
  });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setRawText(null);
    scanFile.mutate(file, {
      onSuccess: (data) => {
        setUploading(false);
        if (data.error) alert("OCR 解析失败: " + data.error);
        else if (data.text) setRawText(data.text);
      },
      onSettled: () => {
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      },
    });
  }

  function handleScan() {
    if (!url.trim()) return;
    setRawText(null);
    scanUrl.mutate(url.trim(), {
      onSuccess: (data) => {
        if (data.error) alert("OCR 解析失败: " + data.error);
        else if (data.text) setRawText(data.text);
      },
    });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleScan();
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function applyToForm(fields: Record<string, string | null>) {
    const caseInfo = {
      case_number: fields["案号"] || "",
      court: fields["法院"] || "",
      cause: fields["案由"] ? fields["案由"]?.replace("纠纷", "") : "",
      hearing_date: fields["开庭时间"] || "",
      opposing_party: fields["被告"] || "",
      our_role: "原告",
    };
    sessionStorage.setItem("_pending_case", JSON.stringify(caseInfo));
    alert("✅ 字段已暂存，请前往「案件」页面新建案件，表单将自动填充");
  }

  const result = scanFile.data || scanUrl.data;
  const fields = result?.fields || {};
  const isScanning = scanUrl.isPending || uploading;
  const hasError = scanUrl.isError || scanFile.isError;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">📷 拍照扫描</h1>
      </div>

      <div className="card">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>扫描法律文书</h3>
        <p className="text-muted text-sm mb-16">
          上传本地图片或 PDF，系统将自动 OCR 识别并抽取：案号、法院、案由、原告、被告、开庭时间等关键字段。
        </p>

        {/* 文件上传区域 */}
        <div
          style={{
            border: "2px dashed var(--border)",
            borderRadius: 8,
            padding: "24px 16px",
            textAlign: "center",
            marginBottom: 16,
            background: "var(--bg-secondary)",
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.pdf"
            style={{ display: "none" }}
            id="scan-file-input"
            onChange={handleFileChange}
          />
          <label
            htmlFor="scan-file-input"
            className="btn btn-primary"
            style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Upload size={14} />
            {uploading ? "上传中..." : "选择文件上传"}
          </label>
          <div className="text-muted text-sm" style={{ marginTop: 8 }}>
            支持 JPG、PNG、PDF，单文件不超过 20MB
          </div>
        </div>

        {/* 分割线 */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
          <span className="text-muted text-sm">或</span>
          <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
        </div>

        {/* URL 输入 */}
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input
            className="form-input"
            style={{ flex: 1 }}
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="粘贴图片 URL（支持 jpg/png）"
          />
          <button
            className="btn btn-outline"
            onClick={handleScan}
            disabled={isScanning || !url.trim()}
          >
            <Camera size={14} /> {isScanning ? "扫描中..." : "扫描 URL"}
          </button>
        </div>

        {hasError && (
          <div className="alert alert-error">
            {String((scanUrl.error || scanFile.error) as string)}
          </div>
        )}

        {result?.error && (
          <div className="alert alert-error">{result.error}</div>
        )}

        {result && !result.error && Object.keys(fields).length > 0 && (
          <div>
            <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, marginTop: 8 }}>抽取结果</h4>
            <table className="table">
              <thead>
                <tr><th>字段</th><th>值</th><th>操作</th></tr>
              </thead>
              <tbody>
                {Object.entries(fields).map(([k, v]) => (
                  <tr key={k}>
                    <td style={{ fontWeight: 500 }}>{k}</td>
                    <td>{v || <span className="text-muted">未识别</span>}</td>
                    <td>
                      {v && (
                        <button className="btn" style={{ padding: "3px 8px", fontSize: 11 }} onClick={() => copyToClipboard(v)}>
                          {copied ? <Check size={11} /> : <Copy size={11} />} 复制
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 12 }}>
              <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={() => applyToForm(fields)}>
                应用到新建案件表单
              </button>
            </div>
          </div>
        )}

        {rawText && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <h4 style={{ fontSize: 13, fontWeight: 600 }}>OCR 原始文本</h4>
              <button className="btn" style={{ padding: "3px 8px", fontSize: 11 }} onClick={() => copyToClipboard(rawText)}>
                {copied ? <Check size={11} /> : <Copy size={11} />} 复制
              </button>
            </div>
            <pre style={{
              background: "#f8f8f8",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: 12,
              fontSize: 12,
              maxHeight: 300,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
            }}>
              {rawText}
            </pre>
          </div>
        )}

        {!result && !isScanning && !hasError && (
          <div className="empty" style={{ padding: 24 }}>
            <div className="empty-icon">📷</div>
            <div>上传文件或粘贴 URL 开始扫描</div>
          </div>
        )}
      </div>
    </div>
  );
}
