---
title: "macOS 环境下 PDF 预览方案"
usage_scenario:
    - "需要展示或打印生成的 PDF 文件时选择打开方式"
    - "排查 PDF 无法在浏览器内显示的问题"
keywords:
    - "macOS"
    - "Preview"
    - "open 命令"
    - "PDF 预览"
source: "auto"
---

项目运行在 macOS 环境，PDF 预览和打印通过调用系统命令 `open <pdf_path>` 启动 macOS Preview 原生阅读器实现，而非浏览器内嵌渲染
