---
title: "Windows环境Python检测与启动规范"
usage_scenario:
    - "开发跨平台桌面工具或本地服务时配置启动脚本"
    - "排查Windows环境下Python无法运行或误触Store的问题"
keywords:
    - "Windows"
    - "Python检测"
    - "Microsoft Store"
    - "启动脚本"
source: "auto"
---

Windows环境Python检测与启动规范：
1. 避免使用`py`命令（会触发Microsoft Store安装引导）。
2. 按优先级探测Python路径：项目自带`.venv\Scripts\python.exe` > `PATH`中的`python`/`python3` > `C:\Python*` > `%LOCALAPPDATA%\Programs\Python\Python3xx\`。
3. 未检测到Python时，自动打开https://www.python.org/downloads/下载页。
