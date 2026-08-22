import { useQuery } from "@tanstack/react-query";
import { Building2, Users, FileText, Clock, Bell, BellRing } from "lucide-react";
import { companyApi } from "../lib/api";
import { agentApi } from "../lib/api";
import { caseApi } from "../lib/api";
import { getUpcomingHearings, UpcomingHearing } from "../lib/hearingAlert";
import { useEffect, useRef, useState } from "react";

export default function Dashboard() {
  const { data: companies } = useQuery({ queryKey: ["companies"], queryFn: companyApi.list });
  const { data: agents } = useQuery({ queryKey: ["agents"], queryFn: agentApi.list });
  const { data: cases } = useQuery({ queryKey: ["cases"], queryFn: () => caseApi.list() });

  // F3：近 7 天开庭案件提醒
  const upcoming = getUpcomingHearings(cases ?? [], 7);
  const notifiedRef = useRef("");
  const [notifyEnabled, setNotifyEnabled] = useState(false);
  const notifyUpcoming = (list: UpcomingHearing[]) => {
    if (typeof Notification === "undefined") return;
    const day = new Date().toDateString();
    if (notifiedRef.current === day) return; // 每天只提醒一次
    if (list.length === 0) return;
    const text = list.map(h => `${h.case_number}（${h.days_left === 0 ? "今天" : `${h.days_left} 天后`}）`).join("、");
    new Notification("📅 开庭提醒", { body: text, tag: "hearing-alert" });
    notifiedRef.current = day;
  };
  const enableNotify = () => {
    if (typeof Notification === "undefined") return;
    Notification.requestPermission().then(p => {
      setNotifyEnabled(p === "granted");
      if (p === "granted") notifyUpcoming(upcoming);
    });
  };
  const canNotify = typeof Notification !== "undefined" && Notification.permission === "granted";
  // 已授权时进入页面自动提醒（ref 每日去重，不会重复弹）
  useEffect(() => {
    if (upcoming.length > 0) notifyUpcoming(upcoming);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [upcoming, canNotify]);

  const stats = [
    { icon: Building2, label: "公司", value: companies?.length ?? 0, color: "#1677ff" },
    { icon: Users, label: "代理人", value: agents?.length ?? 0, color: "#52c41a" },
    { icon: FileText, label: "案件", value: cases?.length ?? 0, color: "#fa8c16" },
    { icon: Clock, label: "最近生成", value: cases?.[0]?.case_number || "—", color: "#722ed1" },
  ];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">首页</h1>
        {upcoming.length > 0 && (
          <div className="page-actions">
            {canNotify || notifyEnabled ? (
              <span className="badge badge-ok"><BellRing size={12} /> 提醒已开启</span>
            ) : (
              <button className="btn" onClick={enableNotify}>
                <Bell size={12} /> 开启提醒
              </button>
            )}
          </div>
        )}
      </div>

      {upcoming.length > 0 && (
        <div className={`alert ${upcoming.some(h => h.days_left === 0) ? "alert-error" : "alert-success"}`} style={{ marginBottom: 16 }}>
          <strong>📅 近 {upcoming.length} 个案件即将开庭：</strong>
          <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
            {upcoming.map(h => (
              <span key={h.id}>
                {h.case_number} · {h.court || "—"} · {h.hearing_date}
                <strong style={{ marginLeft: 8, color: h.days_left === 0 ? "#cf1322" : "#d46b08" }}>
                  {h.days_left === 0 ? "⏰ 今天开庭！" : `${h.days_left} 天后开庭`}
                </strong>
              </span>
            ))}
          </div>
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        {stats.map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="card" style={{ textAlign: "center" }}>
            <Icon size={28} color={color} style={{ margin: "0 auto 8px" }} />
            <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{label}</div>
          </div>
        ))}
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>快速开始</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <a href="/companies" className="btn btn-primary">🏢 管理公司</a>
          <a href="/agents" className="btn btn-primary">👤 管理代理人</a>
          <a href="/cases" className="btn btn-primary">📋 新建案件</a>
          <a href="/history" className="btn">📁 查看历史</a>
        </div>
      </div>
    </div>
  );
}
