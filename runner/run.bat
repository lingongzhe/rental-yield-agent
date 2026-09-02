@echo off
chcp 65001 >nul
title 沈阳大连老破小收租筛选
echo ==================================================================
echo    沈阳 / 大连  30万内老破小  纯投资收租筛选智能体
echo    首次运行请确认已安装 Python 3（本脚本免Python依赖库）
echo ==================================================================
echo.
cd /d "%~dp0"

rem 依次尝试 python / py 命令
set PY=python
python --version >nul 2>&1
if errorlevel 1 (set PY=py)

echo [1/4] 开始取数并评分 ...
%PY% main.py

echo.
echo [报告生成完成]
echo 打开 output\rental-report.html 即可查看可视化结果。
echo 是否现在用浏览器打开？(Y/N)
set /p ans=请选择:
if /i "%ans%"=="Y" start "" "output\rental-report.html"
pause