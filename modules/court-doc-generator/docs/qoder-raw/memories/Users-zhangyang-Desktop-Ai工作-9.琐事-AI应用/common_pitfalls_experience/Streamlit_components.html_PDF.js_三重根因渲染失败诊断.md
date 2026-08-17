---
title: "Streamlit components.html PDF.js 三重根因渲染失败诊断"
usage_scenario:
    - "Streamlit 应用浏览器内 PDF 预览失败"
    - "Streamlit 升级后 PDF 组件报错"
    - "本地 PDF.js 集成失效"
keywords:
    - "Streamlit"
    - "PDF.js"
    - "SPA路由拦截"
    - "sandboxed iframe"
    - "base64 data URI"
    - "st.image use_column_width"
    - "use_container_width"
source: "auto"
---

## Bug Class
Streamlit components.html 嵌入 PDF.js 在 macOS 本地服务下无法渲染 PDF，浏览器内 PDF 预览完全失效。

## Root Cause
三重叠加的根因：
1. **Streamlit SPA 路由拦截**：`curl http://localhost:18501/static/pdfjs/pdf.min.js` 与 `/static/merged/*.pdf` 都返回 Streamlit HTML（10951 bytes）而非实际 JS/PDF，浏览器因严格 MIME 检查拒绝加载（控制台报错 `Expected a JavaScript-or-Wasm module script but the server responded with a MIME type of "text/html"`）。`/static/pdf_viewer.html` 也被 SPA 接管。
2. **sandboxed iframe 不能访问外部 CDN**：components.html 默认 sandbox 阻止跨域请求，PDF.js CDN（cdnjs/unpkg/jsdelivr）全部不可用。
3. **st.image 参数已废弃**：`render_pdf_pages` 用 `use_column_width=True`，Streamlit >= 1.40 已废弃，应改为 `use_container_width=True`。

## Fix Pattern
完全内联 PDF.js 到 components.html（`<script src="data:application/javascript;base64,{pdf_min_js_b64}">`），同时把 PDF 文件作为 `data:application/pdf;base64,...` 传入。彻底绕开 HTTP 路由与外部资源依赖。

## Reusable Lesson
Streamlit 项目中需要浏览器内 PDF 渲染时，不要依赖 /static/ 路径或外部 CDN。优先使用 base64 data URI 内联所有资源（PDF.js + PDF 文件）。如果是企业应用/低频使用，系统 Preview（subprocess.open）是稳定降级方案。

适用范围：Streamlit 1.40+ + 本地部署 + PDF 浏览场景。
