---
title: "Streamlit中调用系统Preview打印PDF技能"
usage_scenario:
    - "Streamlit应用需要PDF预览功能"
    - "macOS环境下实现PDF打印"
    - "浏览器内渲染PDF失败时的替代方案"
keywords:
    - "Streamlit"
    - "PDF打印"
    - "macOS Preview"
    - "subprocess"
    - "系统调用"
source: "auto"
---

## Input
- Streamlit 应用中需要展示 PDF 预览或打印功能
- 目标平台为 macOS

## Steps
1. 尝试在浏览器内渲染 PDF（使用 PDF.js 或 components.html）
2. 发现 Streamlit SPA 路由拦截所有 /static/* 请求，返回 HTML 而非实际文件
3. 放弃前端渲染方案，改用后端按钮触发系统命令
4. 使用 st.button 创建“系统 Preview 打开”按钮
5. 点击时执行 subprocess.Popen(["open", merged_pdf_path]) 调用 macOS Preview
6. 用户在 Preview 中按 Cmd+P 完成打印

## Output
- 用户通过 macOS 原生 Preview 查看和打印 PDF
- 避免浏览器兼容性问题和 Streamlit 限制

## Notes
- 此方案适用于 macOS 环境
- 若需跨平台，可改为调用系统默认 PDF 阅读器
- 保留本地 PDF.js 文件作为备用方案
