@echo off
rem Runs the agent with the project's Python 3.12 environment.
rem Usage: run          (same as "run start")
rem        run console  (talk to it with your mic in the terminal)
cd /d "%~dp0"
set CMD=%1
if "%CMD%"=="" set CMD=start
".venv\Scripts\python.exe" agent.py %CMD%
pause
