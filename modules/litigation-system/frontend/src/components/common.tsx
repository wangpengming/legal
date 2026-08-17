/* 公共 UI 组件（className 对齐 theme/components.css，原子类覆盖走 Tailwind utilities） */
import type { CSSProperties, ReactNode } from "react";
import { AlertTriangle, Info, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { TONE_CLASS, type Tone } from "@/lib/colors";

/* ---------- 状态徽章（六态：green/red/amber/blue/gray/outline） ---------- */
export function Badge({
  tone = "gray",
  dot = true,
  outline = false,
  children,
  title,
  className,
}: {
  tone?: Tone;
  dot?: boolean;
  outline?: boolean;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <span className={cn("badge", outline ? "badge-outline" : TONE_CLASS[tone], className)} title={title}>
      {dot && <i className="dot" />}
      {children}
    </span>
  );
}

/* 枚举 label 徽章（无 dot，plain 背景；传 enum color 时着色） */
export function EnumBadge({ tone, children, className, style }: { tone?: Tone; children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <span className={cn("badge", tone ? TONE_CLASS[tone] : "badge-plain", className)} style={style}>{children}</span>
  );
}

/* ---------- 数字卡 ---------- */
export function StatCard({
  label,
  value,
  delta,
  hint,
  sub,
  onClick,
}: {
  label: ReactNode;
  value: ReactNode;
  delta?: ReactNode;
  hint?: string | null;
  sub?: ReactNode;
  onClick?: () => void;
}) {
  return (
    <div
      className="card stat-card"
      onClick={onClick}
      role={onClick ? "button" : undefined}
      title={hint ?? undefined}
      style={onClick ? { cursor: "pointer" } : undefined}
    >
      <div className="stat-label">
        {label}
        {hint && (
          <span className="help" title={hint}>
            ⓘ
          </span>
        )}
      </div>
      <div className="stat-value">{value}</div>
      {delta && <div className="stat-delta">{delta}</div>}
      {sub && <div style={{ fontSize: 11, color: "var(--muted-2)" }}>{sub}</div>}
    </div>
  );
}

/* ---------- 页面公共头 ---------- */
export function PageHeader({
  title,
  breadcrumb,
  actions,
}: {
  title: ReactNode;
  breadcrumb?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <div className="page-title">{title}</div>
        {breadcrumb && <div className="page-breadcrumb">{breadcrumb}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

/* ---------- 加载 / 错误 / 空态 ---------- */
export function PageLoading({ rows = 3 }: { rows?: number }) {
  return (
    <div style={{ display: "grid", gap: 14 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="card card-pad">
          <div className="skeleton" style={{ height: 16, width: "38%", marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 120 }} />
        </div>
      ))}
    </div>
  );
}

export function Spinner({ label = "加载中…" }: { label?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "24px 8px", color: "var(--muted)" }}>
      <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
      <span style={{ fontSize: 12.5 }}>{label}</span>
    </div>
  );
}

export function PageError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert red">
      <XCircle size={15} />
      <span className="grow">{message}</span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>
          重试
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon = "🗂",
  title,
  desc,
  action,
}: {
  icon?: ReactNode;
  title: string;
  desc?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="e-ico">{icon}</div>
      <div className="e-title">{title}</div>
      {desc && <div className="e-desc">{desc}</div>}
      {action}
    </div>
  );
}

/* ---------- 提示条 / 面包屑 ---------- */
export function Alert({ kind = "blue", children }: { kind?: "blue" | "amber" | "red"; children: ReactNode }) {
  const Icon = kind === "red" ? XCircle : kind === "amber" ? AlertTriangle : Info;
  return (
    <div className={cn("alert", kind)}>
      <Icon size={15} />
      <span className="grow">{children}</span>
    </div>
  );
}

export function Tooltip({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <span className="tip">
      {children}
      <span className="tip-box">{label}</span>
    </span>
  );
}

/* ---------- 同步状态条 ---------- */
export function SyncBar({
  kind,
  icon,
  children,
  action,
}: {
  kind: "ok" | "warn" | "err";
  icon?: ReactNode;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={cn("syncbar", kind)}>
      {icon}
      <span className="grow">{children}</span>
      {action}
    </div>
  );
}

/* ---------- 骨架行 ---------- */
export function SkeletonRows({ rows = 6, height = 22 }: { rows?: number; height?: number }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height, width: `${92 - (i % 4) * 8}%` }} />
      ))}
    </div>
  );
}