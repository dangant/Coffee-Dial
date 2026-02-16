@echo off
title Coffee Brewing Tracker
echo Starting Coffee Brewing Tracker...
echo.
echo Opening browser...
start http://127.0.0.1:8000
echo.
echo ========================================
echo  Close this window to stop the server
echo ========================================
echo.
cd /d "%~dp0"
python -m uvicorn app.main:app --reload
