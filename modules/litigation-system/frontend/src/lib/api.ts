/* API 客户端（对齐后端 /api/v1 契约，docs/03 §6.2）
   统一包裹 {code, data, meta:{total,page,page_size,footnote}}；
   错误抛 ApiError{status, code, message, detail}。 */

export interface ApiMeta {
  total?: number;
  page?: number;
  page_size?: number;
  footnote?: string;
}

export interface ApiRes<T> {
  code: number;
  data: T;
  meta: ApiMeta;
}

export class ApiError extends Error {
  status: number;
  code?: number;
  detail?: unknown;
  constructor(status: number, message: string, code?: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<ApiRes<T>> {
  let res: Response;
  try {
    res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (e) {
    throw new ApiError(0, `网络请求失败：${e instanceof Error ? e.message : String(e)}`);
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* 非 JSON（导出文件流）由调用方处理 */
  }
  if (!res.ok) {
    const detail = (body as { detail?: unknown })?.detail;
    const message = typeof detail === "string" ? detail : res.statusText || `请求失败（${res.status}）`;
    throw new ApiError(res.status, message, (body as { code?: number })?.code, detail);
  }
  const wrapped = body as ApiRes<T>;
  if (!wrapped || typeof wrapped.code !== "number") {
    throw new ApiError(res.status, "响应格式异常：缺少 code 包裹");
  }
  return wrapped;
}

/* ---------------------------------------------------------------- 类型 */

export interface FieldMeta {
  key: string;
  label: string;
  type: "str" | "num" | "date" | "json" | "bool";
  filterable: boolean;
  sortable: boolean;
  in_default: boolean;
}

export interface EnumItem {
  enum_key: string;
  label: string;
  color?: string | null;
  /** JSON 反序列化：{原始选项: 规范值}（合并项别名，dicts.py _load 输出） */
  aliases?: Record<string, string> | null;
  version?: string | null;
}

export interface RuleItem {
  rule_tag: string;
  version?: string | null;
  target_field?: string | null;
  rule_type?: string | null;
  pattern?: string | null;
  replacement?: string | null;
  mapped?: Record<string, string> | null;
  priority: number;
  enabled: boolean;
  description?: string | null;
}

export interface MetricDef {
  key: string;
  title: string;
  version?: string | null;
  definition?: string | null;
  footnote?: string | null;
  sample_n?: number | null;
  enabled: boolean;
}

export interface SyncJobInfo {
  id: number;
  type: string;
  status: string;
  total: number;
  upserted: number;
  skipped: number;
  deleted?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  error_brief?: string | null;
  last_sync_at?: string | null;
}

export interface MetadataData {
  fields: FieldMeta[];
  view_fields: string[];
  enums: Record<string, EnumItem[]>;
  rules: RuleItem[];
  metric_defs: MetricDef[];
  versions: {
    metric?: Record<string, string> | null;
    clean_rules?: Record<string, string> | null;
    schema?: unknown;
    baseline?: unknown;
  };
  feishu_configured: boolean;
  latest_sync: SyncJobInfo | null;
}

/* 检索 */
export interface SearchFilter {
  field: string;
  op: "eq" | "ne" | "in" | "nin" | "contains" | "range";
  value?: string | number;
  values?: (string | number)[];
  min?: number;
  max?: number;
}

export interface SearchSort {
  field: string;
  desc: boolean;
}

export interface SearchRequest {
  q?: string;
  filters?: SearchFilter[];
  sorts?: SearchSort[];
  page: number;
  page_size: number;
  columns?: string[];
  /* scope 仅导出有效（后端 ExportRequest Literal "all"|"search"|"case"）；search POST 忽略多余字段 */
  scope?: "all" | "search" | "case";
  ids?: string[];
}

export type CaseRow = Record<string, unknown>;

/* 案件详情 */
export interface SongLink {
  record_id: string;
  song_name: string;
  artist: string | null;
  role?: string | null;
}

export interface AuditItem {
  id: number;
  op_type: string;
  rule_tag?: string | null;
  rule_version?: string | null;
  field?: string | null;
  action: string;
  old_value?: unknown;
  new_value?: unknown;
  detail?: unknown;
  operator?: string | null;
  created_at?: string | null;
}

export interface CaseDetailData {
  base: Record<string, unknown>;
  songs: SongLink[];
  raw: { record_id: string; fields: Record<string, unknown>; synced_at?: string | null } | null;
  audit: AuditItem[];
  series: {
    parent_record_id: string | null;
    related_case_no: string | null;
    siblings: { record_id: string; case_no: string | null; year?: number | null; resolve?: string | null }[];
  };
}

/* 统计 */
export interface Kpi {
  key: string;
  title: string;
  value: number | null;
  definition?: string | null;
  version?: string | null;
}

export interface TrendItem {
  year: number | null;
  case_count: number;
  verdict_amount: number | null;
}

export interface BizlineItem {
  biz_line: string;
  case_count: number;
  verdict_amount: number | null;
}

export interface UpcomingCourt {
  record_id: string;
  case_no: string | null;
  court_date: number | null;
  year: number | null;
  resolve: string | null;
}

export interface OverviewData {
  kpis: Kpi[];
  metric_versions: Record<string, string>;
  trend: TrendItem[];
  bizline: BizlineItem[];
  upcoming_court: UpcomingCourt[];
  summary: {
    total_cases: number;
    acmc_cases: number;
    monthly_new: number;
    verdict_total: number;
  };
}

/* ---- 04-parties 对手方画像 ---- */
export interface PartyYearRow {
  year: number;
  case_count: number;
  verdict_amount: number;
}
export interface PartyCauseRow {
  cause: string;
  case_count: number;
  verdict_amount: number;
}
export interface PartyCaseRow {
  record_id: string;
  case_no: string;
  year: number | null;
  court: string[] | null;
  resolve: string | null;
  amount: number | null;
  pay_amount: number | null;
  case_status: string | null;
  biz_line?: string | null;
  cause?: string | null;
  support_rate?: number | null;
}
export interface PartyData {
  name: string;
  total: number;
  verdict_count: number;
  verdict_amount: number;
  offsite_count: number;
  win_rate_a: number | null;
  years: PartyYearRow[];
  causes: PartyCauseRow[];
  cases: PartyCaseRow[];
}

export interface PartySummary {
  name: string;
  case_count: number;
  win_count: number;
  lose_count: number;
  win_rate_a: number | null;
  verdict_count: number;
  verdict_amount: number;
  offsite_count: number;
  biz_lines: string[];
  first_year: number | null;
  last_year: number | null;
  share: number | null;
}
export interface PartiesData {
  items: PartySummary[];
  total_parties: number;
  covered_cases: number;
}

/* ---- 05-analysis 多维分析（热力矩阵 + 下钻） ---- */
export type AnalysisDim = "bizYear" | "causeYear" | "payerStatus";
export interface AnalysisCell {
  case_count: number;
  verdict_count: number;
  verdict_rate: number;
}
export interface AnalysisData {
  dim: AnalysisDim;
  row_label: string;
  col_label: string;
  rows: string[];
  cols: string[];
  cells: AnalysisCell[][];
  total_cases: number;
}
export interface AnalysisCauseAgg {
  cause: string;
  case_count: number;
}
export interface AnalysisDrillRow {
  record_id: string;
  case_no: string | null;
  year: number | null;
  defendant: string[] | null;
  court: string[] | null;
  resolve: string | null;
  amount: number | null;
  pay_amount: number | null;
  cause: string | null;
  biz_line: string | null;
  case_status: string | null;
  support_rate: number | null;
  payer: string | null;
}
export interface AnalysisDrillData {
  x: string;
  dim: AnalysisDim;
  col: number | string | null;
  cause: string | null;
  items: AnalysisDrillRow[];
  total: number;
  causes: AnalysisCauseAgg[];
}
export interface AnalysisSel {
  x?: string;
  col?: string;
  cause?: string;
}

export interface BizlineRow {
  biz_line: string;
  year: number;
  case_count: number;
  verdict_amount: number;
  with_year: number;
}
export interface BizlineData {
  year: number | null;
  items: BizlineRow[];
}

export interface SongAgg {
  song_id: string;
  song_name: string;
  artist: string | null;
  case_count: number;
  verdict_amount: number | null;
}
export interface SongsData {
  songs: SongAgg[];
  aggregate: { avg_per_song: number; total_song_slots: number; case_count: number };
  metric: Kpi | null;
}

export interface FeesData {
  year: number | null;
  four: {
    verdict: { amount: number; count: number };
    recovered: { amount: number | null; count: number | null; hint: string };
    expense: { amount: number | null; count: number | null; hint: string };
    net: { amount: number | null; hint: string };
  };
  monthly: { m: string; cnt: number; amount: number | null }[];
  dubious: Record<string, unknown>[];
}

/* 同步 */
export interface SyncStatusData {
  running: boolean;
  running_job_id: number | null;
  last: SyncJobInfo | null;
  next_at: string | null;
  feishu_configured: boolean;
  jobs: Record<string, string>;
}

export interface SyncJobLog {
  id: number;
  job_type: string;
  status: string;
  total: number;
  upserted: number;
  skipped: number;
  error_brief?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

/* 字典 */
export interface DictsData {
  enums: Record<string, EnumItem[]>;
  rules: RuleItem[];
  company_map: { id: number; company_raw: string; canonical: string; source?: string | null; enabled: boolean }[];
  metric_defs: MetricDef[];
  versions: Record<string, unknown>;
}

export interface DirtyItem {
  key: string; // "{record_id}:{field}"，处置端点路径参数
  record_id: string;
  case_no?: string | null;
  field: string;
  raw_value?: string | null;
  trace: { rule_tag?: string | null; created_at?: string | null; reason?: unknown }[];
}


/* M4 标签（/tags，Phase 2）：kind=manual 人工 / derived 派生 */
export type TagKind = "manual" | "derived";

export interface TagItem {
  id: number;
  name: string;
  kind: TagKind;
  color: string | null;
  description: string | null;
  /** 仅列表/对象列举返回：关联对象数 */
  link_count?: number;
}

export type TagTargetType = "case" | "song" | "party" | "external_case";

export interface TagLinkPayload {
  /** 二选一：tag_id 或 tag_name（新名自动创建 manual 标签） */
  tag_id?: number;
  tag_name?: string;
  target_type: TagTargetType;
  target_id: string;
  /** true=打标（幂等），false=取消 */
  link?: boolean;
}

export interface TagObjectsData {
  tag: TagItem;
  objects: { target_type: TagTargetType; target_id: string; name: string; linked_at?: string | null }[];
  by_type: Record<TagTargetType, number>;
}

/* F4.2 同质案类推（POST /similar，Phase 3）：加权 Top10 + 风险提示卡 */
export interface SimilarItem {
  record_id: string;
  case_no: string | null;
  cause: string | null;
  resolve: string | null;
  biz_line: string | null;
  amount: number | null;
  pay_amount: number | null;
  defendant: string[];
  /** 加权得分 0~100（F4.2 权重） */
  similarity: number;
  notes: string | null;
}

export interface SimilarData {
  target: Record<string, unknown>;
  items: SimilarItem[];
  risk: {
    resolve_dist: { resolve: string; count: number }[];
    pay_range: { n: number; p25: number; p50: number; p75: number };
    note_points: string[];
  };
  weights: Record<string, number>;
}

/* Mode B 报告存档（/reports，Phase 3）：T1~T7 落库 + 三源脚注 */
export interface AiSource {
  hits: number;
  note: string;
}

export interface AiSources {
  local: AiSource;
  cases: AiSource;
  law: AiSource;
}

export interface ReportItem {
  id: number;
  template_key: string;
  title: string;
  params: Record<string, string>;
  created_by: string | null;
  created_at: string;
  /** 列表端点不含正文 */
  body?: string;
  sources?: AiSources;
}

export interface ReportGeneratePayload {
  template_key: string;
  params?: Record<string, string>;
  created_by?: string;
}

/* AI Mode A/B 对话（POST /ai/chat，Phase 3） */
export type AiMode = "A" | "B";

export interface AiChatPayload {
  session_id?: string;
  mode: AiMode;
  question: string;
}

export interface AiChatResult {
  mode: AiMode;
  /** A：intent / used_query（整句未命中时的聚焦检索词） */
  intent?: string;
  used_query?: string;
  answer: string;
  evidence?: Record<string, unknown>[];
  law_hits?: { law: string; article: string; text: string }[];
  /** B：title / template_key / report_id / params */
  title?: string;
  template_key?: string;
  report_id?: number | null;
  params?: Record<string, string>;
  sources?: AiSources;
  footnote?: string;
}

export interface AiReportTemplate {
  key: string;
  title: string;
  description: string;
  params: string[];
  output: string;
}

/* 清洗规则试算（POST /dicts/test）：每个样本的命中事件预览，不落库 */
export interface DictTestResult {
  index: number;
  record_id: string;
  changed: boolean;
  dirty_flags: string[];
  /** 单样本失败时不阻断整体（后端防御），error 存在时 events 为空 */
  error?: string | null;
  events: { rule_tag?: string | null; field?: string | null; action?: string | null; old_value?: unknown; new_value?: unknown }[];
}

/* ---------------------------------------------------------------- 端点 */

const BASE = "/api/v1";

export const api = {
  metadata: () => request<MetadataData>(`${BASE}/metadata`),

  search: (payload: SearchRequest) =>
    request<CaseRow[]>(`${BASE}/search`, { method: "POST", body: JSON.stringify(payload) }),

  caseDetail: (id: string) => request<CaseDetailData>(`${BASE}/cases/${encodeURIComponent(id)}`),
  caseRaw: (id: string) =>
    request<{ record_id: string; fields: Record<string, unknown>; synced_at?: string | null }>(
      `${BASE}/cases/${encodeURIComponent(id)}/raw`,
    ),
  caseBatch: (payload: { ids: string[]; action: "tag" | "export"; tag?: string }) =>
    request<{ tag?: string; linked?: number; count?: number; ids?: string[] }>(`${BASE}/cases/batch`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  overview: () => request<OverviewData>(`${BASE}/stats/overview`),
  parties: (limit = 20) => request<PartiesData>(`${BASE}/stats/parties?limit=${limit}`),
  party: (name: string) =>
    request<PartyData>(`${BASE}/stats/party?name=${encodeURIComponent(name)}`),
  bizline: (year?: number) =>
    request<BizlineData>(`${BASE}/stats/bizline${year ? `?year=${year}` : ""}`),
  songs: () => request<SongsData>(`${BASE}/stats/songs`),
  fees: (year?: number) =>
    request<FeesData>(`${BASE}/stats/fees${year ? `?year=${year}` : ""}`),
  analysis: (dim: AnalysisDim = "bizYear") =>
    request<AnalysisData>(`${BASE}/stats/analysis?dim=${dim}`),
  analysisDrill: (dim: AnalysisDim, sel: AnalysisSel) => {
    const p = new URLSearchParams({ dim });
    if (sel.x) p.set("x", sel.x);
    if (sel.col) p.set("col", sel.col);
    if (sel.cause) p.set("cause", sel.cause);
    return request<AnalysisDrillData>(`${BASE}/stats/analysis/drill?${p.toString()}`);
  },

  syncRun: (payload: { type: "full" | "incremental" | "record"; id?: string }) =>
    request<Record<string, unknown>>(`${BASE}/sync/run`, { method: "POST", body: JSON.stringify(payload) }),
  syncStatus: () => request<SyncStatusData>(`${BASE}/sync/status`),
  syncLogs: (limit = 50) => request<SyncJobLog[]>(`${BASE}/sync/logs?limit=${Math.min(limit, 100)}`),

  dicts: () => request<DictsData>(`${BASE}/dicts`),
  dictWrite: (payload: {
    action: "enum" | "rule_toggle";
    field?: string;
    enum_key?: string;
    label?: string;
    color?: string;
    aliases?: Record<string, string>; // {原始选项: 规范值}
    rule_tag?: string;
    enabled?: boolean;
  }) => request<Record<string, unknown>>(`${BASE}/dicts`, { method: "POST", body: JSON.stringify(payload) }),
  dictTest: (payload: { samples: Record<string, unknown>[]; rule_tags?: string[] }) =>
    request<DictTestResult[]>(`${BASE}/dicts/test`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  /** 后端 ok(items, total)：data 为裸数组，总标记数在 meta.total */
  dictDirty: () => request<DirtyItem[]>(`${BASE}/dicts/dirty-items`),
  /** 脏标记处置：key = "{record_id}:{field}"（后端路径参数） */
  dictDirtyAction: (key: string, payload: { action: "adopt" | "ignore" | "edit"; value?: string }) =>
    request<Record<string, unknown>>(`${BASE}/dicts/dirty-items/${encodeURIComponent(key)}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  /* ── M4 标签（Phase 2） ─────────────────────────────────────── */
  tags: (kind?: TagKind) => request<TagItem[]>(`${BASE}/tags${kind ? `?kind=${kind}` : ""}`),
  tagCreate: (payload: {
    name: string;
    kind?: TagKind;
    color?: string | null;
    description?: string | null;
  }) => request<TagItem>(`${BASE}/tags`, { method: "POST", body: JSON.stringify(payload) }),
  tagUpdate: (id: number, payload: { name?: string; color?: string | null; description?: string | null }) =>
    request<TagItem>(`${BASE}/tags/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  tagDelete: (id: number) =>
    request<{ id: number; deleted: boolean }>(`${BASE}/tags/${id}`, { method: "DELETE" }),
  tagLink: (payload: TagLinkPayload) =>
    request<{ linked: boolean; tag_id: number; tag_name: string }>(`${BASE}/tags/link`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  tagBatch: (payload: { tag_name: string; target_type: TagTargetType; target_ids: string[] }) =>
    request<{ tag_id: number; tag_name: string; targets: number; new_links: number }>(`${BASE}/tags/batch`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  tagMerge: (payload: { from_id: number; into_id: number }) =>
    request<{ from_id: number; into_id: number; into_name: string; moved_links: number }>(
      `${BASE}/tags/merge`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  tagObjects: (id: number) => request<TagObjectsData>(`${BASE}/tags/${id}/objects`),

  /* ── F4.2 同质案类推（Phase 3） ─────────────────────────────── */
  similar: (caseId: string) =>
    request<SimilarData>(`${BASE}/similar`, { method: "POST", body: JSON.stringify({ case_id: caseId }) }),

  /* ── Mode B 报告存档（Phase 3） ─────────────────────────────── */
  reportGenerate: (payload: ReportGeneratePayload) =>
    request<ReportItem>(`${BASE}/reports/generate`, { method: "POST", body: JSON.stringify(payload) }),
  reports: (page = 1, pageSize = 20, templateKey?: string) =>
    request<ReportItem[]>(
      `${BASE}/reports?page=${page}&page_size=${pageSize}${templateKey ? `&template_key=${templateKey}` : ""}`,
    ),
  reportDetail: (id: number) => request<ReportItem>(`${BASE}/reports/${id}`),
  reportDelete: (id: number) =>
    request<{ id: number; deleted: boolean }>(`${BASE}/reports/${id}`, { method: "DELETE" }),

  /* ── AI Mode A/B 对话（Phase 3） ────────────────────────────── */
  aiChat: (payload: AiChatPayload) =>
    request<AiChatResult>(`${BASE}/ai/chat`, { method: "POST", body: JSON.stringify(payload) }),
  aiTemplates: () => request<AiReportTemplate[]>(`${BASE}/ai/report-templates`),

  /** 导出：返回 Blob（CSV 带口径脚注可选）；ExportRequest 无需分页字段 */
  async exportCsv(payload: Partial<SearchRequest> & { with_footnote?: boolean }): Promise<Blob> {
    const res = await fetch(`${BASE}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, format: "csv" }),
    });
    if (!res.ok) {
      let msg = `导出失败（${res.status}）`;
      try {
        const b = await res.json();
        if (typeof b?.detail === "string") msg = b.detail;
      } catch { /* ignore */ }
      throw new ApiError(res.status, msg);
    }
    return res.blob();
  },
};