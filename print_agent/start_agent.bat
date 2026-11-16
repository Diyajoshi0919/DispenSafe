@echo off
REM Starts the DispenSafe print agent. Double-click, or add to Task Scheduler "At log on".
cd /d "%~dp0"
python agent.py
pause
