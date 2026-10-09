@echo off
setlocal
cd /d "%~dp0"
echo Close the studio before backup so the database and recordings are consistent.
if not exist "python-path.txt" goto missing
set /p VCR_PYTHON=<python-path.txt
"%VCR_PYTHON%" -m studio.cli backup
if errorlevel 1 echo Backup failed. See the error above.
pause
exit /b
:missing
echo Run Install or Repair.cmd first.
pause
