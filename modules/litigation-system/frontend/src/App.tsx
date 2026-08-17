/* 应用装配（fe-9）：HashRouter + QueryClientProvider + ToastListener（lt:toast 事件桥）
   + AppLayout 外壳 + 全部页面路由（/cases/:recordId、/parties/:name 画像深链等均真实实现）。 */
import { useEffect, useState } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "@/components/layout";
import IndexPage from "@/pages/IndexPage";
import OverviewPage from "@/pages/OverviewPage";
import SearchPage from "@/pages/SearchPage";
import CaseDetailPage from "@/pages/CaseDetailPage";
import SyncPage from "@/pages/SyncPage";
import DictsPage from "@/pages/DictsPage";
import MetricsPage from "@/pages/MetricsPage";
import PartiesPage from "@/pages/PartiesPage";
import AnalysisPage from "@/pages/AnalysisPage";
import SongsPage from "@/pages/SongsPage";
import FeesPage from "@/pages/FeesPage";
import TagsPage from "@/pages/TagsPage";
import AiPage from "@/pages/AiPage";
import ReportsPage from "@/pages/ReportsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

/* 监听全局 lt:toast 事件（页面写操作反馈通道），挂载于 Router 内保证 HMR 后代监听优先。 */
function ToastListener() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    const onToast = (e: Event) => {
      const detail = (e as CustomEvent<string | undefined>).detail;
      setMsg(detail ?? "操作完成");
      window.setTimeout(() => setMsg(null), 2600);
    };
    window.addEventListener("lt:toast", onToast);
    return () => window.removeEventListener("lt:toast", onToast);
  }, []);
  return <div className={`toast${msg ? " show" : ""}`}>{msg ?? ""}</div>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <ToastListener />
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/index" replace />} />
            <Route path="/index" element={<IndexPage />} />
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/cases" element={<CaseDetailPage />} />
            <Route path="/cases/:recordId" element={<CaseDetailPage />} />
            <Route path="/parties" element={<PartiesPage />} />
            <Route path="/parties/:name" element={<PartiesPage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
            <Route path="/songs" element={<SongsPage />} />
            <Route path="/fees" element={<FeesPage />} />
            <Route path="/tags" element={<TagsPage />} />
            <Route path="/metrics" element={<MetricsPage />} />
            <Route path="/ai" element={<AiPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/reports/:id" element={<ReportsPage />} />
            <Route path="/sync" element={<SyncPage />} />
            <Route path="/dicts" element={<DictsPage />} />
            <Route path="*" element={<Navigate to="/index" replace />} />
          </Route>
        </Routes>
      </HashRouter>
    </QueryClientProvider>
  );
}