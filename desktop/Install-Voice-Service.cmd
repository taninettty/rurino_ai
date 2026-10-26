@echo off
setlocal
cd /d "%~dp0"
rem Keep the log in one encoding: Python writes UTF-8, so cmd echoes must too.
chcp 65001 >nul
set "LOG=%~dp0voice-install.log"
echo === Voice service install %DATE% %TIME% === > "%LOG%"

rem The voice environment needs a 64-bit CPython 3.11+; PyTorch 2.3.1 cpu wheels
rem cover 3.11 and 3.12. 3.12 is preferred, 3.11 is accepted instead of failing.
set "PY="
for %%V in (3.12 3.11 3.13) do (
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
  pause
  exit /b 1
)
echo Using interpreter:
%PY% -c "import sys; print(sys.version); print(sys.executable)"
%PY% -c "import sys; print(sys.version); print(sys.executable)" >> "%LOG%" 2>&1

if not exist ".voice-env\Scripts\python.exe" (
  echo Creating .voice-env ...
  %PY% -m venv .voice-env >> "%LOG%" 2>&1
  if errorlevel 1 goto fail
)
set "HF_HOME=%~dp0.voice-assets\hf-cache"
set "NUMBA_CACHE_DIR=%~dp0.voice-assets\numba-cache"
echo Installing CPU PyTorch and voice dependencies, this is a large download ...
".voice-env\Scripts\python.exe" -m pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu >> "%LOG%" 2>&1
if errorlevel 1 goto fail
".voice-env\Scripts\python.exe" -m pip install --prefer-binary -r speech\requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 goto fail
echo Downloading the voice weights and BERT model, about 1.6 GB ...
".voice-env\Scripts\python.exe" speech\download_assets.py >> "%LOG%" 2>&1
if errorlevel 1 goto fail
".voice-env\Scripts\python.exe" -c "import pyopenjtalk; pyopenjtalk.g2p('test'); from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')" >> "%LOG%" 2>&1
if errorlevel 1 goto fail
echo Ready. Run Start-Voice-Service.cmd before starting a conversation.
pause
exit /b 0

:fail
echo.
echo Voice service installation failed. Last lines of voice-install.log:
echo ------------------------------------------------------------
powershell -NoProfile -Command "if (Test-Path 'voice-install.log') { Get-Content 'voice-install.log' -Tail 20 }"
echo ------------------------------------------------------------
echo Full log: %LOG%
echo Keep this error window for troubleshooting.
pause
exit /b 1
