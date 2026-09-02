@echo off
chcp 65001>nul
title 部署到 GitHub
setlocal
cd /d "%~dp0"

echo ============================================================
echo  部署 rental-yield-agent 到 GitHub（含每日自动刷新配置）
echo  前置：本机能联网访问 GitHub，且本地 git 已登录账号。
echo ============================================================
echo.
echo 步骤1：创建远程仓库(公开)。首次请提供 GitHub Token：
echo       生成方式：GitHub Settings - Developer settings
echo        - Personal access tokens - Token(classic)
echo       勾选权限：repo、workflow
echo.
set "TOKEN="
set /p TOKEN=请输入 GitHub Token(留空则用已保存凭据):
echo.

rem 生成本地临时提交后的"当前用户"用于 git 提交作者
set "GIT_USER=lingongzhe"
set "GIT_EMAIL=lingongzhe@users.noreply.github.com"
set "REPO=rental-yield-agent"

if not "%TOKEN%"=="" (
  echo 创建远程仓库 ...
  echo {"name":"%REPO%","private":false,"description":"Daily rental-yield screening for old-town apartments in Shenyang ^& Dalian, auto-refresh via GitHub Actions"}>"%TEMP%\repo_body.json"
  curl -s -X POST https://api.github.com/user/repos ^
    -H "Authorization: token %TOKEN%" ^
    -H "Accept: application/vnd.github+json" ^
    -H "Content-Type: application/json" ^
    --data-binary "@%TEMP%\repo_body.json"
  echo.
  del "%TEMP%\repo_body.json" >nul 2>&1
)

echo 关联远程仓库并推送 ...
git remote remove origin >nul 2>&1
git remote add origin https://github.com/%GIT_USER%/%REPO%.git
git -c user.name="%GIT_USER%" -c user.email="%GIT_EMAIL%" push -u origin main

if errorlevel 1 (
  echo.
  echo [推送失败] 请检查：本机能否联网访问 GitHub？git 是否已登录？
  echo 可用命令查看： git config --list ^| findstr user
) else (
  echo.
  echo 推送成功！接下来配置每日自动刷新：
  echo   GitHub 仓库 Actions 页面会自动识别 .github/workflows/daily.yml
  echo   每日北京时间 08:00 自动运行并提交刷新结果。
  echo   如需立即跑一次：仓库页 Actions - 每日刷新 - Run workflow。
)

echo.
pause