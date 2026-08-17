---
title: "Windows 启动脚本中 py 命令触发 Microsoft Store 安装引导陷阱"
usage_scenario:
    - "Windows 上 Python 启动脚本"
    - "Python 桌面工具跨平台分发"
    - "法务小白启动工具"
keywords:
    - "Windows"
    - "Python Launcher"
    - "py.exe"
    - "Microsoft Store"
    - "启动脚本"
    - "py command"
source: "auto"
---

## Bug Class
Windows 上 `py` 命令在没装 Python 时会触发 Microsoft Store 安装引导窗口，而不是真的执行 Python，导致启动脚本看似"运行"但实际未启动服务。

## Root Cause
Windows 10/11 自带 Python Launcher (`py.exe`)，位于 `%LOCALAPPDATA%\Microsoft\WindowsApps\py.exe`。当用户未装 Python 时：
- 直接运行 `py start.py` → 弹出 Microsoft Store 安装 Python 的窗口（显示 `py` 命令的 usage）
- 但 Python 没真正安装，只是引导用户去 Store
- 用户看到帮助信息后误以为脚本"出错"或"没反应"

## Fix Pattern
不要在启动脚本里使用 `py` 命令（会触发 Store），而应主动探测 Python 真实安装路径，按优先级查找：
1. 项目自带虚拟环境：`.venv\Scripts\python.exe`
2. PATH 中的 `python.exe`（`where python`）
3. PATH 中的 `python3.exe`（`where python3`）
4. 常见安装路径：`C:\Python39-312\python.exe`
5. 用户级 AppData：`%LOCALAPPDATA%\Programs\Python\Python3xx\python.exe`
6. 都找不到 → 自动打开 https://www.python.org/downloads/ 下载页

关键点：必须用 `where python` 而不是 `py` 来检测；Microsoft Store 的 Python 不会自动出现在 `where python` 结果中。

## Reusable Lesson
跨平台启动脚本（Windows .bat）应避免使用 `py` Python Launcher，因为它会触发 Microsoft Store 引导。优先使用 `python` / `python3` 命令，或直接探测已知安装路径。给小白用的工具必须能在没装 Python 时自动打开下载页，而不是弹 Store 误导。

适用范围：Streamlit / 任何 Python 桌面工具的 Windows 启动脚本。
