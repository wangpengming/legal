/* 10-数据同步（docs/02 §8 + plan t08-10）。
   手动触发 full / incremental / record（record 需同步键）；状态 30s 轮询 + 触发后即时 invalidate；
   底部分页日志表 50 条。P0 只读之外少数写操作页。 */
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Activity, Database, Play, RefreshCw, ServerCog, Timer, Zap } from "lucide-react";
import { Alert, Badge, EmptyState, PageHeader, Spinner, SyncBar } from "@/components/common";
import { useSyncLogs, useSyncStatus } from "@/hooks";
import { api } from "@/lib/api";
import { fmtDateTime, fmtNum, fmtText } from "@/lib/format";

const JOB_TYPES = [
  { type: "full" as const, label: "全量同步", desc: "拉取飞书全表记录，幂等 upsert（首次建库 / 重灌用）", icon: Database },
  { type: "incremental" as const, label: "增量同步", desc: "按 updated_at 增量拉取，APScheduler 日常调度默认模式", icon: Zap },
  { type: "record" as const, label: "单条刷新", desc: "按同步键刷新单条记录（案件详情页「刷新」同款）", icon: RefreshCw },
];

function toast(msg: string, isErr = false): void {
  window.dispatchEvent(new CustomEvent("lt:toast", { detail: isErr ? `⚠️ ${msg}` : msg }));
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export default function SyncPage() {
  const qc = useQueryClient();
  const status = useSyncStatus();
  const logs = useSyncLogs(50);
  const [running, setRunning] = useState<string | null>(null);
  const [recordId, setRecordId] = useState("");

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["sync-status"] });
    void qc.invalidateQueries({ queryKey: ["sync-logs"] });
    void qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const doRun = async (type: "full" | "incremental" | "record") => {
    if (type === "record" && !recordId.trim()) {
      toast("请输入同步键（record_id）", true);
      return;
    }
    setRunning(type);
    try {
      const r = await api.syncRun(type === "record" ? { type, id: recordId.trim() } : { type });
      toast(r.data?.job_type ? `已触发${cone(type)}：${String(r.data.job_type)}` : `已触发${cone(type)}`);
      invalidate();
    } catch (e) {
      toast(errMsg(e), true);
    } finally {
      setRunning(null);
    }
  };

  const sd = status.data;
  const last = sd?.last;
  const nowRunning = sd?.running ?? false;

  return (
    <div>
      <PageHeader
        title="数据同步"
        breadcrumb={<>飞书多维表 → 本地 SQLite（WAL + FTS5）· 幂等 upsert · APScheduler 定时 · 30s 轮询</>}
      />

      {/* 同步状态条 */}
      {sd ? (
        <SyncBar kind={nowRunning ? "err" : "ok"} icon={nowRunning ? <Activity size={15} /> : <ServerCog size={15} />}>
          {nowRunning
            ? `同步任务运行中（job #{sd.running_job_id}）… 完成后自动刷新`
            : `就绪 · 上次：${last ? `${jobLabel(last.type)} ${last.status}` : "尚无记录"} · 下次定时：${fmtDateTime(sd.next_at)}`}
        </SyncBar>
      ) : (
        <div className="skeleton" style={{ height: 40, borderRadius: 8 }} />
      )}

      {sd && !sd.feishu_configured && (
        <div style={{ marginTop: 12 }}>
          <Alert kind="amber">未配置飞书凭证（FEISHU_* 环境变量），手动触发将返回 503；配置后即可正常同步。</Alert>
        </div>
      )}

      {/* 上次任务详情 + 手动触发三卡 */}
      <div className="stat-row" style={{ marginTop: 16 }}>
        {JOB_TYPES.map((jt) => {
          const Icon = jt.icon;
          const isRun = running === jt.type;
          return (
            <div key={jt.type} className="card card-pad" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Icon size={15} style={{ color: "var(--primary)" }} />
                <span style={{ fontWeight: 600, fontSize: 13 }}>{jt.label}</span>
              </div>
              <div className="muted" style={{ fontSize: 12, flex: 1 }}>{jt.desc}</div>
              {jt.type === "record" && (
                <input
                  value={recordId}
                  onChange={(e) => setRecordId(e.target.value)}
                  placeholder="同步键（record_id）"
                  style={{ width: "100%" }}
                />
              )}
              <button
                type="button"
                className="btn btn-sm btn-primary"
                disabled={isRun || nowRunning}
                onClick={() => void doRun(jt.type)}
              >
                <Play size={12} /> {isRun ? "触发中…" : `触发${jt.label}`}
              </button>
            </div>
          );
        })}
      </div>

      {/* 上次任务 */}
      {last && (
        <div className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            上次任务 <span className="sub">job #{last.id} · {jobLabel(last.type)}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, marginTop: 8 }}>
            <Mini label="状态" value={last.status} />
            <Mini label="总记录" value={fmtNum(last.total)} />
            <Mini label="新增/更新" value={fmtNum(last.upserted)} />
            <Mini label="跳过" value={fmtNum(last.skipped)} />
            {last.deleted !== undefined && last.deleted !== null && <Mini label="删除" value={fmtNum(last.deleted)} />}
            <Mini label="开始" value={fmtDateTime(last.started_at)} />
            <Mini label="结束" value={fmtDateTime(last.finished_at)} />
          </div>
          {last.error_brief && (
            <div style={{ marginTop: 8 }}>
              <Alert kind="red">{fmtText(last.error_brief)}</Alert>
            </div>
          )}
        </div>
      )}

      {/* 日志表 */}
      <div className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          同步日志 <span className="sub">最近 {logs.data?.length ?? 0} 条（limit 50 · 刷新后自动更新）</span>
        </div>
        {logs.isLoading ? (
          <Spinner label="日志加载中…" />
        ) : !logs.data || logs.data.length === 0 ? (
          <EmptyState icon={<Timer size={18} />} title="暂无同步日志" desc="触发同步任务后在此留痕" />
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>#</th>
                  <th>类型</th>
                  <th>状态</th>
                  <th>总数</th>
                  <th>新增/更新</th>
                  <th>跳过</th>
                  <th>开始</th>
                  <th>结束</th>
                  <th>错误</th>
                </tr>
              </thead>
              <tbody>
                {logs.data.map((l) => (
                  <tr key={l.id}>
                    <td className="muted">{l.id}</td>
                    <td>{jobLabel(l.job_type)}</td>
                    <td>
                      <Badge tone={statusToneOf(l.status)} dot={false}>{l.status}</Badge>
                    </td>
                    <td className="num">{fmtNum(l.total)}</td>
                    <td className="num">{fmtNum(l.upserted)}</td>
                    <td className="num">{fmtNum(l.skipped)}</td>
                    <td className="muted">{fmtDateTime(l.started_at)}</td>
                    <td className="muted">{fmtDateTime(l.finished_at)}</td>
                    <td className="muted" style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{l.error_brief ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function cone(t: string): string {
  return JOB_TYPES.find((j) => j.type === t)?.label ?? t;
}

function jobLabel(t: string | null): string {
  if (!t) return "未知";
  return cone(t);
}

function statusToneOf(s: string): "green" | "amber" | "red" | "gray" {
  if (s === "success") return "green";
  if (s === "running" || s === "pending") return "amber";
  if (s === "failed") return "red";
  return "gray";
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: 11 }}>{label}</div>
      <div style={{ fontWeight: 500, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>{value}</div>
    </div>
  );
}