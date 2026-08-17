---
title: "Windows 启动加固方案"
usage_scenario:
    - "打包项目给 Windows 用户时选择启动入口方案"
    - "排查 Windows 下双击启动无反应或闪退问题"
keywords:
    - "Windows 启动"
    - "Python 脚本"
    - "兼容性"
source: "auto"
---

Windows 启动入口采用 Python 脚本 (start.py) + 简化 .bat 方案：
- 启动.bat 仅负责调用 start.py
- start.py 使用纯 Python 实现健康检查、虚拟环境创建、依赖安装和浏览器打开
- 避免依赖 curl/timeout/tasklist/netstat 等老 Windows 缺失的命令
- 失败时通过 input() 暂停窗口并显示明确错误指引
