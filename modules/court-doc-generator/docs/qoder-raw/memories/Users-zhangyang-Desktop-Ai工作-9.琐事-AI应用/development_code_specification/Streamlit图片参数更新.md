---
title: "Streamlit图片参数更新"
usage_scenario:
    - "编写或升级Streamlit应用中的图片展示逻辑"
    - "修复因API变更导致的TypeError报错"
keywords:
    - "Streamlit"
    - "use_container_width"
    - "API废弃"
source: "auto"
---

使用Streamlit版本≥1.40时，图片显示参数必须使用`use_container_width=True`，原`use_column_width`参数已被废弃。
