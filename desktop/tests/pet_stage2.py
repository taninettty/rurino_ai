"""专用桌宠页面的验证脚本：加载 pet.html，等就绪，调 say()，用 Win32 矩形截图。

与旧脚本的区别：截图坐标不再信任 pywebview 的 window.x/y，
改用 `FindWindowW` + `GetWindowRect` 拿真实窗口位置。
"""
import ctypes
from ctypes import wintypes
import functools
import http.server
import socketserver
import sys
import threading
import time
from pathlib import Path

import webview

ROOT = Path(r'D:\taninety002\22\rurino-web3d')
PORT = 8782
TITLE = 'Ruri'
OUT = Path(__file__).resolve().parents[1] / 'pet-shot.png'


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def window_rect(title):
    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = wintypes.HWND
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return None
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def wait(predicate, timeout, step=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(step)
    return False


def main():
    serve()
    window = webview.create_window(TITLE, f'http://127.0.0.1:{PORT}/pet.html',
                                   width=420, height=720, x=90, y=90,
                                   frameless=True, transparent=True, on_top=True)

    def script():
        print('WAIT_READY', flush=True)
        ok = False
        for tick in range(18):          # 最多 180 秒，每 10 秒读一次日志
            time.sleep(10)
            try:
                log = window.evaluate_js('window.petLog || []')
                ready = window.evaluate_js('!!window.petReady')
            except Exception as error:
                log, ready = ['EVAL_FAIL ' + str(error)], False
            print('T+%02ds ready=%s' % ((tick + 1) * 10, ready), log[-4:], flush=True)
            if ready:
                ok = True
                break
        print('READY', ok, flush=True)
        error = window.evaluate_js('window.petError || ""')
        if error:
            print('PAGE_ERROR', error, flush=True)
        if ok:
            motions = window.evaluate_js('window.pet.motions()')
            print('MOTIONS', len(motions or []), (motions or [])[:5], flush=True)
            window.evaluate_js("window.pet.say('ルリちゃんバッテリー充電完了！', '瑠璃乃电池充电完成！'); 1")
            time.sleep(2.0)
            rect = window_rect(TITLE)
            print('RECT', rect, flush=True)
            if rect:
                from PIL import ImageGrab
                img = ImageGrab.grab(bbox=rect)
                img.save(OUT)
                print('SHOT', OUT, img.size, flush=True)
        window.destroy()
        import os
        os._exit(0)

    threading.Thread(target=script, daemon=True).start()
    webview.start()
    return 0


if __name__ == '__main__':
    sys.exit(main())
