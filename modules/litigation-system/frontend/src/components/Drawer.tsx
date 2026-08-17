/* 可复用右侧抽屉（theme/components.css .drawer-* 结构）：
   mask 点击 / Escape 关闭；body 滚动；foot 放操作按钮。 */
import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export function Drawer({
  title,
  open,
  onClose,
  children,
  foot,
}: {
  title: ReactNode;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  foot?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div className={cn("drawer-mask", open && "open")} onClick={onClose} />
      <div className={cn("drawer", open && "open")} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : "抽屉"}>
        <div className="drawer-head">
          <span className="drawer-title">{title}</span>
          <button type="button" className="icon-btn" style={{ marginLeft: "auto" }} onClick={onClose} aria-label="关闭">
            <X size={15} />
          </button>
        </div>
        <div className="drawer-body">{children}</div>
        {foot && <div className="drawer-foot">{foot}</div>}
      </div>
    </>
  );
}