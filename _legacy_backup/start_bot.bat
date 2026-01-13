@echo off
echo Starting NovaBot Backend...
cd /d %~dp0
call venv\Scripts\activate.bat
python main_nextjs.py
pause
