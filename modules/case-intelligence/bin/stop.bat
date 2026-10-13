@echo off
REM Windows 停止脚本
cd /d "%~dp0\.."
python bin\stop.py
if errorlevel 1 pause