import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import { X } from "lucide-react";

// Set worker source
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

interface PdfPreviewModalProps {
  filePath: string;   // relative path from workspace root, e.g. "outputs/xxx/00_合并出庭手续.pdf"
  title?: string;
  onClose: () => void;
}

function buildFileUrl(relPath: string): string {
  const wsId = sessionStorage.getItem("_ws_id") || "";
  // 支持模板路径格式：templates/<name>
  if (relPath.startsWith("templates/")) {
    return `/api/v1/files/${relPath}?ws=${wsId}&t=${Date.now()}`;
  }
  // 普通文件路径：用 hex 编码
  const hex = Array.from(new TextEncoder().encode(relPath))
    .map(b => b.toString(16).padStart(2, "0")).join("");
  return `/api/v1/files/~hex/${hex}?ws=${wsId}`;
}

// 检查是否是扫描件（需要用 iframe 渲染）
async function isImagePdf(url: string): Promise<boolean> {
  try {
    const res = await fetch(url);
    const buffer = await res.arrayBuffer();
    const header = new TextDecoder().decode(buffer.slice(0, 1000));
    // 检查是否包含 CCITTFaxDecode（扫描件特征）
    return header.includes("CCITTFaxDecode") || header.includes("/CCF");
  } catch {
    return false;
  }
}

export default function PdfPreviewModal({ filePath, title, onClose }: PdfPreviewModalProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [useIframe, setUseIframe] = useState(false);

  useEffect(() => {
    if (!filePath) return;
    setLoading(true);
    setError(null);
    setPage(1);
    setNumPages(0);
    const url = buildFileUrl(filePath);
    
    // 检查是否是扫描件（CCITTFaxDecode 格式），用 iframe 渲染
    isImagePdf(url).then((isImg) => {
      if (isImg) {
        setUseIframe(true);
        setLoading(false);
        return;
      }
      setUseIframe(false);
      
      pdfjsLib.getDocument(url).promise
        .then((pdf) => {
          setNumPages(pdf.numPages);
          // 使用 requestAnimationFrame 延迟确保 canvas 已挂载到 DOM
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              renderPage(pdf, 1);
            });
          });
          setLoading(false);
        })
        .catch((err) => {
          // 渲染失败，尝试用 iframe
          setUseIframe(true);
          setLoading(false);
        });
    });
  }, [filePath]);

  function renderPage(pdf: pdfjsLib.PDFDocumentProxy, pageNum: number) {
    if (!canvasRef.current) return;
    pdf.getPage(pageNum).then((p) => {
      const canvas = canvasRef.current!;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const unscaledViewport = p.getViewport({ scale: 1 });
      // 动态计算容器宽度：获取 canvas 父容器的实际宽度
      const parentWidth = canvas.parentElement?.clientWidth || 800;
      const maxWidth = Math.min(parentWidth - 16, 850); // 减去 padding
      const fitScale = maxWidth / unscaledViewport.width;
      const scale = Math.max(fitScale, 1.0) * (window.devicePixelRatio || 1);
      const viewport = p.getViewport({ scale: Math.max(fitScale, 1.0) });
      canvas.width = viewport.width * (window.devicePixelRatio || 1);
      canvas.height = viewport.height * (window.devicePixelRatio || 1);
      canvas.style.width = viewport.width + "px";
      canvas.style.height = viewport.height + "px";
      canvas.style.maxWidth = "100%";
      canvas.style.maxHeight = "75vh";
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
      p.render({ canvasContext: ctx, viewport }).promise.catch(() => {});
    });
  }

  function goPage(pdf: pdfjsLib.PDFDocumentProxy, delta: number) {
    const next = Math.max(1, Math.min(numPages, page + delta));
    setPage(next);
    renderPage(pdf, next);
  }

  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-panel" style={{ maxWidth: 900, width: "95vw", height: "90vh", display: "flex", flexDirection: "column" }}>
        <div className="modal-header">
          <span style={{ fontWeight: 600 }}>{title || "PDF 预览"}</span>
          <button className="btn" style={{ padding: "4px 8px" }} onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <div className="modal-body" style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: 12, overflow: "auto" }}>
          {loading && <div className="empty">加载中...</div>}
          {error && <div className="alert alert-danger">{error}</div>}
          {!loading && !error && useIframe && (
            <iframe
              src={buildFileUrl(filePath)}
              style={{ flex: 1, width: "100%", border: "1px solid var(--border)", borderRadius: 4 }}
              title="PDF Preview"
            />
          )}
          {!loading && !error && !useIframe && (
            <>
              <div style={{ flex: 1, overflow: "auto", display: "flex", justifyContent: "center", padding: 8 }}>
                <canvas ref={canvasRef} style={{ border: "1px solid var(--border)", maxWidth: "100%", maxHeight: "100%", height: "auto" }} />
              </div>
              {numPages > 1 && (
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
                  <button className="btn" onClick={() => { pdfjsLib.getDocument(buildFileUrl(filePath)).promise.then(p => goPage(p, -1)); }} disabled={page <= 1}>‹ 上一页</button>
                  <span style={{ fontSize: 13 }}>{page} / {numPages}</span>
                  <button className="btn" onClick={() => { pdfjsLib.getDocument(buildFileUrl(filePath)).promise.then(p => goPage(p, 1)); }} disabled={page >= numPages}>下一页 ›</button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
