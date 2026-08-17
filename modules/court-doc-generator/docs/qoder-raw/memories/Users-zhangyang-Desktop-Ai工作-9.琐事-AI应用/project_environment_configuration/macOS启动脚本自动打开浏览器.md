---
title: "macOS启动脚本自动打开浏览器"
usage_scenario:
    - "配置或修复macOS应用的启动脚本时"
    - "排查双击应用图标无反应或浏览器未弹出的问题时"
keywords:
    - "macOS"
    - "启动脚本"
    - "自动打开浏览器"
    - "open命令"
source: "auto"
---

项目运行在macOS环境，双击`启动.command`脚本时，无论服务是新启动还是已在运行，都必须自动调用`open`命令弹出浏览器访问http://localhost:18501
