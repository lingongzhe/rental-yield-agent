@echo off
rem 一键提取浏览器登录态 → house-cli cookies.json（需“以管理员身份运行”）
rem 用法：右键本文件 → 以管理员身份运行；成功后即可正常跑 main.py --refresh
cd /d "%~dp0"
python export_cookies.py
echo.
pause
