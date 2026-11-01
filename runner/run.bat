@echo off
chcp 65001 >nul
title 沈阳大连老破小收租筛选（贝壳官方数据）
echo ==================================================================
echo    沈阳 / 大连  30万内老破小  纯投资收租筛选智能体
echo    数据源：贝壳官方开放平台（beike CLI + 本机 API Key）
echo ==================================================================
echo.
cd /d "%~dp0"

rem 依次尝试 python / py 命令
set PY=python
python --version >nul 2>&1
if errorlevel 1 (set PY=py)

echo.
echo   [A] 联网更新贝壳数据并生成报告  （手动更新数据，几分钟）
echo   [B] 用上次贝壳快照重建报告      （离线，秒出）
echo.
set /p mode=请选择 (A/B)，回车默认 A:
if /i "%mode%"=="B" (goto rebuild) else (goto refresh)

:refresh
echo.
echo [开始] 经贝壳官方 API 更新真实数据并生成报告 ...
%PY% main.py --refresh
goto done

:rebuild
echo.
echo [开始] 用上次贝壳快照重建报告 ...
%PY% main.py
goto done

:done
echo.
echo [报告生成完成]
echo 打开 output\rental-report.html 即可查看可视化结果。
pause