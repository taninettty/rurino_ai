"""Single entry point for the desktop pet.

Starts the voice service only when it is not already running, then launches the
pet itself, and cleans up the service on exit. Runs under pythonw so no console
window appears; anything that goes wrong lands in launcher.log.
"""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
PYTHONW = ROOT / '.venv' / 'Scripts' / 'pythonw.exe'
VOICE_PYTHONW = ROOT / '.voice-env' / 'Scripts' / 'pythonw.exe'
LOG_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'RurinoLive2D'
LOG_DIR.mkdir(parents=True, exist_ok=True)
VOICE_BASE = 'http://127.0.0.1:8765'
MUTEX_NAME = 'RurinoLive2D.Desktop.Singleton'
ERROR_ALREADY_EXISTS = 183


def log(message):
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with (LOG_DIR / 'launcher.log').open('a', encoding='utf-8') as stream:
            stream.write(f'{stamp} {message}\n')
    except OSError:
        pass


def voice_ready(timeout=2.0):
    try:
        with urlopen(VOICE_BASE + '/health', timeout=timeout) as response:
            return json.loads(response.read(65536)).get('service') == 'rurino-speech'
    except Exception:
        return False


def start_voice():
    """Start the speech service hidden; return the process, or None on failure."""
    if not VOICE_PYTHONW.is_file():
        log('voice env missing, running without speech')
        return None
    environment = dict(os.environ,
                       HF_HOME=str(ROOT / '.voice-assets' / 'hf-cache'),
                       NUMBA_CACHE_DIR=str(ROOT / '.voice-assets' / 'numba-cache'),
                       KMP_DUPLICATE_LIB_OK='TRUE')
    try:
        voice_log = (LOG_DIR / 'voice.log').open('a', encoding='utf-8')
        process = subprocess.Popen(
            [str(VOICE_PYTHONW), '-u', 'speech/server.py', '--warm'],
            cwd=str(ROOT), env=environment, stdin=subprocess.DEVNULL,
            stdout=voice_log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        log(f'voice service started, pid {process.pid}')
        return process
    except Exception as error:
        log(f'voice service failed to start: {error}')
        return None


def main():
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        log('another instance is running, exiting')
        return 0
    try:
        started_voice = None
        if voice_ready():
            log('voice service already running')
        else:
            started_voice = start_voice()

        if not PYTHONW.is_file():
            log('.venv missing; run Install-Windows.cmd first')
            return 1
        log('starting desktop pet')
        pet = subprocess.Popen([str(PYTHONW), 'app.py'], cwd=str(ROOT))
        code = pet.wait()
        log(f'desktop pet exited with {code}')
        return code
    finally:
        if started_voice and started_voice.poll() is None:
            # Only stop the service this launcher started; a manually started
            # one belongs to the user.
            started_voice.terminate()
            try:
                started_voice.wait(timeout=10)
            except subprocess.TimeoutExpired:
                started_voice.kill()
            log('voice service stopped')
        if mutex:
            kernel32.CloseHandle(mutex)


if __name__ == '__main__':
    sys.exit(main() or 0)
