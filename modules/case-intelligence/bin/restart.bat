@echo off
REM Windows 重启脚本
cd /d "%~dp0\.."
python bin\restart.py
if errorlevel 1 pause