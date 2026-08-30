import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, Download, Eye, ChevronDown, ChevronUp, Camera } from "lucide-react";
import { historyApi } from "../lib/api";
import PdfPreviewModal from "../components/PdfPreviewModal";
import ConfirmDialog from "../components/ConfirmDialog";

function toHex(str: string): string {
  return Array.from(new TextEncoder().encode(str))
    .map(b => b.toString(16).padStart(2, "0")).join("");
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export default function HistoryPage() {
  const qc = useQueryClient();
  const { data: history = [], isLoading } = useQuery({
    queryKey: ["history"],
    queryFn: historyApi.list,
  });

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filesMap, setFilesMap] = useState<Record<number, Array<{ name: string; path: string; size: number; is_pdf: boolean }>>>({});
  const [previewFile, setPreviewFile] = useState<{ path: string; name: string } | null>(null);
  const [loadingFiles, setLoadingFiles] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const remove = useMutation({
    mutationFn: (id: number) => historyApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
    onError: (err: unknown) => alert(err instanceof Error ? err.message : "删除失败"),
  });

  async function toggleExpand(recordId: number) {
    if (expandedId === recordId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(recordId);
    if (!filesMap[recordId]) {
      setLoadingFiles(recordId);
      try {
        const files = await historyApi.listFiles(recordId);
        setFilesMap(prev => ({ ...prev, [recordId]: files }));
      } catch (e) {
        setFilesMap(prev => ({ ...prev, [recordId]: [] }));
      }
      setLoadingFiles(null);
    }
  }

  function downloadZip(recordId: number) {
    const wsId = sessionStorage.getItem("_ws_id") || "";
    const base = "/api/v1";
    window.open(`${base}/history/${recordId}/download-zip`, "_blank");
  }

  return (
    <div>
      {previewFile && (
        <PdfPreviewModal
          filePath={previewFile.path}
          title={previewFile.name}
          onClose={() => setPreviewFile(null)}
        />
      )}
      {confirmDelete !== null && (
        <ConfirmDialog
          title="删除历史记录"
          message={`确定删除这条生成记录吗？\n输出目录：${history.find(h => h.id === confirmDelete)?.output_dir || ""}\n此操作不可恢复。`}
          confirmText="删除"
          danger={true}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => { remove.mutate(confirmDelete); setConfirmDelete(null); }}
        />
      )}

      <div className="page-header">
        <h1 className="page-title">📁 历史记录</h1>
      </div>

      <div className="card">
        {isLoading ? <div className="empty">加载中...</div>
          : history.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">📁</div>
              <div>暂无生成记录</div>
              <div className="text-muted mt-8 text-sm">
                在「案件」页面选择案件后点击「生成」即可生成出庭材料
              </div>
            </div>
          ) : (
            history.map((h) => (
              <div key={h.id} className="expander">
                <div
                  className="expander-header"
                  onClick={() => toggleExpand(h.id)}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {expandedId === h.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    <span>案件 #{h.case_id}</span>
                    <span className="text-muted text-sm">
                      {h.created_at ? new Date(h.created_at).toLocaleString("zh-CN") : "—"}
                    </span>
                    <span className="text-muted text-sm" style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {h.output_dir}
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: 4 }} onClick={e => e.stopPropagation()}>
                    <button
                      className="btn btn-primary" style={{ padding: "4px 10px", fontSize: 12 }}
                      onClick={() => downloadZip(h.id)}
                      title="下载 ZIP"
                    >
                      <Download size={12} /> ZIP
                    </button>
                    <button
                      className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 12 }}
                      onClick={() => setConfirmDelete(h.id)}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>

                {expandedId === h.id && (
                  <div className="expander-body">
                    {loadingFiles === h.id ? (
                      <div className="empty" style={{ padding: 24 }}>加载文件...</div>
                    ) : (
                      <div>
                        {(filesMap[h.id] || []).map((f) => (
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
                              href={`/api/v1/files/~hex/${toHex(f.path)}?ws=${sessionStorage.getItem("_ws_id") || ""}&t=${Date.now()}`}
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
                )}
              </div>
            ))
          )
        }
      </div>
    </div>
  );
}
