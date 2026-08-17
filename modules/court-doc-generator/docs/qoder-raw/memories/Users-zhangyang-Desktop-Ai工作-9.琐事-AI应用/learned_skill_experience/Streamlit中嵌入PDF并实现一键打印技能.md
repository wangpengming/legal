---
title: "Streamlit中嵌入PDF并实现一键打印技能"
usage_scenario:
    - "为Streamlit文档生成应用添加在线PDF预览和打印功能"
    - "需要在Web界面中不跳转、不下载地展示并打印PDF"
    - "构建法律/政务类AI应用时提供‘所见即所得’的出庭材料交付体验"
keywords:
    - "Streamlit"
    - "PDF预览"
    - "一键打印"
    - "base64 iframe"
source: "auto"
---

## 输入
- 已有 Streamlit 应用主入口（app.py）
- 已有后端生成逻辑（如 generator.py）
- 已生成一个 PDF 文件路径（Path 对象）

## 步骤
1. 在 app.py 中导入 `base64` 和 `streamlit.components.v1 as components`
2. 调用后端生成函数，获取包含 `merged_pdf` 路径的 result 字典
3. 读取 PDF 文件为 bytes → base64 编码 → 构建 data URI
4. 使用 `components.html()` 嵌入 `<iframe src="data:application/pdf;base64,...">`
5. 在 iframe 下添加 HTML 按钮：`onclick="document.getElementById('pdfFrame').contentWindow.print()"`
6. 添加下载链接：`<a href="data:application/pdf;base64,..." download="...">`
7. （可选）调用跨平台提示音（如 `play_success_sound()`）

## 输出
- Web 页面上出现可滚动、可缩放的 PDF 预览 iframe
- 点击“🖨 一键打印全部”按钮，直接触发浏览器原生打印对话框
- “⬇ 下载合并 PDF”按钮可下载该 PDF
- 整个流程不依赖后端文件服务，纯前端完成

## 注意事项
- 必须确保 PDF 文件路径存在且可读；大文件需注意 base64 字符串长度限制（本例 < 5MB 安全）
- iframe 的 `#zoom=page-width` 参数保证首次加载时自动适配宽度
- 打印按钮必须通过 `contentWindow.print()` 调用，不可用 `window.print()`
