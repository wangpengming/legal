/** F6 操作日志页。 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { auditApi, AuditLog } from "../lib/api";

const ACTION_LABEL: Record<string, string> = {
  register: "注册",
  login: "登录",
  case_create: "新建案件",
  case_delete: "删除案件",
  generate: "生成材料",
  export: "导出数据",
};

export default function AuditLogsPage() {
  const [limit, setLimit] = useState(50);
  const { data: logs = [], isLoading } = useQuery<AuditLog[]>({
    queryKey: ["audit-logs", limit],
    queryFn: () => auditApi.list(limit),
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">📜 操作日志</h1>
        <div className="page-actions">
          <select
            className="form-input" style={{ width: "auto" }}
            value={limit}
            onChange={e => setLimit(Number(e.target.value))}
          >
            <option value={20}>20 条</option>
            <option value={50}>50 条</option>
            <option value={100}>100 条</option>
            <option value={200}>200 条</option>
          </select>
        </div>
      </div>

      <div className="card">
        {isLoading ? <div className="empty">加载中...</div>
          : logs.length === 0 ? <div className="empty"><div className="empty-icon"><ScrollText size={32} /></div>暂无操作记录</div>
          : (
            <table className="table">
              <thead>
                <tr><th>时间</th><th>用户</th><th>操作</th><th>对象</th><th>结果</th></tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{log.created_at || "—"}</td>
                    <td>{log.username}</td>
                    <td>{ACTION_LABEL[log.action] || log.action}</td>
                    <td style={{ wordBreak: "break-all" }}>{log.target || "—"}</td>
                    <td>
                      {log.result === "ok"
                        ? <span className="badge badge-ok">✅ 成功</span>
                        : <span className="badge badge-fail">❌ 失败</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </div>
    </div>
  );
}