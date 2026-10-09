@echo off
setlocal
cd /d "%~dp0"
if not exist "python-path.txt" goto missing
set /p VCR_PYTHON=<python-path.txt
if not exist "%VCR_PYTHON%" goto missing
"%VCR_PYTHON%" -m studio.cli serve --load-engine
if errorlevel 1 (
 echo Startup stopped. Run Diagnostics.cmd for details, or Install or Repair.cmd to repair packages.
 pause
)
exit /b
:missing
echo Python environment is missing. Double-click Install or Repair.cmd first.
pause
