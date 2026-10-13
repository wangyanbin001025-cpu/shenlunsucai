@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo             申 论 素 材 库
echo ==============================================
where python >nul 2>nul
if errorlevel 1 (
  echo 未检测到 Python。请先安装 Python 3.10 或更高版本，并勾选 Add Python to PATH。
  pause
  exit /b 1
)
start "申论素材库网页" http://127.0.0.1:8765
python server.py
pause
