@echo off
setlocal
cd /d "%~dp0"
echo AI Voice Cloning Studio 2.0 - Installation
echo.
if exist ".venv\Scripts\python.exe" goto install_packages
echo Checking Python 3.11...
py -3.11 --version
if errorlevel 1 goto missing_python
echo Creating the separate Studio 2.0 environment...
py -3.11 -m venv .venv
if errorlevel 1 goto environment_failed
:install_packages
echo Installing required packages. Keep this window open...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto packages_failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto packages_failed
echo.
echo Installation complete. Run Start Studio 2.0.cmd.
pause
exit /b 0
:missing_python
echo.
echo Python 3.11 or the Windows Python launcher is missing.
echo Install 64-bit Python 3.11 from python.org with the Python launcher enabled.
echo Then run this installer again. Existing applications are not changed.
goto failed
:environment_failed
echo.
echo Unable to create the environment. Extract the ZIP into a writable folder.
goto failed
:packages_failed
echo.
echo Package installation or validation failed. The error is printed above.
echo Please send a screenshot of this window.
:failed
pause
exit /b 1
