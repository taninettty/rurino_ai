@echo off
setlocal
cd /d "%~dp0"
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.12 x64 with Python Launcher first.
  pause
  exit /b 1
)
if not exist ".voice-env\Scripts\python.exe" (
  py -3.12 -m venv .voice-env
  if errorlevel 1 goto fail
)
set "HF_HOME=%~dp0.voice-assets\hf-cache"
set "NUMBA_CACHE_DIR=%~dp0.voice-assets\numba-cache"
".voice-env\Scripts\python.exe" -m pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto fail
".voice-env\Scripts\python.exe" -m pip install --prefer-binary -r speech\requirements.txt
if errorlevel 1 goto fail
".voice-env\Scripts\python.exe" speech\download_assets.py
if errorlevel 1 goto fail
".voice-env\Scripts\python.exe" -c "import pyopenjtalk; pyopenjtalk.g2p('test'); from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
if errorlevel 1 goto fail
echo Ready. Run Start-Voice-Service.cmd before starting a conversation.
pause
exit /b 0
:fail
echo Voice service installation failed. Keep this error window for troubleshooting.
pause
exit /b 1
