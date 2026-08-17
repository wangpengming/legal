---
title: "Streamlit SPA路由拦截URL导致PDF无法预览"
usage_scenario:
    - "Streamlit应用内嵌PDF预览失败"
    - "浏览器内无法加载本地PDF或JS资源"
    - "需要稳定可靠的PDF打印方案"
keywords:
    - "Streamlit"
    - "SPA路由"
    - "PDF预览"
    - "macOS Preview"
    - "subprocess"
source: "auto"
---

Streamlit 的 SPA 路由会拦截所有 URL（包括 /static/merged/*.pdf 和 /static/pdfjs/*.js），导致浏览器内嵌 PDF.js 无法加载本地文件。解决方案：放弃浏览器渲染，改用后端 subprocess.Popen(["open", pdf_path]) 调用 macOS Preview 原生阅读器打开 PDF，这是最稳定的打印方案。（来源：Bash, CallMcpTool）

关键排查步骤：
1. 检查 curl http://localhost:18501/static/merged/merged_*.pdf 返回的是 streamlit HTML 而非 PDF 内容
2. 确认 sandboxed iframe 无法访问 CDN 和本地静态资源
3. 最终采用系统级 open 命令替代前端渲染
