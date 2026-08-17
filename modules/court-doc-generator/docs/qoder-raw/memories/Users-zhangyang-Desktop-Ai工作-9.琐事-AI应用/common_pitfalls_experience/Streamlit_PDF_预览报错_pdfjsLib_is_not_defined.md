---
title: "Streamlit PDF 预览报错 pdfjsLib is not defined"
usage_scenario:
    - "Streamlit 应用运行时报 pdfjsLib is not defined 错误"
    - "PDF 预览功能无法加载或显示空白"
keywords:
    - "Streamlit"
    - "PDF.js"
    - "pdfjsLib"
    - "前端依赖"
source: "auto"
---

在 Streamlit 应用中渲染 PDF 时，若报错 `pdfjsLib is not defined`，通常是因为前端未正确加载 PDF.js 库或组件路径配置错误。需确保：1. 项目中已安装 `pdfjs-dist` 依赖；2. 前端代码中正确引用了 `pdfjsLib.GlobalWorkerOptions.workerSrc`；3. 静态资源目录（如 `/static`）下存在正确的 `merged_auto.pdf` 文件且路径可访问。（来源：Bash/WebSearch）
