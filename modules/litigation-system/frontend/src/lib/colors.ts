/* 状态/结案原因 → 徽章色 映射表（docs/02 §2.2，全站唯一来源）。
   语义色：green=我方占优 / red=判赔·败 / amber=执行·终本·待定 / blue=审理中 / gray=中性。 */

export type Tone = "green" | "red" | "amber" | "blue" | "gray";

export const TONE_CLASS: Record<Tone, string> = {
  green: "status-green",
  red: "status-red",
  amber: "status-amber",
  blue: "status-blue",
  gray: "status-gray",
};

/* 案件状态（21 项）按生命周期分组匹配，顺序即优先级 */
const STATUS_RULES: [Tone, RegExp][] = [
  ["red", /判赔/],
  ["green", /撤诉|和解|胜诉|驳回|已结案/],
  ["amber", /执行|终本/],
  ["blue", /待判决|开庭|排期|审理/],
  ["gray", /破产|清算|待办|其他|管辖权|立案/],
];

export function statusTone(s: string | null | undefined): Tone {
  if (!s) return "gray";
  for (const [tone, re] of STATUS_RULES) if (re.test(s)) return tone;
  return "gray";
}

/* 结案原因（15 项）→ 胜负三色（docs/02 §2.2，口径A 胜集） */
const RESOLVE_WIN = ["胜诉", "驳回上诉维持原判", "判决驳回对雷石的诉求", "裁定驳回雷石的诉讼请求", "裁定驳回对雷石的诉讼请求"];
const RESOLVE_LOSE = ["判赔"];

export function resolveTone(r: string | null | undefined): Tone {
  if (!r) return "gray";
  if (RESOLVE_LOSE.includes(r)) return "red";
  if (RESOLVE_WIN.includes(r)) return "green";
  if (r.includes("终本")) return "amber";
  return "gray";
}

/* 后端 EnumDict.color 字符串色名（seed.py）→ Tone */
export function enumTone(color: string | null | undefined): Tone {
  switch (color) {
    case "red":
      return "red";
    case "green":
    case "teal":
      return "green";
    case "amber":
    case "orange":
      return "amber";
    case "blue":
    case "purple":
      return "blue";
    default:
      return "gray";
  }
}

/* 业务线 9 色固定色序（docs/02 §2.2；与 tokens.css --palette 一致，图形共用） */
export const PALETTE = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#db2777", "#65a30d", "#64748b"];

/** 读取当前主题下语义色（ECharts canvas 用，亮暗切换时重取） */
export function themeColors(): { text: string; muted: string; border: string; primary: string; surface: string; fg: string } {
  if (typeof document === "undefined") return { text: "#0f172a", muted: "#64748b", border: "#e2e8f0", primary: "#2563eb", surface: "#ffffff", fg: "#ffffff" };
  const cs = getComputedStyle(document.documentElement);
  const pick = (name: string, d: string) => cs.getPropertyValue(name).trim() || d;
  return {
    text: pick("--text", "#0f172a"),
    muted: pick("--muted", "#64748b"),
    border: pick("--border", "#e2e8f0"),
    primary: pick("--primary", "#2563eb"),
    surface: pick("--surface", "#ffffff"),
    fg: pick("--primary-fg", "#ffffff"),
  };
}