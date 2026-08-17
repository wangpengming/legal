/* 00-首页：工作台导航（原型 00-index 结构 + 真实路由）。
   卡片数据静态（12 页清单），pillbar 数据事实基线用 /metadata 真值渲染。 */
import { useNavigate } from "react-router-dom";
import { useMetadata, useOverview } from "@/hooks";
import { fmtNum } from "@/lib/format";

interface NavCard {
  no: string;
  title: string;
  phase: "p0" | "p1" | "p2";
  ph: string;
  route: string;
  desc: string;
  nav?: boolean; // false = 详情页（需要路由参数）
}

const CARDS: NavCard[] = [
  { no: "01", title: "态势总览", phase: "p0", ph: "Ph1", route: "/overview", desc: "全库/音集协/在办/判赔累计数字卡；收案与判赔趋势图；业务线构成；开庭日程；同步状态条。" },
  { no: "02", title: "案件检索", phase: "p0", ph: "Ph1", route: "/search", desc: "14 列高密度表格；字段驱动筛选 + 已选条件胶囊；列设置/排序/分页/导出 CSV；脏数据角标；支持率迷你条。" },
  { no: "03", title: "案件详情", phase: "p0", ph: "Ph1", route: "/cases", nav: false, desc: "案件五区 + 生命周期时间轴 + 涉及歌曲清单 + 系列案树；原始值/清洗值对照；编辑/导出。" },
  { no: "04", title: "对手方画像", phase: "p1", ph: "Ph2", route: "/parties", desc: "画像头卡 + 对抗指标（胜诉率/支持率/判赔率）+ 时间线 + 我方同类案件清单。" },
  { no: "05", title: "多维分析", phase: "p1", ph: "Ph2", route: "/analysis", desc: "业务线 × 年份交叉热力；判赔趋势；归因钻取。" },
  { no: "06", title: "歌曲维度", phase: "p1", ph: "Ph2", route: "/songs", desc: "曲目使用频次、单曲判赔、在办/结案分布与高频歌曲清单。" },
  { no: "07", title: "费用看板", phase: "p1", ph: "Ph2", route: "/fees", desc: "判赔/获赔/支出/净费用四值与月度趋势，存疑金额标注。" },
  { no: "08", title: "指标口径中心", phase: "p1", ph: "Ph1", route: "/metrics", desc: "8 项指标口径 v1.0 定义 + formula SQL 断言 + 版本历史快照。" },
  { no: "09", title: "AI 对话", phase: "p1", ph: "Ph3", route: "/ai", desc: "Mode A 对话 + Mode B 报告模板（T1~T7）双模式同源检索语料。" },
  { no: "10", title: "同步管理", phase: "p0", ph: "Ph1", route: "/sync", desc: "同步状态卡；手动触发（全量/增量/单条）；历次同步日志与对账结果。" },
  { no: "11", title: "词典与清洗规则", phase: "p1", ph: "Ph1", route: "/dicts", desc: "枚举字典、公司名归一映射、规则启停/回滚/保存重跑、脏数据采纳台。" },
];

const PHASE_TAG: Record<NavCard["phase"], string> = { p0: "tag-p0", p1: "tag-p1", p2: "tag-p2" };
const PHASE_LABEL: Record<NavCard["phase"], string> = { p0: "P0", p1: "P1", p2: "P2" };

export default function IndexPage() {
  const navigate = useNavigate();
  const { data: meta } = useMetadata();
  const { data: ov } = useOverview();

  const total = ov?.summary.total_cases ?? meta?.latest_sync?.total ?? 0;
  const causeCount = meta?.enums.cause?.length ?? 0;
  const statusCount = meta?.enums.case_status?.length ?? 0;
  const resolveCount = meta?.enums.resolve?.length ?? 0;
  const payerCount = meta?.enums.payer?.length ?? 0;

  const groups: { label: string; items: NavCard[] }[] = [
    { label: "P0 · 核心工作台", items: CARDS.filter((c) => c.phase === "p0") },
    { label: "P1 · 分析与管理", items: CARDS.filter((c) => c.phase === "p1") },
  ].filter((g) => g.items.length > 0);

  return (
    <div>
      <div className="hero" style={{ padding: "26px 0 18px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div className="brand-logo">法</div>
          <div>
            <div className="hero-title">法务诉讼业务平台</div>
            <div className="hero-sub">Legal Case Workspace · 指标口径 v1.0 · 数据真值驱动</div>
          </div>
          <div className="hero-actions">
            <span className="badge status-green">
              <i className="dot" />
              已接入 · {fmtNum(total)} 条
            </span>
            <button className="btn btn-primary btn-sm" onClick={() => navigate("/search")}>
              案件检索 →
            </button>
          </div>
        </div>
      </div>

      <div className="pillbar">
        <span>
          数据事实基线：<b>{fmtNum(total)}</b> 条案件 · <b>8</b> 业务线（VOD/IPTV·OTT/车载/雷客/人力/哇屋/研发/默霆）
        </span>
        <span>
          <b>{causeCount}</b> 案由 · <b>{statusCount}</b> 案件状态 · <b>{resolveCount}</b> 结案原因 · <b>{payerCount}</b> 支付主体
        </span>
        <span>
          金额单位：<b>元</b> · 8 项指标口径（口径中心 08 页） · 三源交叉验证（📂本地/⚖️案例/📜法规）
        </span>
      </div>

      {groups.map((g) => (
        <section key={g.label}>
          <div className="sec-label">{g.label}</div>
          <div className="pgrid">
            {g.items.map((c) => (
              <div
                key={c.route + c.no}
                className="card card-pad pcard"
                onClick={() => (c.nav === false ? navigate("/search") : navigate(c.route))}
                role="button"
              >
                <div className="no">{c.no}</div>
                <div className="pt">
                  {c.title} <span className={PHASE_TAG[c.phase]}>{PHASE_LABEL[c.phase]}</span>
                </div>
                <div className="pd">{c.desc}</div>
                <div className="pm">
                  <span className="route">{c.route}</span>
                  <span className="phnum">{c.ph}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      <div className="note">
        交付链：需求 → SPEC → 调研 → 详细设计（<code>docs/02</code>）→ 高保真原型（77/79 项验收通过）→ 开发。
        本页数据事实基线来自 <code>/api/v1/metadata</code> 与 <code>/api/v1/stats/overview</code>，数字与口径中心同步。
      </div>
    </div>
  );
}