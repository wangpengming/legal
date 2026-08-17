@echo off
REM Windows 重启脚本
cd /d "%~dp0\.."
where python >nul 2>nul
if errorlevel 1 (
    echo ❌ 未找到 Python
    pause
    exit /b 1
)
python bin\restart.py
if errorlevel 1 pause