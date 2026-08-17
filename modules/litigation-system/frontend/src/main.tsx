/* 应用入口（fe-9）：Tailwind v4 设计系统 CSS → React 18 StrictMode → App 装配。
   index.css 内部 @import tailwindcss + theme/tokens.css + theme/components.css。 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);