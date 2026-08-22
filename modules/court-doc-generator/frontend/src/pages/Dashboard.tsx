import { useQuery } from "@tanstack/react-query";
import { Building2, Users, FileText, Clock } from "lucide-react";
import { companyApi } from "../lib/api";
import { agentApi } from "../lib/api";
import { caseApi } from "../lib/api";

export default function Dashboard() {
  const { data: companies } = useQuery({ queryKey: ["companies"], queryFn: companyApi.list });
  const { data: agents } = useQuery({ queryKey: ["agents"], queryFn: agentApi.list });
  const { data: cases } = useQuery({ queryKey: ["cases"], queryFn: () => caseApi.list() });

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
      </div>
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
