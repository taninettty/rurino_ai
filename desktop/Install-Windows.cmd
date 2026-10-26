@echo off
setlocal
cd /d "%~dp0"
rem Keep the log in one encoding: Python writes UTF-8, so cmd echoes must too.
chcp 65001 >nul
set "LOG=%~dp0install.log"
echo === Desktop install %DATE% %TIME% === > "%LOG%"

rem live2d-py ships a cp311-abi3 wheel, so every 64-bit CPython 3.11+ can use
rem it. 3.12 stays the first choice because that is what the package was tested
rem on, but a machine with only 3.11 or 3.13 must not be turned away.
set "PY="
for %%V in (3.12 3.13 3.11) do (
  if not defined PY (
    py -%%V -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
    if not errorlevel 1 set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import struct,sys; assert struct.calcsize('P') == 8 and sys.version_info >= (3, 11)" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo No 64-bit Python 3.11 or newer was found.
  echo Install Python from https://www.python.org/downloads/windows/ and run this file again.
  echo Python 3.12 x64 recommended; keeping the Python Launcher makes discovery automatic.
  pause
  exit /b 1
)
echo Using interpreter:
%PY% -c "import sys; print(sys.version); print(sys.executable)"
%PY% -c "import sys; print(sys.version); print(sys.executable)" >> "%LOG%" 2>&1

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  %PY% -m venv .venv >> "%LOG%" 2>&1
  if errorlevel 1 goto fail
)
echo Installing dependencies, this can take a few minutes ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG%" 2>&1
".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -c "import live2d; from PyQt5.QtWidgets import QApplication; from voice import Voice" >> "%LOG%" 2>&1
if errorlevel 1 goto fail
echo Ready. Run Start-Windows.cmd, then select your exported .model3.json.
echo This package does not include a rigged Rurino model.
pause
exit /b 0

:fail
echo.
echo Installation failed. Last lines of install.log:
echo ------------------------------------------------------------
powershell -NoProfile -Command "if (Test-Path 'install.log') { Get-Content 'install.log' -Tail 20 }"
echo ------------------------------------------------------------
echo Full log: %LOG%
echo Keep this window open and send the error to your helper.
pause
exit /b 1
