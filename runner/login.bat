@echo off
chcp 65001 >nul
cd /d %~dp0
echo ==========================================
echo   链家/贝壳 登录态采集 - 登录一次
echo   之后每日任务将自动翻页抓更多真实数据
echo ==========================================
echo.
"C:\Users\zheli\AppData\Local\Programs\Python312\python.exe" login.py
echo.
pause