/* 03-案件详情（docs/02 §4.3 + plan t08-10）。
   路由 /cases/:recordId；五区布局：头部卡 + 案件当事人/金额/司法程序/知识 + 侧栏(时间轴/歌曲/系列案)；
   raw 档案对照抽屉 + audit 审计抽屉 + 打标/导出/单条刷新（P0 只读：写操作仅此三项）。 */
import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, CalendarDays, CheckCircle2, Download, FileText, Inbox, RefreshCw,
  ScrollText, Share2, Tag,
} from "lucide-react";
import { Drawer } from "@/components/Drawer";
import SimilarPanel from "@/components/SimilarPanel";
import { Alert, Badge, EnumBadge, PageError, PageHeader, Spinner, Tooltip } from "@/components/common";
import { useCaseDetail, useMetadata } from "@/hooks";
import { api } from "@/lib/api";
import { downloadBlob, fmtByType, fmtDate, fmtDateTime, fmtMoney, fmtNum, fmtPct, fmtText } from "@/lib/format";
import { enumTone, resolveTone, statusTone } from "@/lib/colors";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- 静态元数据兜底 */

/* 48 字段中文 label 兜底（与 backend CASE_FIELD_META 一致；metadata 就绪后优先用其 label） */
const LABEL: Record<string, string> = {
  id: "内部 ID", record_id: "同步键", case_no: "案号", case_no_raw: "案号（原始）",
  case_no_ext: "合并拆分案号", related_case_no: "关联案号", case_status: "案件状态",
  court_date: "最近开庭", merged_count: "合并案件数", year: "收案年份", year_raw: "收案年份（原始）",
  accept_date: "收案时间", plaintiff: "原告", plaintiff_raw: "原告（原始）", defendant: "被告",
  defendant_raw: "被告（原始）", other_parties: "其他当事人", cause: "案由", court: "管辖法院",
  arbitration_org: "仲裁机构", court_raw: "法院（原始）", amount: "标的金额", song_count: "涉案歌曲数",
  artist: "艺人", per_song_amount: "单曲判赔", doc1_date: "一审文书时间", doc2_date: "二审文书时间",
  resolve: "结案原因", resolve_detail: "具体结案原因", payer: "支付主体", support_rate: "对方诉求支持率",
  pay_date: "支付时间", pay_amount: "支付总金额", case_owner: "负责人 id", case_owner_name: "案件负责人",
  lawyer_fee: "律师代理费", notes: "办案笔记", close_date: "结案日期", exec_case_no: "执行案号",
  judge_info: "承办法官", judge_name: "法官（提取）", biz_line: "业务线", parent_record_id: "系列案父记录",
  remark: "备注", withdraw_user: "撤卷申请人", synced_at: "同步时间", dirty_flags: "脏标记",
  created_at: "创建时间", updated_at: "更新时间",
};

/* Formula 字段（docs/02 §4.3：F 徽标 → tooltip 公式字段） */
const FORMULA = new Set(["song_count", "per_song_amount", "support_rate"]);

/* 金额字段（fmtByType num→fmtMoney 会误伤 year 等纯数字，故显式区分） */
const MONEY_KEYS = new Set(["amount", "pay_amount", "per_song_amount"]);

/* 五区字段分组（key → 区） */
const GROUP_ONE = ["related_case_no", "case_no_ext", "other_parties", "cause", "court", "arbitration_org", "merged_count", "year", "biz_line"];
const GROUP_THREE = ["case_status", "court_date", "doc1_date", "doc2_date", "resolve", "resolve_detail", "payer", "close_date"];
const GROUP_FOUR = ["case_owner_name", "judge_info", "judge_name", "notes", "withdraw_user", "exec_case_no", "remark"];

/* 时间轴节点 → 锚点区域 id（点击滚动 + 闪烁） */
const TL_NODES: { key: string; label: string; icon: typeof Inbox; anchor: string }[] = [
  { key: "accept_date", label: "收案", icon: Inbox, anchor: "sec-head" },
  { key: "doc1_date", label: "一审文书", icon: FileText, anchor: "sec-proc" },
  { key: "court_date", label: "开庭", icon: CalendarDays, anchor: "sec-proc" },
  { key: "doc2_date", label: "二审文书", icon: FileText, anchor: "sec-proc" },
  { key: "close_date", label: "结案", icon: CheckCircle2, anchor: "sec-proc" },
];

