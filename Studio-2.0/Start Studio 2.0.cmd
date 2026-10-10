@echo off
cd /d "%~dp0"
if not exist "D:\" if not defined STUDIO2_DATA_DIR (
 echo D: is unavailable. Set STUDIO2_DATA_DIR to your chosen location.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
 echo Run Install Studio 2.0.cmd first.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m studio
pause
