@echo off
REM Windows 停止脚本
cd /d "%~dp0\.."
where python >nul 2>nul
if errorlevel 1 (
    echo ❌ 未找到 Python
    pause
    exit /b 1
)
python bin\stop.py
if errorlevel 1 pause