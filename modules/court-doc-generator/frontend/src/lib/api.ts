/** API 客户端（代理到 FastAPI 后端）。 */

export const API_BASE = "/api/v1";
const BASE = API_BASE;

function authHeaders(): Record<string, string> {
  const id = sessionStorage.getItem("_ws_id");
  return id ? { "X-Workspace-Id": id } : {};
}

async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(opts?.headers as Record<string, string> || {}),
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || data.detail || "请求失败");
  return data as T;
}

// ── 认证 ────────────────────────────────────────────────────────────────
export const authApi = {
  login: (name: string, password: string) =>
    api<{ workspace_id: string; workspace_name: string; token: string }>(
      "/auth/login", {
        method: "POST",
        body: JSON.stringify({ name, password }),
      }
    ),
  register: (name: string, password: string) =>
    api<{ workspace_id: string; workspace_name: string; token: string }>(
      "/auth/register", {
        method: "POST",
        body: JSON.stringify({ name, password }),
      }
    ),
  listWorkspaces: () =>
    api<Array<{ id: string; name: string; created_at: string }>>("/auth/list"),
};

// ── 公司 ────────────────────────────────────────────────────────────────
export interface Company {
  id: number;
  name: string;
  credit_code: string;
  legal_rep_name: string;
  legal_rep_position: string;
  legal_rep_id_card: string;
  address: string;
  phone: string;
  // 文件路径
  business_license_path: string;
  legal_rep_id_card_path: string;
  legal_rep_cert_path: string;
  power_of_attorney_path: string;
  recommendation_path: string;
}

export const companyApi = {
  list: () => api<Company[]>("/companies"),
  create: (body: Omit<Company, "id">) => api<Company>("/companies", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  delete: (id: number) => api("/companies/" + id, { method: "DELETE" }),
  uploadFiles: async (companyId: number, formData: FormData): Promise<{ ok: boolean; updated: string[] }> => {
    const wsId = sessionStorage.getItem("_ws_id") || "";
    const res = await fetch(`/api/v1/companies/${companyId}/upload`, {
      method: "PUT",
      headers: { "X-Workspace-Id": wsId },
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "上传失败");
    return data;
  },
};

// ── 代理人 ─────────────────────────────────────────────────────────────
export interface Agent {
  id: number;
  name: string;
  position: string;
  phone: string;
  id_card: string;
  labor_contract: string;
  company_id: number | null;
  is_default: number;
  company_name: string | null;
}

export const agentApi = {
  list: () => api<Agent[]>("/agents"),
  create: (body: Omit<Agent, "id" | "id_card" | "labor_contract" | "company_name">) =>
    api<Agent>("/agents", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: number) => api("/agents/" + id, { method: "DELETE" }),
};

// ── 案件 ────────────────────────────────────────────────────────────────
export interface Case {
  id: number;
  case_number: string;
  court: string;
  cause: string;
  hearing_date: string;
  opposing_party: string;
  our_role: string;
  company_id: number | null;
  agent_id: number | null;
  status: string;
  created_at: string;
}

export const caseApi = {
  list: (filters?: Record<string, string>) => {
    const qs = filters
      ? "?" + Object.entries(filters)
          .filter(([, v]) => v !== undefined && v !== null && v !== "")
          .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
          .join("&")
      : "";
    return api<Case[]>(`/cases${qs}`);
  },
  create: (body: Omit<Case, "id" | "status" | "created_at">) =>
    api<Case>("/cases", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: number) => api("/cases/" + id, { method: "DELETE" }),
};

// ── 预设库（法院/案由）─────────────────────────────────────────────────
export interface Preset {
  id: number;
  kind: string;
  value: string;
  usage_count: number;
  created_at: string;
}

export const presetApi = {
  list: (kind: string) => api<Preset[]>(`/presets?kind=${kind}`),
  create: (kind: string, value: string) =>
    api<Preset>("/presets", { method: "POST", body: JSON.stringify({ kind, value }) }),
  bump: (id: number) => api("/presets/" + id + "/bump", { method: "POST" }),
  delete: (id: number) => api("/presets/" + id, { method: "DELETE" }),
};

// ── 生成 ────────────────────────────────────────────────────────────────
export interface GenerateResult {
  output_dir: string;
  files: string[];
  merged_pdf: string | null;
}

export const generateApi = {
  generate: (case_id: number, company_id: number, agent_id: number) =>
    api<GenerateResult>("/generate", {
      method: "POST",
      body: JSON.stringify({ case_id, company_id, agent_id }),
    }),
};

// ── 历史 ───────────────────────────────────────────────────────────────
export interface History {
  id: number;
  case_id: number;
  workspace_id: string;
  output_dir: string;
  created_at: string;
}

export const historyApi = {
  list: () => api<History[]>("/history"),
  delete: (id: number) => api("/history/" + id, { method: "DELETE" }),
  listFiles: (id: number) =>
    api<Array<{ name: string; path: string; size: number; is_pdf: boolean }>>(
      "/history/" + id + "/files"
    ),
  downloadZip: (id: number) => {
    const wsId = sessionStorage.getItem("_ws_id") || "";
    const token = sessionStorage.getItem("_token") || "";
    return `${BASE}/history/${id}/download-zip`;
  },
};

// ── 操作日志 ─────────────────────────────────────────────────────────────
export interface AuditLog {
  id: number;
  username: string;
  action: string;
  target: string;
  result: string;
  created_at: string;
}

export const auditApi = {
  list: (limit = 100, offset = 0) =>
    api<AuditLog[]>(`/audit-logs?limit=${limit}&offset=${offset}`),
};

// ── 文件服务（直接 URL，支持 ?ws= query 参数）───────────────────────────────────
export function fileUrl(relativePath: string): string {
  const wsId = sessionStorage.getItem("_ws_id") || "";
  return `${BASE}/files/${relativePath}?ws=${wsId}`;
}
