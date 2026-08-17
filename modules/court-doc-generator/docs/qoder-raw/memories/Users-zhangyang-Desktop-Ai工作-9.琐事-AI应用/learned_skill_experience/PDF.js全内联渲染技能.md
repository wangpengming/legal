---
title: "PDF.js全内联渲染技能"
usage_scenario:
    - "在sandboxed iframe中加载第三方JS库"
    - "无外部CDN访问权限时的前端资源加载"
    - "Streamlit组件内嵌复杂JS应用"
keywords:
    - "PDF.js"
    - "全内联"
    - "Base64"
    - "iframe"
    - "eval"
source: "auto"
---

## Input
- JavaScript库源码（如PDF.js）
- 需要渲染的目标数据（如PDF文件二进制）
- 目标容器（sandboxed iframe）

## Steps
1. **Base64编码**：将JS库源码和PDF文件分别进行Base64编码。
2. **Worker注入**：将Worker JS解码为Uint8Array，创建Blob对象，生成Object URL（`URL.createObjectURL`）。
3. **主库执行**：在主脚本中使用 `<script>eval(atob(main_b64))</script>` 执行主库代码。**注意**：必须使用 `eval` 配合inline script，因为 `new Function()` 创建的函数作用域无法泄漏 `var pdfjsLib` 到外层。
4. **数据加载**：调用 `pdfjsLib.getDocument({ data: atob(pdf_b64) })` 加载PDF。
5. **渲染**：配置Viewer并挂载到DOM。

## Output
- 在iframe中成功渲染PDF，支持缩放、翻页、打印等交互。

## Notes
- 适用于所有需要在受限环境（如sandboxed iframe、无外部CDN访问权限）中动态加载大型JS库的场景。
- 确保Worker URL和主库版本匹配。
- 如果库依赖全局变量，避免使用 `new Function` 构造器。