const IN_PROGRESS = /待判决|开庭|排期|审理/;

function toast(msg: string, isErr = false): void {
  window.dispatchEvent(new CustomEvent("lt:toast", { detail: isErr ? `⚠️ ${msg}` : msg }));
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function stamp(): string {
  return new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
}

/* 值渲染：金额 / 纯数字 / date / json / str 分流 */
function fmtField(k: string, v: unknown, type?: string): string {
  if (MONEY_KEYS.has(k)) return fmtMoney(v);
  if (type === "num") return fmtNum(v);
  return fmtByType(v, type ?? "str");
}

/* ---------------------------------------------------------------- 字段行 / 折叠列表 */

function FieldRow({
  label,
  value,
  children,
  formula,
  dirty,
  onClick,
  className,
}: {
  label: string;
  value?: ReactNode;
  children?: ReactNode;
  formula?: boolean;
  dirty?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <div className={cn("field", className)} onClick={onClick}>
      <div className="f-label">
        {label}
        {formula && (
          <span className="raw-ico" title="公式字段：显示飞书计算值，本地已复刻口径">F</span>
        )}
        {dirty && <span className="raw-ico" title="该字段已被清洗规则修正；原始值见「原始档案」">⚑</span>}
      </div>
      <div className="f-value">{children ?? value}</div>
    </div>
  );
}

/** 数组折叠：前 N 项 + "+N" 徽章，Tooltip 全列表 */
function FoldList({ values, limit = 2 }: { values: string[]; limit?: number }) {
  if (!values.length) return <span className="f-value" style={{ color: "var(--muted-2)", fontStyle: "italic" }}>—</span>;
  const head = values.slice(0, limit);
  const rest = values.slice(limit);
  return (
    <span className="f-value" style={{ display: "inline-flex", alignItems: "center", gap: 5, flexWrap: "wrap" }}>
      {head.map((v, i) => (
        <Badge key={i} tone="gray" dot={false}>{v}</Badge>
      ))}
      {rest.length > 0 && (
        <Tooltip label={<span>{values.map((v, i) => <div key={i} style={{ whiteSpace: "nowrap" }}>{v}</div>)}</span>}>
          <span className="badge badge-plain" style={{ cursor: "help" }}>+{rest.length}</span>
        </Tooltip>
      )}
    </span>
  );
}

/* ---------------------------------------------------------------- 主体 */

export default function CaseDetailPage() {
  const { recordId = "" } = useParams<{ recordId: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useCaseDetail(recordId);
  const { data: meta } = useMetadata();

  const fieldMeta = useMemo(() => new Map((meta?.fields ?? []).map((f) => [f.key, f])), [meta]);
  const labelOf = (k: string) => fieldMeta.get(k)?.label ?? LABEL[k] ?? k;
  const typeOf = (k: string) => fieldMeta.get(k)?.type;

  /* 抽屉 / 操作状态 */
  const [auditOpen, setAuditOpen] = useState(false);
  const [tagOpen, setTagOpen] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const [rawOpen, setRawOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [flashSec, setFlashSec] = useState<string | null>(null);
  const [tab, setTab] = useState<"detail" | "similar">("detail");

  /* 时间轴点击 → 锚点滚动 + 闪烁 1 次 */
  useEffect(() => {
    if (!flashSec) return;
    const t = setTimeout(() => setFlashSec(null), 2200);
    return () => clearTimeout(t);
  }, [flashSec]);

  const scrollTo = (anchor: string) => {
    setFlashSec(anchor);
    document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const is404 = isError && !!error && (error as { status?: number }).status === 404;
  const dataStale = useMemo(() => {
    const synced = data?.base?.synced_at as number | string | null | undefined;
    if (typeof synced !== "number" || !Number.isFinite(synced)) return false;
    return Date.now() - synced > 48 * 3600_000;
  }, [data]);

  /* ---------------------------------------------------------------- 操作 */

  const doExport = async () => {
    setExporting(true);
    try {
      const blob = await api.exportCsv({ scope: "case", ids: [recordId], with_footnote: true });
      downloadBlob(blob, `litigation_case_${recordId}_${stamp()}.csv`);
      toast("已导出本案件（CSV 含口径脚注）");
    } catch (e) {
      toast(errMsg(e), true);
    } finally {
      setExporting(false);
    }
  };

  const doRefresh = async () => {
    setRefreshing(true);
    try {
      await api.syncRun({ type: "record", id: recordId });
      toast("已触发单条刷新，稍后自动更新");
      setTimeout(() => void refetch(), 1500);
    } catch (e) {
      toast(errMsg(e), true);
    } finally {
      setRefreshing(false);
    }
  };

  const doTag = async () => {
    const tag = tagInput.trim();
    if (!tag) {
      toast("请输入标签内容", true);
      return;
    }
    try {
      const r = await api.caseBatch({ ids: [recordId], action: "tag", tag });
      toast(`已打标 ${r.data?.linked ?? 1} 件「${tag}」`);
      setTagOpen(false);
      setTagInput("");
    } catch (e) {
      toast(errMsg(e), true);
    }
  };

  /* ---------------------------------------------------------------- 渲染 */

  if (isLoading) return <Spinner label="案件详情加载中…" />;
  if (is404) {
    return (
      <div>
        <PageHeader title="案件详情" breadcrumb="该案件不存在或已被归档" />
        <div className="empty" style={{ padding: "48px 0" }}>
          <div className="e-ico">🗂</div>
          <div className="e-title">该案件不存在或已被归档</div>
          <div className="e-desc">同步键 {recordId} 未能匹配任何案件记录</div>
          <button type="button" className="btn btn-primary" onClick={() => navigate("/search")}>
            <ArrowLeft size={13} /> 返回检索
          </button>
        </div>
      </div>
    );
  }
  if (isError || !data) return <PageError message="案件详情加载失败" onRetry={() => void refetch()} />;

  const base = data.base;
  const raw = data.raw;
  const audit = data.audit ?? [];
  const songs = data.songs ?? [];
  const siblings = data.series?.siblings ?? [];
  const dirtyFlags = Array.isArray(base.dirty_flags) ? (base.dirty_flags as string[]) : [];
  const dirtyCount = dirtyFlags.length;

  const caseNo = fmtText(base.case_no);
  const status = base.case_status as string | null | undefined;
  const biz = base.biz_line as string | null | undefined;
  const rt = resolveTone(base.resolve as string | null | undefined);

  /* 判决胜负 banner（视觉锚点，docs/02 §4.3） */
  let banner: { tone: "green" | "red" | "gray"; text: string } | null = null;
  const resolve = base.resolve as string | null | undefined;
  if (resolve) {
    if (rt === "green") banner = { tone: "green", text: `胜诉定性：${fmtText(base.resolve_detail ?? resolve)}` };
    else if (rt === "red") {
      const amt = fmtMoney(base.pay_amount ?? base.amount);
      banner = { tone: "red", text: `判决判赔 ${amt}` };
    } else banner = { tone: "gray", text: `结案原因：${fmtText(base.resolve_detail ?? resolve)}` };
  }

  const BANNER_STYLE: Record<"green" | "red" | "gray", CSSProperties> = {
    green: { background: "var(--success-soft, #dcfce7)", color: "var(--success)", borderLeft: "4px solid var(--success)" },
    red: { background: "var(--danger-soft, #fee2e2)", color: "var(--danger)", borderLeft: "4px solid var(--danger)" },
    gray: { background: "var(--surface-2)", color: "var(--muted)", borderLeft: "4px solid var(--border)" },
  };

  /* 时间轴：有值节点推进；审理中以「开庭」为当前态 pulse */
  const inProgress = IN_PROGRESS.test(status ?? "");
  const lastIdx = TL_NODES.reduce<number>((acc, n, i) => {
    const v = base[n.key];
    return v !== null && v !== undefined && v !== "" ? i : acc;
  }, -1);
  const tlCls = (i: number) => {
    if (i < lastIdx) return "done";
    if (i === lastIdx && inProgress) return "now";
    return i <= lastIdx ? "done" : "";
  };

  const sr = base.support_rate as number | null | undefined;
  const srWidth =
    sr !== null && sr !== undefined && Number.isFinite(Number(sr))
      ? Math.min(100, Math.abs(Number(sr)) <= 1 ? Number(sr) * 100 : Number(sr))
      : 0;

  const rowsOf = (keys: string[]) =>
    keys
      .filter((k) => (base[k] !== null && base[k] !== undefined && base[k] !== "") || k === "support_rate")
      .map((k) => {
        const v = base[k];
        if (k === "support_rate") {
          return (
            <FieldRow
              key={k}
              label={labelOf(k)}
              formula
              value={
                sr === null || sr === undefined ? (
                  <span className="f-value" style={{ color: "var(--muted-2)", fontStyle: "italic" }}>—</span>
                ) : (
                  <span className="sup">
                    <span className="track">
                      <span className="fill" style={{ width: `${srWidth}%` }} />
                    </span>
                    <span className="val">{fmtPct(sr)}</span>
                  </span>
                )
              }
            />
          );
        }
        const isList = Array.isArray(v);
        const dirty = dirtyFlags.includes(k) || (isList && dirtyFlags.some((d) => String(d) === k));
        return (
          <FieldRow key={k} label={labelOf(k)} formula={FORMULA.has(k)} dirty={dirty || undefined}>
            {k === "cause" || k === "cost" ? fmtText(v) : isList ? <FoldList values={(v as unknown[]).map(String)} /> : fmtField(k, v, typeOf(k))}
          </FieldRow>
        );
      });

  const plaintiff = Array.isArray(base.plaintiff) ? (base.plaintiff as unknown[]).map(String) : base.plaintiff ? [String(base.plaintiff)] : [];
  const defendants = (base.defendant as unknown[] | null | undefined) ?? [];
  const courts = (base.court as unknown[] | null | undefined) ?? [];
  const courtList = Array.isArray(courts) ? courts.map(String) : courts ? [String(courts)] : [];

  const auditTone = (op: string): "blue" | "amber" | "gray" | "green" =>
    op.startsWith("clean") ? "blue" : op.startsWith("sync") ? "amber" : op === "tag" ? "green" : "gray";
  const short = (v: unknown): string => {
    if (v === null || v === undefined || v === "") return "—";
    const s = Array.isArray(v) ? v.map(String).join("、") : String(v);
    return s.length > 60 ? `${s.slice(0, 58)}…` : s;
  };

  const rawRows = raw ? Object.entries(raw.fields ?? {}) : [];

  return (
    <div>
      <PageHeader
        title={caseNo}
        breadcrumb={
          <>
            检索结果 &gt; {caseNo} · 同步键 {base.record_id ?? recordId}
          </>
        }
        actions={
          <>
            <button type="button" className="btn btn-sm" onClick={() => navigate("/search")}>
              <ArrowLeft size={13} /> 返回检索
            </button>
          </>
        }
      />

      {/* 视图切换：案件详情 | 相似案（F4.2 同质案类推） */}
      <div style={{ marginBottom: 12 }}>
        <div className="seg" role="tablist" aria-label="案件视图">
          <button type="button" className={tab === "detail" ? "seg-item active" : "seg-item"} role="tab" aria-selected={tab === "detail"} onClick={() => setTab("detail")}>
            案件详情
          </button>
          <button type="button" className={tab === "similar" ? "seg-item active" : "seg-item"} role="tab" aria-selected={tab === "similar"} onClick={() => setTab("similar")}>
            相似案
          </button>
        </div>
      </div>

      {tab === "similar" ? (
        <SimilarPanel caseId={recordId} />
      ) : (
        <>
      {dataStale && (
        <div style={{ marginBottom: 12 }}>
          <Alert kind="amber">
            同步于 48 小时前（{fmtDateTime(base.synced_at)}），数据可能陈旧；可点「刷新本案件」拉取飞书最新值。
          </Alert>
        </div>
      )}

      {/* 头部卡（锚点 sec-head） */}
      <div className="card card-pad" id="sec-head" style={{ ...(flashSec === "sec-head" ? { outline: "2px solid var(--primary)", outlineOffset: 2 } : {}) }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ fontSize: 17, fontWeight: 600, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              {caseNo}
              {dirtyCount > 0 && (
                <Badge tone="amber">{dirtyCount} 项待清洗</Badge>
              )}
            </div>
            <div style={{ fontSize: 12, color: "var(--muted-2)", marginTop: 4 }}>
              {biz && <EnumBadge tone={enumTone(bizColorOf(biz))} style={{ marginRight: 6 }}>{biz}</EnumBadge>}
              <Badge tone={statusTone(status)}>{status ?? "未知"}</Badge>
              <span style={{ marginLeft: 10 }}>收案 {fmtDate(base.accept_date)}</span>
              <span style={{ marginLeft: 10 }}>案由 {fmtText(base.cause)}</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-sm" disabled={exporting} onClick={() => void doExport()}>
              <Download size={13} /> 导出
            </button>
            <button type="button" className="btn btn-sm" onClick={() => setTagOpen(true)}>
              <Tag size={13} /> 打标
            </button>
            <button type="button" className="btn btn-sm" disabled={refreshing} onClick={() => void doRefresh()}>
              <RefreshCw size={13} /> 刷新
            </button>
            <button type="button" className="btn btn-sm" onClick={() => setAuditOpen(true)}>
              <ScrollText size={13} /> 审计
            </button>
            <button type="button" className="btn btn-sm" onClick={() => setRawOpen(true)}>
              <Share2 size={13} /> 原始档案
            </button>
          </div>
        </div>

        {/* 判决胜负 banner（详情页视觉锚点） */}
        {banner && (
          <div style={{ ...BANNER_STYLE[banner.tone], borderRadius: 6, padding: "8px 12px", marginTop: 12, fontSize: 13, fontWeight: 500 }}>
            {banner.text}
          </div>
        )}

        {/* 当事人行 */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 8, marginTop: 12 }}>
          <div className="field">
            <div className="f-label">原告</div>
            <FoldList values={plaintiff} />
          </div>
          <div className="field">
            <div className="f-label">被告</div>
            <FoldList values={defendants.map(String)} />
          </div>
          <div className="field">
            <div className="f-label">管辖法院</div>
            <FoldList values={courtList} />
          </div>
        </div>
      </div>

      {/* 主区 2/3 + 侧栏 1/3 */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)", gap: 14, marginTop: 14, alignItems: "start" }}>
        <div style={{ display: "grid", gap: 14 }}>
          {/* ① 案件与当事人 */}
          <div className="card card-pad">
            <div className="card-title">
              ① 案件与当事人
              <span className="sub">案由 / 管辖 / 合并 / 系列案归属</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "10px 18px" }}>
              {rowsOf(GROUP_ONE)}
            </div>
          </div>

          {/* ② 金额区（三兄弟 + 支持率） */}
          <div className="card card-pad" id="sec-amount">
            <div className="card-title">
              ② 金额与赔付
              <span className="sub">口径 v1.0 · 公式值 = 飞书计算值</span>
            </div>
            <div className="stat-row" style={{ marginBottom: 4 }}>
              <StatCardMini label="标的金额" value={fmtMoney(base.amount)} hint="原告起诉标的（飞书原值）" />
              <StatCardMini label="支付总金额" value={fmtMoney(base.pay_amount)} hint="结案后实际支付合计（口径 v1.0）" />
              <StatCardMini label="单曲判赔" value={fmtMoney(base.per_song_amount)} hint="公式字段：支付金额 ÷ 涉案歌曲数" formula />
            </div>
            <div className="field" style={{ maxWidth: 320 }}>
              <div className="f-label">
                对方诉求支持率
                <span className="raw-ico" title="公式字段：对方诉求被支持金额 / 标的金额">F</span>
              </div>
              {sr === null || sr === undefined ? (
                <span className="f-value" style={{ color: "var(--muted-2)", fontStyle: "italic" }}>—（该字段飞书侧为空）</span>
              ) : (
                <span className="sup">
                  <span className="track">
                    <span className="fill" style={{ width: `${srWidth}%` }} />
                  </span>
                  <span className="val">{fmtPct(sr)}</span>
                </span>
              )}
            </div>
          </div>

          {/* ③ 司法程序 */}
          <div className="card card-pad" id="sec-proc" style={{ ...(flashSec === "sec-proc" ? { outline: "2px solid var(--primary)", outlineOffset: 2 } : {}) }}>
            <div className="card-title">
              ③ 司法程序
              <span className="sub">状态 / 文书 / 结案归因</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "10px 18px" }}>
              {rowsOf(GROUP_THREE)}
            </div>
          </div>

          {/* ④ 知识区 */}
          <div className="card card-pad">
            <div className="card-title">
              ④ 办案知识
              <span className="sub">负责人 / 法官 / 笔记 / 备注</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "10px 18px" }}>
              {rowsOf(GROUP_FOUR)}
            </div>
          </div>
        </div>

        {/* 侧栏 */}
        <div style={{ display: "grid", gap: 14 }}>
          {/* ④ 时间轴 */}
          <div className="card card-pad">
            <div className="card-title">
              ④ 案件时间轴
              <span className="sub">节点可点 → 跳转对应字段卡</span>
            </div>
            <div className="timeline" style={{ marginTop: 10 }}>
              {TL_NODES.map((n, i) => {
                const v = base[n.key];
                const Icon = n.icon;
                const has = v !== null && v !== undefined && v !== "";
                return (
                  <div key={n.key} className={cn("tl-node", tlCls(i), has && "done")} style={{ cursor: has ? "pointer" : "default" }} onClick={() => has && scrollTo(n.anchor)}>
                    <div className="tl-label">
                      <Icon size={11} style={{ verticalAlign: "-1px", marginRight: 4 }} />
                      {n.label}
                      {i === lastIdx && inProgress && <span className="badge badge-plain" style={{ marginLeft: 6 }}>当前</span>}
                    </div>
                    {has ? <div className="tl-date">{fmtDate(v)}</div> : <div className="tl-empty">— 无记录</div>}
                  </div>
                );
              })}
            </div>
          </div>

          {/* ⑤ 关联歌曲 */}
          <div className="card card-pad">
            <div className="card-title">
              ⑤ 涉及歌曲
              <span className="sub">
                本案涉 <b>{fmtNum(base.song_count ?? songs.length)}</b> 首
              </span>
            </div>
            {songs.length > 0 ? (
              <table className="tbl">
                <thead>
                  <tr>
                    <th>歌曲</th>
                    <th>艺人</th>
                    <th style={{ textAlign: "right" }}>判赔分摊</th>
                  </tr>
                </thead>
                <tbody>
                  {songs.map((s) => (
                    <tr key={s.record_id}>
                      <td>{fmtText(s.song_name)}</td>
                      <td className="muted">{fmtText(s.artist)}</td>
                      <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {perSong(base)}<span className="muted" style={{ fontSize: 11 }}> × 1 首</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty" style={{ padding: "22px 0" }}>本案件未关联歌曲</div>
            )}
          </div>

          {/* ⑤ 系列案 */}
          <div className="card card-pad">
            <div className="card-title">
              ⑤ 系列案
              <span className="sub">{siblings.length > 0 ? `同组 ${siblings.length} 件` : base.parent_record_id ? "已归组" : "未归组"}</span>
            </div>
            {base.parent_record_id || (data.series?.related_case_no ?? null) ? (
              <div className="alert blue" style={{ marginBottom: 8, fontSize: 12 }}>
                <Share2 size={13} />
                <span>属于系列案组：{fmtText(data.series?.related_case_no ?? base.parent_record_id)}</span>
              </div>
            ) : null}
            {siblings.length > 0 ? (
              <table className="tbl">
                <thead>
                  <tr>
                    <th>案号</th>
                    <th>年份</th>
                    <th>结案原因</th>
                  </tr>
                </thead>
                <tbody>
                  {siblings.map((s) => (
                    <tr key={s.record_id} style={{ cursor: "pointer" }} onClick={() => navigate(`/cases/${s.record_id}`)}>
                      <td className="link" style={{ color: "var(--primary)" }}>{fmtText(s.case_no)}</td>
                      <td className="muted">{fmtNum(s.year)}</td>
                      <td><Badge tone={resolveTone(s.resolve)} dot={false}>{fmtText(s.resolve)}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : base.parent_record_id ? (
              <div className="empty" style={{ padding: "18px 0", fontSize: 12 }}>同组暂无其他案件</div>
            ) : (
              <div className="empty" style={{ padding: "18px 0", fontSize: 12 }}>独立案件（未归组）</div>
            )}
          </div>
        </div>
      </div>

      {/* 打标抽屉 */}
      <Drawer title="给本案件打标签" open={tagOpen} onClose={() => setTagOpen(false)} foot={<>
        <button type="button" className="btn btn-sm" onClick={() => setTagOpen(false)}>取消</button>
        <button type="button" className="btn btn-sm btn-primary" onClick={() => void doTag()}>确认打标</button>
      </>}>
        <label className="f-label" style={{ marginBottom: 6 }}>标签内容（如「二审可能」；支持重复标签类目，打标幂等）</label>
        <input
          value={tagInput}
          onChange={(e) => setTagInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void doTag()}
          placeholder="输入标签后回车"
          style={{ width: "100%" }}
          autoFocus
        />
        <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>打标记录进入审计日志；标签可用于检索（Phase 2 标签检索）。</div>
      </Drawer>

      {/* 审计抽屉 */}
      <Drawer title="记录审计（最近 20 条）" open={auditOpen} onClose={() => setAuditOpen(false)}>
        {audit.length > 0 ? (
          <div style={{ display: "grid", gap: 8 }}>
            {audit.map((a) => (
              <div key={a.id} className="card-pad" style={{ background: "var(--surface-2)", borderRadius: 6, padding: "8px 10px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <EnumBadge tone={auditTone(a.op_type)}>{a.op_type}</EnumBadge>
                  {a.rule_tag && <span className="muted" style={{ fontSize: 11 }}>{a.rule_tag}@{a.rule_version ?? "-"}</span>}
                  <span className="muted" style={{ fontSize: 11, marginLeft: "auto" }}>{fmtDateTime(a.created_at)}</span>
                </div>
                {a.field && (
                  <div style={{ fontSize: 12, marginTop: 4 }}>
                    <b>{labelOf(a.field)}</b>（{a.action}）：<span className="muted">{short(a.old_value)}</span>
                    <span style={{ color: "var(--muted-2)" }}> → </span>
                    <span style={{ color: "var(--primary)" }}>{short(a.new_value)}</span>
                  </div>
                )}
                {a.operator && <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>操作人：{a.operator}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="empty" style={{ padding: "28px 0" }}>暂无审计记录（同步/清洗/导出在此留痕）</div>
        )}
      </Drawer>

      {/* 原始档案抽屉 */}
      <Drawer title="飞书原始档案（raw 整包留档）" open={rawOpen} onClose={() => setRawOpen(false)}>
        {raw ? (
          <>
            <div className="alert blue" style={{ fontSize: 12, marginBottom: 10 }}>
              <Share2 size={13} />
              <span>同步于 {fmtDateTime(raw.synced_at)} · 共 {rawRows.length} 个字段（飞书原始字段名与规范 key 不一定一致）</span>
            </div>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: "42%" }}>飞书字段</th>
                  <th>原始值</th>
                </tr>
              </thead>
              <tbody>
                {rawRows.slice(0, 200).map(([k, v]) => (
                  <tr key={k}>
                    <td className="muted" style={{ fontSize: 12 }}>{k}</td>
                    <td style={{ wordBreak: "break-all", fontSize: 12 }}>{short(v)}</td>
                  </tr>
                ))}
                {rawRows.length > 200 && (
                  <tr>
                    <td colSpan={2} className="muted" style={{ textAlign: "center" }}>其余 {rawRows.length - 200} 个字段已截断（前端展示限制）</td>
                  </tr>
                )}
              </tbody>
            </table>
          </>
        ) : (
          <div className="empty" style={{ padding: "28px 0" }}>无原始留档（该记录未进入同步留档案）</div>
        )}
      </Drawer>
        </>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- 小组件 */

function StatCardMini({ label, value, hint, formula }: { label: string; value: string; hint?: string; formula?: boolean }) {
  return (
    <div className="stat-card" style={{ background: "var(--surface-2)", borderRadius: 8, padding: "10px 14px" }}>
      <div className="stat-label" style={{ fontSize: 11 }}>
        {label}
        {formula && <span className="raw-ico" title="公式字段：显示飞书计算值，本地已复刻口径">F</span>}
        {hint && !formula && <span className="help" title={hint}>ⓘ</span>}
      </div>
      <div className="stat-value" style={{ fontSize: 18 }}>{value}</div>
    </div>
  );
}

const bizColorOf = (_biz: string) => null; /* 业务线色 = metadata enum color；此处由调用方 EnumBadge 兜底灰 */

function perSong(b: Record<string, unknown>): string {
  return fmtMoney(b.per_song_amount);
}