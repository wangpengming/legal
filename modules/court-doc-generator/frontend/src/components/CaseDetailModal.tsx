import { useEffect, useState } from "react";
import { Download, Eye, X } from "lucide-react";
import { historyApi, Case } from "../lib/api";
import PdfPreviewModal from "./PdfPreviewModal";

function toHex(str: string): string {
  return Array.from(new TextEncoder().encode(str))
    .map(b => b.toString(16).padStart(2, "0")).join("");
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

interface HistoryFile { name: string; path: string; size: number; is_pdf: boolean }
interface HistoryRecord { id: number; case_id: number; output_dir: string; created_at: string | null }

interface CaseDetailModalProps {
  caseItem: Case;
  onClose: () => void;
}

/** 案件详情弹窗：基本信息 + 生成历史文件列表（可预览/下载）。 */
export default function CaseDetailModal({ caseItem, onClose }: CaseDetailModalProps) {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [filesMap, setFilesMap] = useState<Record<number, HistoryFile[]>>({});
  const [loadingRecords, setLoadingRecords] = useState(true);
  const [loadingFiles, setLoadingFiles] = useState<number | null>(null);
  const [previewFile, setPreviewFile] = useState<{ path: string; name: string } | null>(null);

  // 加载该案件的生成历史
  useEffect(() => {
    let cancelled = false;
    setLoadingRecords(true);
    historyApi.list().then((list) => {
      if (cancelled) return;
      const mine = list.filter(h => h.case_id === caseItem.id);
      setRecords(mine);
      setLoadingRecords(false);
      // 并行加载每条记录的文件列表
      mine.forEach(async (h) => {
        try {
          const files = await historyApi.listFiles(h.id);
          if (!cancelled) setFilesMap(prev => ({ ...prev, [h.id]: files }));
        } catch { /* 忽略单条加载失败 */ }
      });
    }).catch(() => {
      if (!cancelled) setLoadingRecords(false);
    });
    return () => { cancelled = true; };
  }, [caseItem.id]);

  const rows: Array<[string, string]> = [
    ["案号", caseItem.case_number],
    ["审理法院", caseItem.court || "—"],
    ["案由", caseItem.cause || "—"],
    ["开庭日期", caseItem.hearing_date || "—"],
    ["对方当事人", caseItem.opposing_party || "—"],
    ["我方角色", caseItem.our_role],
  ];

  return (
    <>
      {previewFile && (
        <PdfPreviewModal
          filePath={previewFile.path}
          title={previewFile.name}
          onClose={() => setPreviewFile(null)}
        />
      )}

      <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
        <div className="modal-panel" style={{ maxWidth: 760, width: "95vw", height: "85vh", display: "flex", flexDirection: "column" }}>
          <div className="modal-header">
            <span style={{ fontWeight: 600 }}>案件详情：{caseItem.case_number}</span>
            <button className="btn" style={{ padding: "4px 8px" }} onClick={onClose}>
              <X size={16} />
            </button>
          </div>

          <div className="modal-body" style={{ flex: 1, overflowY: "auto", padding: 16 }}>
            {/* 基本信息 */}
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>📋 基本信息</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "6px 24px", marginBottom: 20 }}>
              {rows.map(([k, v]) => (
                <div key={k} style={{ display: "flex", gap: 8, fontSize: 13 }}>
                  <span className="text-muted" style={{ flexShrink: 0 }}>{k}</span>
                  <span>{v}</span>
                </div>
              ))}
            </div>

            {/* 生成历史 */}
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>📁 生成记录</h3>
            {loadingRecords ? (
              <div className="empty" style={{ padding: 24 }}>加载中...</div>
            ) : records.length === 0 ? (
              <div className="empty" style={{ padding: 24 }}>
                <div className="empty-icon">📁</div>
                <div>该案件还没有生成记录</div>
                <div className="text-muted text-sm" style={{ marginTop: 4 }}>
                  回到案件列表点击「生成」即可生成出庭材料
                </div>
              </div>
            ) : (
              records.map(h => (
                <div key={h.id} className="card" style={{ marginBottom: 12, padding: 12 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <span className="text-muted text-sm">
                      {h.created_at ? new Date(h.created_at).toLocaleString("zh-CN") : "—"}
                    </span>
                    <span className="text-muted text-sm" style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {h.output_dir}
                    </span>
                    <a
                      href={`/api/v1/history/${h.id}/download-zip`}
                      className="btn" style={{ padding: "4px 8px", fontSize: 12 }}
                      title="下载 ZIP"
                    >
                      <Download size={12} /> ZIP
                    </a>
                  </div>
                  {loadingFiles === h.id ? (
                    <div className="text-muted text-sm" style={{ padding: "8px 0" }}>加载文件...</div>
                  ) : (
                    <div>
                      {(filesMap[h.id] || []).map(f => (
                        <div key={f.name} className="file-item">
                          <span style={{ flex: 1 }}>{f.name}</span>
                          <span className="text-muted text-sm">{formatSize(f.size)}</span>
                          {f.is_pdf && (
                            <button
                              className="btn" style={{ padding: "4px 8px", fontSize: 12 }}
                              onClick={() => setPreviewFile({ name: f.name, path: f.path })}
                            >
                              <Eye size={12} /> 预览
                            </button>
                          )}
                          <a
                            href={`/api/v1/files/~hex/${toHex(f.path)}?ws=${sessionStorage.getItem("_ws_id") || ""}`}
                            target="_blank"
                            rel="noreferrer"
                            className="btn" style={{ padding: "4px 8px", fontSize: 12 }}
                            download={f.name}
                          >
                            <Download size={12} />
                          </a>
                        </div>
                      ))}
                      {(!filesMap[h.id] || filesMap[h.id].length === 0) && (
                        <div className="text-muted text-sm" style={{ padding: "8px 0" }}>无文件</div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}