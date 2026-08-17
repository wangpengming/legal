---
title: "PDF预览内联base64方案"
usage_scenario:
    - "在SPA框架（如Streamlit）中实现复杂前端组件渲染"
    - "需要离线或无外部依赖的PDF查看功能"
keywords:
    - "PDF.js"
    - "base64"
    - "data URI"
    - "内联脚本"
source: "auto"
---

PDF预览采用全内联base64 data URI方案：将PDF.js库和PDF文件编码为base64，通过data URL传入iframe，绕过Streamlit SPA路由拦截及外部CDN限制。
