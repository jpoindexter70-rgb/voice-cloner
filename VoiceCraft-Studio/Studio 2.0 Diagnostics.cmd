@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-ai\Scripts\python.exe" goto missing_install
".venv-ai\Scripts\python.exe" scripts\diagnostics.py
pause
exit /b 0
:missing_install
echo The separate Studio 2.0 environment is not installed yet.
echo Run Open Studio 2.0.cmd from this folder.
pause
exit /b 1
