---
title: "Streamlit集成PDF.js实现高质量预览技能"
usage_scenario:
    - "需要在Web应用中展示PDF文档"
    - "Streamlit应用增加文件预览功能"
    - "提升前端界面的专业度和易用性"
keywords:
    - "PDF.js"
    - "Streamlit"
    - "前端预览"
    - "静态资源"
source: "auto"
---

## Input
- 待预览的 PDF 文件路径
- Streamlit 应用的运行端口

## Steps
1. **准备静态资源**：在项目根目录创建 `static/` 文件夹，并在其中编写 `pdf_viewer.html`，引入 PDF.js CDN 资源，解析 URL 参数中的 PDF 路径并渲染。
2. **保存生成文件**：后端生成 PDF 后，将其复制到 `static/merged/` 目录下，确保可通过 HTTP 访问。
3. **构建预览链接**：拼接 URL，格式为 `http://{host}:{port}/static/pdf_viewer.html?pdf={relative_path}&title={filename}`。
4. **前端交互**：在 Streamlit 界面提供“在线预览”按钮，点击后使用 `target="_blank"` 在新标签页打开上述链接。

## Output
用户在新窗口中看到带有缩放、翻页、打印功能的 PDF 预览界面。

## Notes
- 必须使用 HTTP URL 而非相对路径或 base64，以避免浏览器安全限制和性能问题。
- PDF.js 渲染效果优于原生 iframe/embed 标签。
