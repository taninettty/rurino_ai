@echo off
setlocal
where ollama >nul 2>&1
if errorlevel 1 (
  echo Install Ollama from https://ollama.com/download/windows
  echo Start Ollama, then run this script again.
  start "" "https://ollama.com/download/windows"
  pause
  exit /b 1
)
ollama list >nul 2>&1
if errorlevel 1 (
  echo Start the Ollama application, then run this script again.
  pause
  exit /b 1
)
echo Downloading qwen3:1.7b for local conversation.
ollama pull qwen3:1.7b
if errorlevel 1 (
  echo Model download failed. Check the error above.
  pause
  exit /b 1
)
echo Ready. Select qwen3:1.7b in the chat window.
pause
