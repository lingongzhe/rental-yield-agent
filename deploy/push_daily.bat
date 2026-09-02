@echo off
chcp 65001>nul
rem ============================================================
rem  本机每日真实数据 → 生成报告 → 自动推送到 GitHub Pages
rem  前置：本机能联网访问链家(国内网络)，且有 GitHub Token 在
rem        ..\rv-crawler\deploy\.gh_token 或已保存凭据。
rem ============================================================
setlocal
cd /d "%~dp0"

set "PY=%~dp0..\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "RUNNER=%~dp0..\runner"

echo [%date% %time%] 开始：采集真实数据并生成报告 ...
"%PY%" "%RUNNER%\main.py"
set RC=%ERRORLEVEL%
if not "%RC%"=="0" (
  echo [运行失败] main.py 退出码=%RC%，但仍尝试推送已有报告。
)

rem 若本次为提示页且找不到真实数据，则不覆盖线上
findstr /C:"未获取到真实数据" "%RUNNER%\output\rental-report.html" >nul
if not errorlevel 1 (
  echo [注意] 本次未抓到真实数据，线上保持上次内容，不推送提示页覆盖。
  goto :end
)

echo 同步到 docs/index.html ...
copy /Y "%RUNNER%\output\rental-report.html" "%~dp0..\docs\index.html" >nul

echo 提交并推送到 GitHub ...
set "TOKEN="
if exist "%~dp0..\..\rv-crawler\deploy\.gh_token" set /p TOKEN=< "%~dp0..\..\rv-crawler\deploy\.gh_token"
if "%TOKEN%"=="" (
  echo 未找到 token 文件，尝试使用已保存的 git 凭据推送。
  git -C "%~dp0.." add -A
  git -C "%~dp0.." -c user.name="lingongzhe" -c user.email="lingongzhe@users.noreply.github.com" commit -m "auto: 每日真实收租报告 %date:~0,10%" 2>nul || echo 无新变更
  git -C "%~dp0.." push origin main
) else (
  git -C "%~dp0.." add -A
  git -C "%~dp0.." -c user.name="lingongzhe" -c user.email="lingongzhe@users.noreply.github.com" commit -m "auto: 每日真实收租报告 %date:~0,10%" 2>nul || echo 无新变更
  git -C "%~dp0.." push "https://x-access-token:%TOKEN%@github.com/lingongzhe/rental-yield-agent.git" main:main
)
if errorlevel 1 (
  echo [推送失败] 请检查网络或 token。
) else (
  echo 推送成功！线上 Pages 将自动更新为真实数据报告。
)
:end
endlocal