@echo off
setlocal
cd /d "%~dp0"
if not exist "python-path.txt" goto missing
set /p VCR_PYTHON=<python-path.txt
if not exist "%VCR_PYTHON%" goto missing
"%VCR_PYTHON%" -m studio.cli download-models --engine all
if errorlevel 1 goto failed
"%VCR_PYTHON%" -m studio.cli verify-models --engine all
if errorlevel 1 goto failed
echo Models downloaded and verified.
pause
exit /b
:failed
echo Model download or verification failed. Check internet access and the error above. Existing voice recordings are unchanged.
pause
exit /b 1
:missing
echo Run Install or Repair.cmd first.
pause
exit /b 1
