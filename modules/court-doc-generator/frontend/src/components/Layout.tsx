import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { useThemeStore, applyTheme, ThemeMode } from "../stores/themeStore";
import {
  LayoutDashboard, Building2, Users, FileText, History, LogOut, ScrollText, Sun, Moon, Monitor,
} from "lucide-react";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "首页" },
  { to: "/companies", icon: Building2, label: "公司管理" },
  { to: "/agents", icon: Users, label: "代理人" },
  { to: "/cases", icon: FileText, label: "案件" },
  { to: "/history", icon: History, label: "历史记录" },
  { to: "/audit-logs", icon: ScrollText, label: "操作日志" },
];

const THEME_OPTIONS: { value: ThemeMode; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "浅色", icon: Sun },
  { value: "dark", label: "深色", icon: Moon },
  { value: "system", label: "跟随系统", icon: Monitor },
];

export default function Layout() {
  const { workspaceName, logout } = useAuthStore();
  const themeMode = useThemeStore(s => s.mode);
  const setThemeMode = useThemeStore(s => s.setMode);
  const navigate = useNavigate();

  // F7：主题变更即应用；system 模式跟随系统偏好实时切换
  useEffect(() => {
    applyTheme(themeMode);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onSystemChange = () => {
      if (useThemeStore.getState().mode === "system") applyTheme("system");
    };
    mq.addEventListener("change", onSystemChange);
    return () => mq.removeEventListener("change", onSystemChange);
  }, [themeMode]);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span>⚖️ 出庭手续生成器</span>
        </div>
        <nav className="sidebar-nav">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => "nav-item" + (isActive ? " active" : "")}
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="theme-switch" style={{ marginBottom: 8 }}>
            {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                className={"theme-option" + (themeMode === value ? " active" : "")}
                title={label}
                onClick={() => setThemeMode(value)}
              >
                <Icon size={13} /> {label}
              </button>
            ))}
          </div>
          <div style={{ marginBottom: 8, fontSize: 13, color: "var(--text)" }}>
            👤 {workspaceName || "未登录"}
          </div>
          <button className="btn" onClick={handleLogout}>
            <LogOut size={14} /> 退出登录
          </button>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
