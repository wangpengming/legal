/* TanStack Query hooks（数据层统一入口，对齐 backend /api/v1 契约）。
   useSearch 返回完整 ApiRes（meta.footnote 需透出「命中数」口径）；
   其余返回 data。staleTime 按数据易变程度分级。 */

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AiChatPayload, type AnalysisDim, type AnalysisSel, type SearchRequest, type TagKind } from "@/lib/api";

/* 元数据驱动（枚举/字段/规则）——低频，长缓存 */
export function useMetadata() {
  return useQuery({
    queryKey: ["metadata"],
    queryFn: () => api.metadata().then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function useOverview() {
  return useQuery({
    queryKey: ["overview"],
    queryFn: () => api.overview().then((r) => r.data),
    staleTime: 60_000,
  });
}

/** 检索：key 含完整请求体，输入变化自动重取；开启分页骨架缓存。 */
export function useSearch(req: SearchRequest, enabled = true) {
  return useQuery({
    queryKey: ["search", req],
    queryFn: () => api.search(req),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useCaseDetail(id: string | undefined) {
  return useQuery({
    queryKey: ["case", id],
    queryFn: () => api.caseDetail(id!).then((r) => r.data),
    enabled: !!id,
  });
}

export function useCaseRaw(id: string | undefined) {
  return useQuery({
    queryKey: ["case-raw", id],
    queryFn: () => api.caseRaw(id!).then((r) => r.data),
    enabled: !!id,
  });
}

/* 同步状态：轮询 30s（配合 APScheduler 周期） */
export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync-status"],
    queryFn: () => api.syncStatus().then((r) => r.data),
    staleTime: 5_000,
    refetchInterval: 30_000,
  });
}

export function useSyncLogs(limit = 50) {
  return useQuery({
    queryKey: ["sync-logs", limit],
    queryFn: () => api.syncLogs(limit).then((r) => r.data),
    staleTime: 30_000,
  });
}

export function useDicts() {
  return useQuery({
    queryKey: ["dicts"],
    queryFn: () => api.dicts().then((r) => r.data),
    staleTime: 60_000,
  });
}

export function useDirtyItems() {
  return useQuery({
    queryKey: ["dirty-items"],
    queryFn: () => api.dictDirty().then((r) => r.data),
    staleTime: 30_000,
  });
}

/* Phase 2 统计页（占位页提前挂载，避免后续返工） */
export function useParties(limit = 20) {
  return useQuery({
    queryKey: ["parties", limit],
    queryFn: () => api.parties(limit).then((r) => r.data),
    staleTime: 60_000,
  });
}

export function useParty(name: string | undefined) {
  return useQuery({
    queryKey: ["party", name],
    queryFn: () => api.party(name!).then((r) => r.data),
    enabled: !!name,
  });
}

export function useBizline(year?: number) {
  return useQuery({
    queryKey: ["bizline", year ?? null],
    queryFn: () => api.bizline(year).then((r) => r.data),
    staleTime: 60_000,
  });
}

export function useSongs() {
  return useQuery({
    queryKey: ["songs"],
    queryFn: () => api.songs().then((r) => r.data),
    staleTime: 60_000,
  });
}

export function useFees(year?: number) {
  return useQuery({
    queryKey: ["fees", year ?? null],
    queryFn: () => api.fees(year).then((r) => r.data),
    staleTime: 60_000,
  });
}

/* ---- 05-analysis 多维分析 ---- */
export function useAnalysis(dim: AnalysisDim = "bizYear") {
  return useQuery({
    queryKey: ["analysis", dim],
    queryFn: () => api.analysis(dim).then((r) => r.data),
    staleTime: 60_000,
  });
}

export function useAnalysisDrill(dim: AnalysisDim, sel: AnalysisSel) {
  return useQuery({
    queryKey: ["analysisDrill", dim, sel],
    queryFn: () => api.analysisDrill(dim, sel).then((r) => r.data),
    enabled: !!sel.x,
    staleTime: 60_000,
  });
}

/* Phase 2 M4 标签（/tags） */
export function useTags(kind?: TagKind) {
  return useQuery({
    queryKey: ["tags", kind ?? null],
    queryFn: () => api.tags(kind).then((r) => r.data),
    staleTime: 30_000,
  });
}

export function useTagObjects(tagId: number | undefined) {
  return useQuery({
    queryKey: ["tag-objects", tagId],
    queryFn: () => api.tagObjects(tagId!).then((r) => r.data),
    enabled: tagId != null,
    staleTime: 30_000,
  });
}

/** 标签写操作：mutation 后统一失效 tags / tag-objects 缓存 */
export function useTagMutation() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["tags"] });
    qc.invalidateQueries({ queryKey: ["tag-objects"] });
  };
  return {
    create: useMutation({ mutationFn: api.tagCreate, onSuccess: invalidate }),
    update: useMutation({
      mutationFn: (vars: { id: number; name?: string; color?: string | null; description?: string | null }) =>
        api.tagUpdate(vars.id, vars),
      onSuccess: invalidate,
    }),
    remove: useMutation({ mutationFn: api.tagDelete, onSuccess: invalidate }),
    link: useMutation({ mutationFn: api.tagLink, onSuccess: invalidate }),
    batch: useMutation({ mutationFn: api.tagBatch, onSuccess: invalidate }),
    merge: useMutation({ mutationFn: api.tagMerge, onSuccess: invalidate }),
  };
}

/* Phase 3 F4.2 同质案类推 */
export function useSimilar(caseId: string | undefined) {
  return useQuery({
    queryKey: ["similar", caseId],
    queryFn: () => api.similar(caseId!).then((r) => r.data),
    enabled: !!caseId,
    staleTime: 60_000,
  });
}

/* Phase 3 Mode B 报告存档 */
export function useReports(page = 1, pageSize = 10, templateKey?: string) {
  return useQuery({
    queryKey: ["reports", page, pageSize, templateKey ?? null],
    queryFn: () => api.reports(page, pageSize, templateKey).then((r) => ({ list: r.data, meta: r.meta })),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}

export function useReportDetail(id: number | undefined) {
  return useQuery({
    queryKey: ["report-detail", id],
    queryFn: () => api.reportDetail(id!).then((r) => r.data),
    enabled: id != null,
    staleTime: 60_000,
  });
}

/** 报告生成/删除：mutation 后失效 reports 列表 */
export function useReportMutation() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["reports"] });
    qc.invalidateQueries({ queryKey: ["report-detail"] });
  };
  return {
    generate: useMutation({ mutationFn: api.reportGenerate, onSuccess: invalidate }),
    remove: useMutation({ mutationFn: api.reportDelete, onSuccess: invalidate }),
  };
}

/* Phase 3 AI Mode A/B 对话：mutation 每次发送，不在乎缓存 */
export function useAiChat() {
  return useMutation({
    mutationFn: (payload: AiChatPayload) => api.aiChat(payload).then((r) => r.data),
  });
}

export function useAiTemplates() {
  return useQuery({
    queryKey: ["ai-templates"],
    queryFn: () => api.aiTemplates().then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}