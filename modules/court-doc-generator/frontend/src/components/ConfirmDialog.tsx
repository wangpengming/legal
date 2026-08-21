import { X } from "lucide-react";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmText?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** 二次确认弹窗：用于删除/生成等敏感操作。 */
export default function ConfirmDialog({
  title,
  message,
  confirmText = "确认",
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="modal-panel" style={{ maxWidth: 420, width: "90vw" }}>
        <div className="modal-header">
          <span style={{ fontWeight: 600 }}>{title}</span>
          <button className="btn" style={{ padding: "4px 8px" }} onClick={onCancel}>
            <X size={16} />
          </button>
        </div>
        <div style={{ padding: "16px 20px", fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
          {message}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, padding: "0 20px 16px" }}>
          <button className="btn" onClick={onCancel}>取消</button>
          <button className={danger ? "btn btn-danger" : "btn btn-primary"} onClick={onConfirm}>
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}