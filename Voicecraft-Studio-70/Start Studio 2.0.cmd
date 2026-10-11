@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-ai\Scripts\python.exe" goto missing_install
echo Starting Studio 2.0. Keep this window open while using the browser.
".venv-ai\Scripts\python.exe" -m studio
if errorlevel 1 goto failed
pause
exit /b 0
:missing_install
echo Run Install Studio 2.0.cmd to install the full engine first.
goto failed
:failed
echo Startup failed. The error above identifies the failing prerequisite.
pause
exit /b 1
