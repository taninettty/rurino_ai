@echo off
setlocal
cd /d "%~dp0"
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.12 x64 from https://www.python.org/downloads/windows/
  echo Include the Python Launcher, then run this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -c "import live2d; from PyQt5.QtWidgets import QApplication; from voice import Voice"
if errorlevel 1 goto fail
echo Ready. Run Start-Windows.cmd, then select your exported .model3.json.
echo This package does not include a rigged Rurino model.
pause
exit /b 0
:fail
echo Installation failed. Keep this window open and send the error to your helper.
pause
exit /b 1
