@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-ai\Scripts\python.exe" goto prepare_studio
".venv-ai\Scripts\python.exe" scripts\check_installation.py
if not errorlevel 1 goto start_studio
:prepare_studio
echo Preparing your separate local Studio 2.0 installation.
py -3.11 scripts\bootstrap.py
if errorlevel 1 goto failed
:start_studio
".venv-ai\Scripts\python.exe" -m studio
if errorlevel 1 goto failed
exit /b 0
:failed
echo Studio could not start. The error above explains what is missing.
echo No existing applications or family recordings were removed.
pause
exit /b 1
