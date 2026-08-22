import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import { Printer, X } from "lucide-react";

// Set worker source
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

interface PdfPreviewModalProps {
  filePath: string;
  title?: string;
  onClose: () => void;
}

function buildFileUrl(relPath: string): string {
  const wsId = sessionStorage.getItem("_ws_id") || "";
  if (relPath.startsWith("templates/")) {
    return `/api/v1/files/${relPath}?ws=${wsId}&t=${Date.now()}`;
  }
  const hex = Array.from(new TextEncoder().encode(relPath))
    .map(b => b.toString(16).padStart(2, "0")).join("");
  // 生成产物可能变化，带时间戳参数避免浏览器缓存旧版本（与 templates/ 分支一致）
  return `/api/v1/files/~hex/${hex}?ws=${wsId}&t=${Date.now()}`;
}

async function isImagePdf(url: string): Promise<boolean> {
  try {
    const res = await fetch(url);
    const buffer = await res.arrayBuffer();
    const header = new TextDecoder().decode(buffer.slice(0, 1000));
    return header.includes("CCITTFaxDecode") || header.includes("/CCF");
  } catch {
    return false;
  }
}

export default function PdfPreviewModal({ filePath, title, onClose }: PdfPreviewModalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [useIframe, setUseIframe] = useState(false);
  const [printing, setPrinting] = useState(false);

  const handlePrint = () => {
    setPrinting(true);
    const url = buildFileUrl(filePath);
    // 打开 PDF 在新窗口，让浏览器原生 PDF 阅读器渲染
    const w = window.open(url, "_blank");
    if (w) {
      // 等待 PDF 加载后触发打印预览
      const checkReady = setInterval(() => {
        try {
          if (w.document.readyState === "complete") {
            clearInterval(checkReady);
            setTimeout(() => {
              w.print();
              setPrinting(false);
            }, 500);
          }
        } catch {
          // 跨域或其他异常，直接触发打印
          clearInterval(checkReady);
          w.print();
          setPrinting(false);
        }
      }, 200);
      // 超时保护
      setTimeout(() => {
        clearInterval(checkReady);
        setPrinting(false);
      }, 10000);
    } else {
      setPrinting(false);
      alert("浏览器拦截了弹窗，请允许弹窗后重试");
    }
  };

  useEffect(() => {
    if (!filePath) return;
    let aborted = false;
    setLoading(true);
    setError(null);
    const url = buildFileUrl(filePath);

    isImagePdf(url).then((isImg) => {
      if (aborted) return;
      if (isImg) {
        setUseIframe(true);
        setLoading(false);
        return;
      }
      setUseIframe(false);

      pdfjsLib.getDocument(url).promise
        .then(async (pdf) => {
          if (aborted) return;
          // 清空容器
          if (containerRef.current) {
            containerRef.current.replaceChildren();
          }

          // 计算容器宽度
          const containerWidth = containerRef.current?.clientWidth || 800;
          const maxWidth = Math.min(containerWidth - 16, 850);

          // 拿到第一页的原始宽度，统一 scale
          const firstPage = await pdf.getPage(1);
          const unscaledViewport = firstPage.getViewport({ scale: 1 });
          const fitScale = maxWidth / unscaledViewport.width;
          const scale = Math.max(fitScale, 1.0);

          // 逐页渲染，每页一个 canvas
          for (let i = 1; i <= pdf.numPages; i++) {
            try {
              const page = await pdf.getPage(i);
              const viewport = page.getViewport({ scale });

              const canvas = document.createElement("canvas");
              canvas.width = viewport.width * (window.devicePixelRatio || 1);
              canvas.height = viewport.height * (window.devicePixelRatio || 1);
              canvas.style.width = viewport.width + "px";
              canvas.style.height = viewport.height + "px";
              canvas.style.maxWidth = "100%";
              canvas.style.display = "block";
              canvas.style.margin = "0 auto 8px auto";
              canvas.style.border = "1px solid var(--border)";

              const ctx = canvas.getContext("2d");
              if (ctx) {
                ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
                await page.render({ canvasContext: ctx, viewport }).promise;
              }

              containerRef.current?.appendChild(canvas);
            } catch (e) {
              console.error(`渲染第 ${i} 页失败:`, e);
            }
          }

          if (aborted) return;
          setLoading(false);
        })
        .catch(() => {
          if (aborted) return;
          setUseIframe(true);
          setLoading(false);
        });
    });

    return () => { aborted = true; };
  }, [filePath]);

  return (
    <div className="modal-overlay" style={{ zIndex: 1100 }} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-panel" style={{ maxWidth: 900, width: "95vw", height: "90vh", display: "flex", flexDirection: "column" }}>
        <div className="modal-header">
          <span style={{ fontWeight: 600 }}>{title || "PDF 预览"}</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {!loading && !error && !useIframe && (
              <button
                className="btn"
                style={{ padding: "4px 10px", display: "flex", alignItems: "center", gap: 4, fontSize: 13 }}
                onClick={handlePrint}
                disabled={printing}
                title="打印 PDF（弹出打印预览）"
              >
                <Printer size={16} />
                {printing ? "打印中..." : "打印"}
              </button>
            )}
            <button className="btn" style={{ padding: "4px 8px" }} onClick={onClose}>
              <X size={16} />
            </button>
          </div>
        </div>
        <div className="modal-body" style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", padding: 12, overflow: "auto" }}>
          {loading && <div className="empty">加载中...</div>}
          {error && <div className="alert alert-danger">{error}</div>}
          {!loading && !error && useIframe && (
            <iframe
              src={buildFileUrl(filePath)}
              style={{ flex: 1, width: "100%", border: "1px solid var(--border)", borderRadius: 4 }}
              title="PDF Preview"
            />
          )}
          {!useIframe && (
            <div
              ref={containerRef}
              style={{ width: "100%", flex: 1, overflow: "auto", padding: "8px 0", display: loading ? "none" : "block" }}
            />
          )}
        </div>
      </div>
    </div>
  );
}