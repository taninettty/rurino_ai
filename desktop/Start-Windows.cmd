@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run Install-Windows.cmd first.
  pause
  exit /b 1
)
start "Rurino Live2D" ".venv\Scripts\pythonw.exe" "%~dp0app.py"
