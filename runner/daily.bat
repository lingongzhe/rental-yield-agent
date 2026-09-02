@echo off
title 沈阳大连老破小收租筛选·每日自动运行
rem 本脚本用于 Windows 计划任务，每日自动运行一次，无交互、不弹窗。
cd /d "%~dp0"

rem 依次尝试 python / py 命令（计划任务环境无 PATH 时优先用绝对路径）
set PY=python
if exist "C:\Users\zheli\AppData\Local\Programs\Python312\python.exe" set "PY=C:\Users\zheli\AppData\Local\Programs\Python312\python.exe"
if "%PY%"=="python" (
    python --version >nul 2>&1
    if errorlevel 1 set PY=py
)

echo [%date% %time%] 开始每日收租筛选 ...
"%PY%" main.py >> output\daily.log 2>&1
echo [%date% %time%] 运行结束，报告已更新。 >> output\daily.log