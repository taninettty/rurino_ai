@echo off
setlocal
cd /d "%~dp0"
if not exist ".voice-env\Scripts\python.exe" (
  echo Run Install-Voice-Service.cmd first.
  pause
  exit /b 1
)
set "HF_HOME=%~dp0.voice-assets\hf-cache"
set "NUMBA_CACHE_DIR=%~dp0.voice-assets\numba-cache"
rem torch and faster-whisper each ship libiomp5md.dll; loading both aborts the process.
set "KMP_DUPLICATE_LIB_OK=TRUE"
".voice-env\Scripts\python.exe" -u speech\server.py --warm
pause
