@echo off
echo ===================================================
echo 🚀 NOVA BOT - RESTART SEQUENCE
echo ===================================================

echo.
echo 🛑 Stopping existing processes...
call npx pm2 stop all
call npx pm2 delete all

echo.
echo 🧹 Cleaning up temporary files...
if exist "dump.rdb" del "dump.rdb"

echo.
echo Stopping all Python processes...
taskkill /F /IM python.exe /T 2>nul
timeout /t 2 /nobreak >nul

echo.
echo ▶️ Starting Bot and Frontend with PM2...
call npx pm2 start ecosystem.windows.config.js

echo.
echo 📜 Showing logs (Press Ctrl+C to exit logs, Bot will keep running)...
echo ===================================================
call npx pm2 logs
