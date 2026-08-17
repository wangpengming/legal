---
title: "Streamlit中无CDN环境下内联PDF.js预览方案"
usage_scenario:
    - "Streamlit应用中集成PDF预览功能"
    - "解决iframe沙箱导致的跨域或CDN加载失败问题"
    - "处理Streamlit SPA路由对静态资源的拦截"
keywords:
    - "Streamlit"
    - "PDF.js"
    - "内联脚本"
    - "Base64"
    - "前端调试"
source: "auto"
---

## 输入
- 需要嵌入PDF预览功能的Streamlit应用
- 无法使用外部CDN或存在iframe沙箱限制的环境

## 步骤
1. **资源内联**：将 `pdf.min.js` 和 `pdf.worker.min.js` 转换为Base64字符串。
2. **Worker注入**：通过Blob URL注入Worker：`URL.createObjectURL(new Blob([Uint8Array.from(atob(workerB64), c=>c.charCodeAt(0))], {type:'application/javascript'}))`
3. **主库执行**：使用 `<script>eval(atob(mainB64))</script>` 执行主库代码，确保 `var pdfjsLib` 暴露在当前作用域（避免使用 `new Function` 导致变量不泄漏）。
4. **加载PDF**：使用 `pdfjsLib.getDocument({data: atob(PDF_B64)})` 加载PDF数据。
5. **样式适配**：在Streamlit中使用 `use_container_width=True` 替代已废弃的 `use_column_width`；添加 `@media print` 隐藏工具栏。

## 输出
浏览器内可正常显示、缩放、翻页且中文清晰的PDF预览组件

## 注意事项
- Streamlit SPA路由会拦截 `/static/` 下的请求返回HTML，不要尝试通过HTTP URL直接访问静态PDF文件。
- 缩略图建议控制在50KB以内以防卡顿。
