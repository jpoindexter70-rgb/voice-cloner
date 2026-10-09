@echo off
setlocal
cd /d "%~dp0"
echo VOICE CONTROL ROOM ADVANCED
echo Starting the installer. Keep this window open.
echo Existing files will be backed up before installation.
if not exist "%~dp0scripts\install.ps1" (
 echo ERROR: Installer files are missing. Extract the entire ZIP before running this file.
 pause
 exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
if errorlevel 1 echo Installation stopped. Read the error above. Existing voice data was not deleted.
pause
