---
title: "macOS 环境下 PDF 预览采用系统 Preview 方案"
usage_scenario:
    - "Streamlit 项目中需要展示 PDF 文件时选择预览方案"
    - "浏览器内嵌 PDF 渲染失败时切换到系统级打开"
keywords:
    - "macOS"
    - "PDF 预览"
    - "系统 Preview"
    - "subprocess.open"
source: "auto"
---

项目运行在 macOS 环境，PDF 预览优先使用系统原生 Preview 应用（通过 subprocess.open() 调用），而非浏览器内嵌渲染。当浏览器方案因 Streamlit SPA 路由限制或 sandboxed iframe 无法加载资源时，应切换至系统级打开方式以保证稳定性和打印质量。
