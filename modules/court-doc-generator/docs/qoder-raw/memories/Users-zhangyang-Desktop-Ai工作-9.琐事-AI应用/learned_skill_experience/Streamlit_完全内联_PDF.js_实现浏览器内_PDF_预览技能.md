---
title: "Streamlit 完全内联 PDF.js 实现浏览器内 PDF 预览技能"
usage_scenario:
    - "Streamlit 浏览器内 PDF 预览"
    - "Streamlit 沙盒 iframe 不能访问 CDN 时的 PDF 渲染"
    - "macOS 本地服务 SPA 路由拦截下的 PDF 浏览"
keywords:
    - "Streamlit"
    - "PDF.js"
    - "base64"
    - "内联"
    - "components.html"
    - "Blob URL"
    - "eval"
    - "CMap"
source: "auto"
---

## Input
- Streamlit 应用中需要在浏览器内显示 PDF（缩放/翻页/文字选择/打印）
- 用户在 macOS，本地端口部署
- PDF 文件路径已知（Path 对象）

## Steps
1. **PDF.js 全内联到 components.html**：把 `static/pdfjs/pdf.min.js`（320KB）和 `pdf.worker.min.js`（1MB）用 `@st.cache_resource` 缓存为 base64 字符串
2. **Worker 通过 Blob URL 注入**：`URL.createObjectURL(new Blob([Uint8Array.from(atob(workerB64), c=>c.charCodeAt(0))], {type:'application/javascript'}))` — 避免跨域/CSP 限制
3. **主库用 eval + inline script 暴露全局变量**：PDF.js 用 `var pdfjsLib = {...}` 声明，**必须用 inline `<script>eval(atob(mainB64))</script>`** 而不能用 `new Function()` — 因为 Function 内部 var 不会泄漏到外层
4. **PDF 文件按需 base64 编码**：`base64.b64encode(Path(pdf_path).read_bytes()).decode()`，3MB PDF → 4MB base64
5. **PDF.js getDocument 用 data 参数**：`pdfjsLib.getDocument({ data: atob(PDF_DATA_B64) })` — 不用 url 参数（避免 HTTP）
6. **CSS 隐藏打印工具栏**：`@media print { .toolbar, .actions, .page-label { display: none; } .page-wrap { page-break-after: always; } }`

## Output
- 浏览器内真正的 PDF 体验（缩放/翻页/文字选择/打印）
- 不依赖外部 CDN
- 不受 Streamlit SPA 路由拦截影响
- 保留 macOS 系统 Preview 按钮作为降级方案

## Notes
- 大文件 base64 字符串拼接 HTML 会让 HTML 体积显著增加（每个 PDF 4MB），但仅在打开预览时一次性渲染
- PDF.js 默认渲染中文 PDF 会有 CMap 警告，但 PDF 内嵌字体可正常显示文字
- 控制台会有 `pdfjsLib.GlobalWorkerOptions` 的 sandbox 警告，但不影响功能
- Streamlit >= 1.40 提示 `st.components.v1.html` 即将废弃，未来应改用 `st.iframe`
