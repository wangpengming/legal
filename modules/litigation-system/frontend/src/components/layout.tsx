/* App 外壳（docs/02 §3）：Sidebar 12 项导航（3 组）+ Topbar（全局检索 / 同步状态 / 主题切换）
   + 内容区 Outlet + 页脚口径声明（G13）。 */
import { useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bot,
  Gauge,
  Home,
  Library,
  ListTree,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Scale,
  Search,
  ServerCog,
  Settings2,
  Sun,
  Table2,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useOverview, useSyncStatus } from "@/hooks";
import { useUiStore } from "@/stores/ui";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- 导航配置（12 页，3 组） */

interface NavItem {
  no: string;
  label: string;
  to: string;
  icon: LucideIcon;
  beta?: boolean;
}

const NAV_GROUPS: { head: string; items: NavItem[] }[] = [
  {
    head: "工作台",
    items: [
      { no: "00", label: "首页", to: "/index", icon: Home },
      { no: "01", label: "态势总览", to: "/overview", icon: Gauge },
      { no: "02", label: "案件检索", to: "/search", icon: Search },
      { no: "03", label: "案件详情", to: "/cases", icon: Scale },
    ],
  },
  {
    head: "统计分析",
    items: [
      { no: "04", label: "对手方画像", to: "/parties", icon: Users },
      { no: "05", label: "归因分析", to: "/analysis", icon: ListTree },
      { no: "06", label: "歌曲维度", to: "/songs", icon: Library },
      { no: "07", label: "费用看板", to: "/fees", icon: Table2 },
    ],
  },
  {
    head: "系统管理",
    items: [
      { no: "08", label: "指标口径", to: "/metrics", icon: Settings2 },
      { no: "09", label: "AI 对话", to: "/ai", icon: Bot, beta: true },
      { no: "10", label: "数据同步", to: "/sync", icon: ServerCog },
      { no: "11", label: "字典配置", to: "/dicts", icon: UserRound },
    ],
  },
];

/* ---------------------------------------------------------------- Sidebar */

function isTypingTarget(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  return t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName);
}

function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const setSidebarCollapsed = useUiStore((s) => s.setSidebarCollapsed);
  const navigate = useNavigate();
  const location = useLocation();
  const { data: overview } = useOverview();

  const courtCount = overview?.upcoming_court?.length ?? 0;
  /* 案件详情（03）为深链页：位于 /cases* 时高亮 */
  const inCases = location.pathname.startsWith("/cases");

  return (
    <aside className={cn("sidebar", collapsed && "collapsed")}>
      <div className="brand">
        <div className="brand-logo">法</div>
        <div>
          <div className="brand-name">法务诉讼平台</div>
          <div className="brand-sub">Legal Ops · v0.6</div>
        </div>
      </div>

      {NAV_GROUPS.map((g) => (
        <div className="nav-group" key={g.head}>
          <div className="nav-group-head">{g.head}</div>
          {g.items.map((item) => {
            const Icon = item.icon;
            const active = item.to === "/cases" ? inCases : location.pathname === item.to;
            return (
              <button
                key={item.no}
                type="button"
                className={cn("nav-item", active && "active")}
                onClick={() => navigate(item.to)}
                title={item.label}
              >
                <span className="nav-ico">
                  <Icon size={16} />
                </span>
                <span className="nav-label">{item.label}</span>
                {item.no === "01" && courtCount > 0 && <span className="nav-count">开庭 {courtCount}</span>}
                {item.beta && <span className="ph-badge">Beta</span>}
              </button>
            );
          })}
        </div>
      ))}

      <div className="side-foot">
        <button type="button" className="collapse-btn" onClick={() => setSidebarCollapsed(!collapsed)}>
          {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          <span>{collapsed ? "展开" : "折叠"}</span>
        </button>
      </div>
    </aside>
  );
}

/* ---------------------------------------------------------------- Topbar */

function Topbar() {
  const navigate = useNavigate();
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const { data: sync } = useSyncStatus();

  /* 全局「/」聚焦检索，Escape 失焦（docs/02 §3.2） */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && !isTypingTarget(e.target)) {
        e.preventDefault();
        inputRef.current?.focus();
      } else if (e.key === "Escape") {
        inputRef.current?.blur();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const submit = () => {
    const v = q.trim();
    if (!v) return;
    navigate(`/search?q=${encodeURIComponent(v)}`);
    setQ("");
    inputRef.current?.blur();
  };

  const syncRunning = sync?.running;
  const syncFailed = sync?.last?.status === "failed" || sync?.last?.status === "error";

  return (
    <header className="topbar">
      <div className="search-box">
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="全局检索：案号 / 当事人 / 歌名…"
          aria-label="全局检索"
        />
        <span className="s-ico">⌕</span>
        <kbd className="kbd">/</kbd>
      </div>

      <div className="top-right">
        {/* 同步状态徽标 → 跳数据同步 */}
        <button
          type="button"
          className="icon-btn"
          title={syncRunning ? "同步进行中" : syncFailed ? "最近一次同步失败" : "数据同步正常"}
          onClick={() => navigate("/sync")}
        >
          <RefreshCw size={15} className={cn(syncRunning && "animate-spin")} />
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: syncFailed ? "var(--danger)" : syncRunning ? "var(--primary)" : "var(--success)",
              marginLeft: 2,
            }}
          />
        </button>
        {/* 主题切换 */}
        <button type="button" className="icon-btn" title={theme === "dark" ? "切换亮色" : "切换暗色"} onClick={toggleTheme}>
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </header>
  );
}

/* ---------------------------------------------------------------- 页脚（G13 口径声明） */

function LayoutFoot() {
  const { data: sync } = useSyncStatus();
  const latest = sync?.last ? `数据同步于 ${latestTime(sync.last.finished_at) ?? "—"}` : "尚未同步";
  return (
    <footer className="layout-foot">
      <span>法务诉讼业务平台 v0.6 · Phase 0~3 已交付</span>
      <span>·</span>
      <span>指标口径 v1.0（8 项，见口径中心）</span>
      <span>·</span>
      <span>状态/结案原因色映射表见设计文档 §2.2</span>
      <span>·</span>
      <span>{latest}</span>
      <span className="grow" />
      <a href="mailto:legal-ops@leishi.local?subject=%E6%B3%95%E5%8A%A1%E8%AF%89%E8%AE%BC%E5%B9%B3%E5%8F%B0%E5%8F%8D%E9%A6%88">反馈问题</a>
    </footer>
  );
}

function latestTime(t: string | null | undefined): string | null {
  if (!t) return null;
  const d = new Date(t);
  if (Number.isNaN(d.getTime())) return null;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/* ---------------------------------------------------------------- 外壳 */

export function AppLayout() {
  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <Topbar />
        <main className="content">
          <Outlet />
        </main>
        <LayoutFoot />
      </div>
    </div>
  );
}