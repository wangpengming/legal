---
title: "Windows下py命令未装Python会触发Store弹窗"
usage_scenario:
    - "Windows环境下编写Python启动脚本"
    - "排查Windows上Python命令无响应或跳转浏览器的问题"
keywords:
    - "Windows"
    - "Python Launcher"
    - "Microsoft Store"
    - "py命令"
source: "auto"
---

在 Windows 10/11 环境中，直接调用 `py` 命令（Python Launcher）时，如果系统未安装 Python，它不会报错退出，而是会**自动弹出 Microsoft Store 的 Python 安装引导页面**。这会导致脚本看似运行但实际未执行任何逻辑。

解决方案：
1. 避免在自动化脚本中直接使用 `py` 命令。
2. 使用 `where python` 或 `where python3` 检测 PATH 中的可执行文件。
3. 检查常见安装路径（如 `C:\Python3xx\python.exe` 或 `%LOCALAPPDATA%\Programs\Python\...`）。
4. 若未找到，应明确提示用户安装并打开 python.org 下载页，而不是依赖 `py` 的隐式行为。（来源：Bash/Write）
