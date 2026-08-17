/* 展示格式化（docs/02 §2.3：tabular-nums、¥ 千分位、日期统一格式）。 */

/** 金额：¥1,284,600（无值/0 原样）；小数保留 2 位。 */
export function fmtMoney(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  return (
    (n < 0 ? "-¥" : "¥") +
    Math.abs(n).toLocaleString("zh-CN", { minimumFractionDigits: Math.abs(n) % 1 > 0 ? 2 : 0, maximumFractionDigits: 2 })
  );
}

/** 原始数字（千分位，无小数）。 */
export function fmtNum(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("zh-CN");
}

/** 百分比：48.9%（null → —）；ratio 为 0~1 或 0~100 自动识别。 */
export function fmtPct(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  const pct = Math.abs(n) <= 1 ? n * 100 : n;
  return `${pct.toFixed(1)}%`;
}

/** 日期时间（后端 epoch_ms）→ YYYY-MM-DD。 */
export function fmtDate(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "string") return v.startsWith("--") ? v : v;
  const ms = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(ms)) return String(v);
  const d = new Date(ms);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** 日期时间 → YYYY-MM-DD HH:mm。 */
export function fmtDateTime(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const ms = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(ms)) return String(v);
  const d = new Date(ms);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${fmtDate(ms)} ${hh}:${mm}`;
}

/** 数组/JSON 值 → 展示串（defendant/court/artist 等）；空数组 → — 占位。 */
export function fmtList(v: unknown): string {
  if (Array.isArray(v)) {
    const s = v.filter((x) => x !== null && x !== "").join(" / ");
    return s || "—";
  }
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

export function fmtText(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

/** 字段值按类型格式化（详情/表格统一入口）。 */
export function fmtByType(v: unknown, type: string): string {
  switch (type) {
    case "num":
      return fmtMoney(v);
    case "date":
      return fmtDate(v);
    case "json":
      return fmtList(v);
    default:
      return fmtText(v);
  }
}

/** 下载 Blob（导出）。 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** 复制到剪贴板。 */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}