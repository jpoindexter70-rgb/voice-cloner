@echo off
setlocal
cd /d "%~dp0"
echo AI Voice Cloning Studio 2.0 - Startup
echo.
if not exist "D:\" if not defined STUDIO2_DATA_DIR goto missing_storage
if not exist ".venv\Scripts\python.exe" goto missing_install
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto invalid_install
echo.
echo Starting the studio. Keep this window open.
echo When the server reports it is running, open Chrome or Edge at:
echo http://127.0.0.1:8770
echo.
".venv\Scripts\python.exe" -m studio
if errorlevel 1 goto startup_failed
echo Studio stopped.
pause
exit /b 0
:missing_storage
echo D: is unavailable. Studio 2.0 will not silently store data on C:.
echo Set STUDIO2_DATA_DIR to a chosen writable location before starting.
goto failed
:missing_install
echo Run Install Studio 2.0.cmd first and wait for Installation complete.
goto failed
:invalid_install
echo Required packages are inconsistent. Run Install Studio 2.0.cmd again.
goto failed
:startup_failed
echo.
echo Startup failed. Please send a screenshot of the error printed above.
:failed
pause
exit /b 1
