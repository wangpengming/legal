@echo off
REM =============================================
REM Windows 启动脚本
REM 关键：用 python.exe 而非 py（避免触发 Microsoft Store 安装引导）
REM =============================================
cd /d "%~dp0\.."
where python >nul 2>nul
if errorlevel 1 (
    echo ❌ 未找到 Python。请安装 Python 3.10+ 并勾选 "Add to PATH"
    pause
    exit /b 1
)
python bin\start.py
if errorlevel 1 pause