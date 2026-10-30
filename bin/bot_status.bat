@echo off
REM Windows bot status（用 python.exe 而非 py）
cd /d "%~dp0\.."
where python
if errorlevel 1 (
    echo 未找到 Python。请安装 Python 3.10+ 并勾选 "Add to PATH"
    pause
    exit /b 1
)
python bin\bot_status.py
if errorlevel 1 pause
