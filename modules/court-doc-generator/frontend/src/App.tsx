import { Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import { useAuthStore } from "./stores/authStore";
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";
import CompaniesPage from "./pages/CompaniesPage";
import CompanyDetailPage from "./pages/CompanyDetailPage";
import AgentsPage from "./pages/AgentsPage";
import AgentDetailPage from "./pages/AgentDetailPage";
import CasesPage from "./pages/CasesPage";
import HistoryPage from "./pages/HistoryPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import Layout from "./components/Layout";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { workspaceId } = useAuthStore();
  // 同步 workspaceId 到 sessionStorage（API 依赖 sessionStorage）
  useEffect(() => {
    if (workspaceId) {
      sessionStorage.setItem("_ws_id", workspaceId);
    }
  }, [workspaceId]);
  if (!workspaceId) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
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
  );
}
