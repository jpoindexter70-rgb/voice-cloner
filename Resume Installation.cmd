@echo off
setlocal
cd /d "%~dp0"
echo VOICE CONTROL ROOM ADVANCED - RESUME AFTER VERIFIED BACKUP
echo Use this only when BOTH backups completed before an installation error.
echo If you changed recordings or profiles since then, use Install or Repair.cmd.
echo This will recheck existing archives but will not copy a new full backup.
choice /C YN /N /M "Have both backups completed, with no recording/profile changes since then? [Y/N] "
if errorlevel 2 exit /b 1
if not exist "%~dp0scripts\install.ps1" (
 echo ERROR: Extract the entire updated ZIP before running this file.
 pause
 exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" -ResumeVerifiedBackup
if errorlevel 1 echo Resume stopped. Read the error above. Existing voice files were not deleted.
pause
