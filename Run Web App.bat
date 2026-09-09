@echo off
cd /d "%~dp0"
echo.
echo  ==========================================
echo   Instagram to YouTube Bot - Web Server
echo  ==========================================
echo.
pip install flask flask-cors >nul 2>&1
python web_server.py
pause
