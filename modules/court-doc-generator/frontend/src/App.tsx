import { Routes, Route } from "react-router-dom";
import { useEffect } from "react";
import Dashboard from "./pages/Dashboard";
import CompaniesPage from "./pages/CompaniesPage";
import CompanyDetailPage from "./pages/CompanyDetailPage";
import AgentsPage from "./pages/AgentsPage";
import AgentDetailPage from "./pages/AgentDetailPage";
import CasesPage from "./pages/CasesPage";
import HistoryPage from "./pages/HistoryPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import Layout from "./components/Layout";

// 单租户模式：启动时设置 shared workspace ID，所有 API 自动使用此 ID
function InitWorkspace() {
  useEffect(() => {
    sessionStorage.setItem("_ws_id", "shared");
  }, []);
  return null;
}

export default function App() {
  return (
    <>
      <InitWorkspace />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="companies" element={<CompaniesPage />} />
          <Route path="companies/:id" element={<CompanyDetailPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="agents/:id" element={<AgentDetailPage />} />
          <Route path="cases" element={<CasesPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="audit-logs" element={<AuditLogsPage />} />
        </Route>
      </Routes>
    </>
  );
}
