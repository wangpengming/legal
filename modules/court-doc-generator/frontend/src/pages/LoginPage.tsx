import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { authApi } from "../lib/api";

export default function LoginPage() {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuthStore();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const fn = tab === "login" ? authApi.login : authApi.register;
      const res = await fn(name, password);
      setAuth(res.workspace_id, res.workspace_name, res.token);
      // 同步到 sessionStorage（用于 API header 恢复）
      sessionStorage.setItem("_ws_id", res.workspace_id);
      navigate("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-title">⚖️ 出庭手续生成器</div>

        <div className="tabs">
          <button className={"tab" + (tab === "login" ? " active" : "")} onClick={() => setTab("login")}>
            登录
          </button>
          <button className={"tab" + (tab === "register" ? " active" : "")} onClick={() => setTab("register")}>
            注册
          </button>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">用户名</label>
            <input
              className="form-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={tab === "register" ? "至少 2 个字符" : "输入用户名"}
              required
              minLength={2}
            />
          </div>
          <div className="form-group">
            <label className="form-label">密码</label>
            <input
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={tab === "register" ? "至少 4 个字符" : "输入密码"}
              required
              minLength={4}
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center", marginTop: 8 }}>
            {loading ? "处理中..." : tab === "login" ? "登录" : "注册"}
          </button>
        </form>
      </div>
    </div>
  );
}
