---
title: "Streamlit SPA路由拦截与API废弃陷阱"
usage_scenario:
    - "访问/static/路径返回HTML而非文件"
    - "Streamlit组件报错unexpected keyword argument"
keywords:
    - "Streamlit"
    - "SPA路由"
    - "use_container_width"
    - "静态资源"
source: "auto"
---

### 1. Streamlit SPA路由拦截静态资源
- **现象**：访问 `/static/*` 路径时，Streamlit的SPA路由会拦截请求并返回HTML页面（而非实际文件），导致浏览器报MIME类型错误。
- **原因**：Streamlit默认将所有非路由请求视为SPA的一部分。
- **解决方案**：不要依赖HTTP路径访问静态资源；若需嵌入JS/CSS，应将其Base64编码后通过 `st.components.v1.html` 或 `st.iframe` 以Data URI方式内联。

### 2. Streamlit `use_column_width` 已废弃
- **现象**：运行时报错 `TypeError: ImageMixin.image() got an unexpected keyword argument 'use_column_width'`。
- **原因**：Streamlit ≥ 1.40 移除了该参数。
- **解决方案**：统一替换为 `use_container_width=True`。（来源：Bash, Streamlit）
