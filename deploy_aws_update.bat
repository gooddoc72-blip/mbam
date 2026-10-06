@echo off
chcp 65001 >nul
cd /d "%~dp0"
python auth_server\deploy_server.py %*
if errorlevel 9009 (
    echo.
    echo [ERROR] python not found. Please check Python installation.
    pause
)
