@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run Install-Windows.cmd first.
  pause
  exit /b 1
)
rem The launcher starts the speech service when needed and stops it on exit.
start "Rurino Live2D" ".venv\Scripts\pythonw.exe" "%~dp0launcher.py"
