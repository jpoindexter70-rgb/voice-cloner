@echo off
setlocal
cd /d "%~dp0"
echo Studio 2.0 optional local browser-server installation
py -3.11 scripts\bootstrap.py
if errorlevel 1 goto failed
echo Installation complete. Run Start Studio 2.0.cmd.
pause
exit /b 0
:failed
echo Installation failed. Keep the error above for diagnosis.
echo Python 3.11 64-bit and the Windows Python launcher are required.
pause
exit /b 1
