@echo off
REM Script to fetch production logs from remote server (Windows)
REM Usage: fetch_prod_logs.bat [lines]

set LINES=%1
if "%LINES%"=="" set LINES=100

echo 📥 Fetching last %LINES% lines from production logs...
echo.

echo 🤖 Bot Engine Logs:
echo ====================
ssh root@10.10.20.76 "pm2 logs hl-bot-engine --lines %LINES% --nostream"

echo.
echo.

echo 🌐 API Logs:
echo ====================
ssh root@10.10.20.76 "pm2 logs hl-bot-api --lines %LINES% --nostream"

echo.
echo.

echo 🎨 Frontend Logs:
echo ====================
ssh root@10.10.20.76 "pm2 logs hl-bot-frontend --lines %LINES% --nostream"
