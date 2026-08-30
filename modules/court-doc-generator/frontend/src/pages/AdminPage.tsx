import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ConfirmDialog from "../components/ConfirmDialog";

interface Workspace {
  id: string;
  name: string;
  created_at: string;
}

interface User {
  workspace_id: string;
  workspace_name: string;
  username: string;
  email: string;
  created_at: string;
}

const ADMIN_KEY = "_admin_token";

export default function AdminPage() {
  const navigate = useNavigate();
  const token = sessionStorage.getItem(ADMIN_KEY);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [tab, setTab] = useState<"workspaces" | "users">("workspaces");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDeleteWs, setConfirmDeleteWs] = useState<string | null>(null);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "密码错误");
      }
      const data = await res.json();
      sessionStorage.setItem(ADMIN_KEY, data.token);
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadData() {
    if (!token) return;
    try {
      const [wsRes, userRes] = await Promise.all([
        fetch("/api/v1/admin/workspaces", {
          headers: { "X-Admin-Token": token },
        }),
        fetch("/api/v1/admin/users", {
          headers: { "X-Admin-Token": token },
        }),
      ]);
      if (wsRes.ok) setWorkspaces(await wsRes.json());
      if (userRes.ok) setUsers(await userRes.json());
    } catch {}
  }

  if (!token) {
    return (
      <div style={{
        display: "flex", justifyContent: "center", alignItems: "center",
        height: "100vh", background: "#f5f5f5",
      }}>
        <div style={{
          background: "#fff", padding: 40, borderRadius: 12,
          boxShadow: "0 2px 12px rgba(0,0,0,0.1)", width: 360,
          textAlign: "center",
        }}>
          <h2 style={{ marginBottom: 24, color: "#333" }}>系统管理后台</h2>
          <form onSubmit={handleLogin}>
            <input
              type="password"
              placeholder="输入管理员密码"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={{
                width: "100%", padding: "12px 16px", fontSize: 16,
                border: "1px solid #ddd", borderRadius: 8,
                boxSizing: "border-box", marginBottom: 12,
              }}
              autoFocus
            />
            {error && (
              <div style={{ color: "#dc3545", fontSize: 13, marginBottom: 12 }}>
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%", padding: "12px", fontSize: 16,
                background: "#0d6efd", color: "#fff",
                border: "none", borderRadius: 8, cursor: "pointer",
              }}
            >
              {loading ? "验证中..." : "进入后台"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // 首次加载数据
  if (workspaces.length === 0 && users.length === 0) {
    loadData();
  }

  async function handleDelete(wsId: string) {
    setDeleting(wsId);
    try {
      const res = await fetch(`/api/v1/admin/workspaces/${wsId}`, {
        method: "DELETE",
        headers: { "X-Admin-Token": token! },
      });
      if (res.ok) {
        setWorkspaces(prev => prev.filter(w => w.id !== wsId));
      } else {
        const d = await res.json();
        alert(d.detail || "删除失败");
      }
    } finally {
      setDeleting(null);
      setConfirmDeleteWs(null);
    }
  }

  function handleLogout() {
    sessionStorage.removeItem(ADMIN_KEY);
    window.location.reload();
  }

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>系统管理后台</h2>
        <button
          onClick={handleLogout}
          style={{
            padding: "6px 16px", background: "#6c757d", color: "#fff",
            border: "none", borderRadius: 6, cursor: "pointer",
          }}
        >
          退出登录
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, borderBottom: "1px solid #ddd", paddingBottom: 0 }}>
        {(["workspaces", "users"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "8px 20px", border: "none", borderBottom: tab === t ? "2px solid #0d6efd" : "2px solid transparent",
              background: "none", cursor: "pointer", fontSize: 14,
              color: tab === t ? "#0d6efd" : "#666", fontWeight: tab === t ? 600 : 400,
            }}
          >
            {t === "workspaces" ? `工作空间（${workspaces.length}）` : `用户（${users.length}）`}
          </button>
        ))}
      </div>

      {confirmDeleteWs !== null && (
        <ConfirmDialog
          title="删除工作空间"
          message={`确定删除工作空间「${confirmDeleteWs}」吗？\n此操作不可恢复，所有案件和文件将永久删除。`}
          confirmText="删除"
          danger={true}
          onCancel={() => setConfirmDeleteWs(null)}
          onConfirm={() => handleDelete(confirmDeleteWs)}
        />
      )}

      {tab === "workspaces" && (
        <div style={{ background: "#fff", borderRadius: 8, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.08)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ background: "#f8f9fa" }}>
                <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 600 }}>ID</th>
                <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 600 }}>名称</th>
                <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 600 }}>创建时间</th>
                <th style={{ padding: "10px 16px", textAlign: "right", fontWeight: 600 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {workspaces.length === 0 && (
                <tr><td colSpan={4} style={{ padding: "24px", textAlign: "center", color: "#999" }}>暂无数据</td></tr>
              )}
              {workspaces.map(ws => (
                <tr key={ws.id} style={{ borderTop: "1px solid #eee" }}>
                  <td style={{ padding: "10px 16px", fontFamily: "monospace", fontSize: 12 }}>{ws.id}</td>
                  <td style={{ padding: "10px 16px" }}>{ws.name}</td>
                  <td style={{ padding: "10px 16px", color: "#666" }}>{ws.created_at}</td>
                  <td style={{ padding: "10px 16px", textAlign: "right" }}>
                    <button
                      onClick={() => setConfirmDeleteWs(ws.id)}
                      disabled={deleting === ws.id}
                      style={{
                        padding: "4px 12px", background: "#dc3545", color: "#fff",
                        border: "none", borderRadius: 4, cursor: "pointer", fontSize: 12,
                      }}
                    >
                      {deleting === ws.id ? "删除中..." : "删除"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "users" && (
        <div style={{ background: "#fff", borderRadius: 8, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.08)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ background: "#f8f9fa" }}>
                <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 600 }}>用户名</th>
                <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 600 }}>邮箱</th>
                <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 600 }}>Workspace</th>
                <th style={{ padding: "10px 16px", textAlign: "left", fontWeight: 600 }}>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr><td colSpan={4} style={{ padding: "24px", textAlign: "center", color: "#999" }}>暂无数据</td></tr>
              )}
              {users.map(u => (
                <tr key={u.workspace_id + u.username} style={{ borderTop: "1px solid #eee" }}>
                  <td style={{ padding: "10px 16px" }}>{u.username || "—"}</td>
                  <td style={{ padding: "10px 16px", color: "#666" }}>{u.email || "—"}</td>
                  <td style={{ padding: "10px 16px", fontFamily: "monospace", fontSize: 12 }}>{u.workspace_id}</td>
                  <td style={{ padding: "10px 16px", color: "#666" }}>{u.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
