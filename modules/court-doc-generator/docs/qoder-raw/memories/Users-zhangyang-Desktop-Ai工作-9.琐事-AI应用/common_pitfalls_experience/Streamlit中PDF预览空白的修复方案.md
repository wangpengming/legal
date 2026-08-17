---
title: "Streamlit中PDF预览空白的修复方案"
usage_scenario:
    - "Streamlit应用PDF预览显示空白"
    - "st.components.v1.html被弃用后的替代方案"
    - "解决base64过大导致的iframe加载失败"
keywords:
    - "Streamlit"
    - "PDF预览"
    - "st.components.v1"
    - "PDF.js"
source: "auto"
---

Streamlit 中 `st.components.v1.html` 已废弃，且 `st.iframe` 对本地文件路径支持不稳定（需传入 `pathlib.Path` 对象或使用绝对 HTTP URL）。当遇到 PDF 预览空白时，建议采用以下方案：
1. 将生成的 PDF 保存到项目的 `static/` 目录下。
2. 编写一个独立的 HTML 页面（如 `static/pdf_viewer.html`），使用 Mozilla 开源库 **PDF.js** 进行渲染。
3. 在 Streamlit 前端通过 `<a>` 标签或按钮，以 HTTP URL 形式（如 `http://localhost:port/static/pdf_viewer.html?pdf=/static/path/to/file.pdf`）在新窗口打开该页面。

来源：Bash, CallMcpTool
