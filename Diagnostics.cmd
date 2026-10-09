@echo off
setlocal
cd /d "%~dp0"
if not exist "python-path.txt" goto missing
set /p VCR_PYTHON=<python-path.txt
"%VCR_PYTHON%" -m studio.cli doctor
pause
exit /b
:missing
echo Python environment missing. Run Install or Repair.cmd. Install Python 3.11 x64 with the py launcher if not already installed.
pause
