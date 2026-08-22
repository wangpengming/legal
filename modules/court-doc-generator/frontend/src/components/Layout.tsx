import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import {
  LayoutDashboard, Building2, Users, FileText, History, LogOut, Camera, ScrollText,
} from "lucide-react";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "首页" },
  { to: "/companies", icon: Building2, label: "公司管理" },
  { to: "/agents", icon: Users, label: "代理人" },
  { to: "/cases", icon: FileText, label: "案件" },
  { to: "/history", icon: History, label: "历史记录" },
  { to: "/scan", icon: Camera, label: "拍照扫描" },
  { to: "/audit-logs", icon: ScrollText, label: "操作日志" },
];

export default function Layout() {
  const { workspaceName, logout } = useAuthStore();
  const navigate = useNavigate();

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
