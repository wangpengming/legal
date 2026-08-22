import { useRef, useState } from "react";
import { Upload, X, Camera, CheckCircle2 } from "lucide-react";
import { scanUpload, scanImageUrl, mapFieldsToCaseForm, ScanResult, ScanCaseMapping } from "../lib/scan";

interface ScanModalProps {
  open: boolean;
  onClose: () => void;
  onApply: (mapping: ScanCaseMapping) => void;
}

const FIELD_LABELS: Record<string, string> = {
  "案号": "案号",
  "法院": "法院",
  "案由": "案由",
  "原告": "原告",
  "被告": "被告",
  "开庭时间": "开庭时间",
  "立案日期": "立案日期",
  "标的金额": "标的金额",
};

export default function ScanModal({ open, onClose, onApply }: ScanModalProps) {
  const [url, setUrl] = useState("");
  const [rawText, setRawText] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [scanningUrl, setScanningUrl] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);
    setRawText(null);
    try {
      const data = await scanUpload(file);
      if (data.error) setError("OCR 解析失败: " + data.error);
      else if (data.text) {
        setResult(data);
        setRawText(data.text);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "扫描失败");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleScanUrl() {
    if (!url.trim()) return;
    setScanningUrl(true);
    setError(null);
    setResult(null);
    setRawText(null);
    try {
      const data = await scanImageUrl(url.trim());
      if (data.error) setError("OCR 解析失败: " + data.error);
      else if (data.text) {
        setResult(data);
        setRawText(data.text);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "扫描失败");
    } finally {
      setScanningUrl(false);
    }
  }

  const fields = result?.fields || {};
  const recognizedFields = Object.entries(fields).filter(([k, v]) => v);

  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-panel" style={{ maxWidth: 680, width: "95vw", maxHeight: "88vh", display: "flex", flexDirection: "column" }}>
        <div className="modal-header">
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>📷 扫描起诉状</h3>
          <button className="btn" style={{ padding: "4px 8px" }} onClick={onClose} aria-label="关闭">
            <X size={16} />
          </button>
        </div>

        <div className="modal-body" style={{ flex: 1, overflowY: "auto", padding: 16 }}>
          <p className="text-muted text-sm" style={{ marginBottom: 16 }}>
            上传起诉状照片 / 扫描件，系统自动 OCR 识别案号、法院、案由、当事人、开庭时间等，一键填入新建案件表单。
          </p>

          {/* 文件上传 */}
          <div style={{ border: "2px dashed var(--border)", borderRadius: 8, padding: "24px 16px", textAlign: "center", marginBottom: 16, background: "var(--bg-secondary)" }}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.pdf"
              style={{ display: "none" }}
              id="scan-file-input"
              onChange={handleFileChange}
            />
            <label htmlFor="scan-file-input" className="btn btn-primary" style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Upload size={14} />
              {uploading ? "识别中..." : "选择文件上传"}
            </label>
            <div className="text-muted text-sm" style={{ marginTop: 8 }}>支持 JPG、PNG、PDF，单文件不超过 20MB</div>
          </div>

          {/* URL 方式 */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              className="form-input"
              style={{ flex: 1 }}
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleScanUrl(); }}
              placeholder="或粘贴图片 URL（支持 jpg/png）"
            />
            <button className="btn btn-outline" onClick={handleScanUrl} disabled={scanningUrl || !url.trim()}>
              <Camera size={14} /> {scanningUrl ? "识别中..." : "识别 URL"}
            </button>
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          {/* 识别结果 */}
          {result && recognizedFields.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>识别结果</h4>
              <table className="table">
                <thead>
                  <tr><th>字段</th><th>值</th></tr>
                </thead>
                <tbody>
                  {recognizedFields.map(([k, v]) => (
                    <tr key={k}>
                      <td style={{ fontWeight: 500 }}>{FIELD_LABELS[k] || k}</td>
                      <td>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button
                className="btn btn-primary"
                style={{ marginTop: 12, fontSize: 13 }}
                onClick={() => onApply(mapFieldsToCaseForm(fields))}
              >
                <CheckCircle2 size={14} /> 填入案件表单
              </button>
            </div>
          )}

          {rawText && (
            <details style={{ marginTop: 16 }}>
              <summary className="text-muted text-sm" style={{ cursor: "pointer" }}>查看 OCR 原始文本</summary>
              <pre style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: 12,
                fontSize: 12,
                maxHeight: 220,
                overflow: "auto",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                marginTop: 8,
              }}>
                {rawText}
              </pre>
            </details>
          )}

          {!result && !uploading && !scanningUrl && !error && (
            <div className="empty" style={{ padding: 24 }}>
              <div className="empty-icon">📷</div>
              <div>上传起诉状文件或粘贴 URL 开始识别</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}