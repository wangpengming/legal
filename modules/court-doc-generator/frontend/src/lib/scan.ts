// 拍照扫描：OCR 调用 + 识别字段 → 新建案件表单映射（纯函数，便于验证）

export interface ScanResult {
  text: string;
  fields: Record<string, string | null>;
  error: string | null;
}

export interface ScanCaseMapping {
  case_number: string;
  court: string;
  cause: string;
  hearing_date: string;
  opposing_party: string;
  our_role: string;
}

function wsHeader(): Record<string, string> {
  return { "X-Workspace-Id": sessionStorage.getItem("_ws_id") || "" };
}

async function postScan(url: string, body: FormData | string, headers: Record<string, string>): Promise<ScanResult> {
  const res = await fetch(url, { method: "POST", headers: { ...wsHeader(), ...headers }, body });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || data.detail || "扫描失败");
  return data as ScanResult;
}

/** 上传本地图片/PDF 进行 OCR 识别（支持多文件，后端合并识别并整合字段） */
export async function scanUploadFiles(files: File[]): Promise<ScanResult> {
  const form = new FormData();
  files.forEach(f => form.append("files", f));
  return postScan("/api/v1/scan/scan", form, {});
}

/** 通过图片 URL 进行 OCR 识别 */
export async function scanImageUrl(url: string): Promise<ScanResult> {
  return postScan("/api/v1/scan/scan-url", JSON.stringify({ url }), { "Content-Type": "application/json" });
}

/** 开庭时间归一化：「2026年8月22日」/「2026-8-22」→「2026-08-22」；无法解析则原样返回 */
export function normalizeHearingDate(value: string | null | undefined): string {
  if (!value) return "";
  const m = value.match(/(\d{4})[年\-/.]{1}(\d{1,2})[月\-/.]{1}(\d{1,2})/);
  if (!m) return value;
  return `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;
}

/**
 * 案由提取：OCR 文本中“XX纠纷”常带前缀（本案/本案系/系/属/因/为等）。
 * 取最后一个“纠纷”前的最后一段（按标点/关系词切分）作为案由词干。
 */
export function extractCause(raw: string): string {
  if (!raw) return "";
  const idx = raw.lastIndexOf("纠纷");
  if (idx < 0) return raw;
  const head = raw.slice(0, idx);
  const parts = head.split(/[，。、：:；\s]|本案系|本案|系|属|为|因|由/);
  const stem = parts[parts.length - 1];
  return stem ? `${stem}纠纷` : raw;
}

/**
 * OCR 识别字段 → 新建案件表单映射。
 * 规则：案号→case_number；法院→court；案由去“纠纷”后缀→cause；
 * 开庭时间归一月日→hearing_date；对方当事人优先取「被告」，仅识别到「原告」时取原告（名称内 OCR 空格噪音清洗）；
 * 我方角色：识别到被告→原告（我方起诉），仅识别到原告→被告（对方起诉我方）。
 */
export function mapFieldsToCaseForm(fields: Record<string, string | null>): ScanCaseMapping {
  const caseNumber = fields["案号"] || "";
  const court = fields["法院"] || "";
  const causeRaw = extractCause(fields["案由"] || "");
  const hearingDate = normalizeHearingDate(fields["开庭时间"]);
  const defendant = fields["被告"] || "";
  const plaintiff = fields["原告"] || "";
  const opposingParty = (defendant || plaintiff || "").replace(/\s+/g, "");
  const ourRole = defendant ? "原告" : plaintiff ? "被告" : "原告";
  return {
    case_number: caseNumber,
    court,
    cause: causeRaw ? causeRaw.replace(/纠纷$/, "") : "",
    hearing_date: hearingDate,
    opposing_party: opposingParty,
    our_role: ourRole,
  };
}