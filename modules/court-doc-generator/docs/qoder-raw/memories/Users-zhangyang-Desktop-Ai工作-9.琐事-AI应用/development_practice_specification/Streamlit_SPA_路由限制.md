---
title: "Streamlit SPA 路由限制"
usage_scenario:
    - "开发 Streamlit 应用时遇到静态资源加载失败"
    - "设计文件下载或预览功能需绕过路由拦截"
keywords:
    - "Streamlit"
    - "SPA 路由"
    - "静态资源拦截"
    - "URL 限制"
source: "auto"
---

Streamlit 应用存在 SPA 路由拦截问题：所有 URL 请求（包括/static/下的静态资源）均被返回 Streamlit 应用 HTML，导致无法直接访问本地 PDF 文件或 JS 库
