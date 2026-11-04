"""Windows 空闲检测：用户多久没动键鼠。

`GetLastInputInfo` 返回的是系统启动以来的毫秒数，和 `GetTickCount` 同源，
所以用两个值相减得到"距上次输入过了多久"。非 Windows 平台退化为 0。
"""
import ctypes
import sys
import time


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]


def seconds_since_input():
    """返回距上次键盘/鼠标输入的秒数；取不到时返回 0.0。"""
    if sys.platform != 'win32':
        return 0.0
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        elapsed_ms = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0.0, elapsed_ms / 1000.0)
    except Exception:
        return 0.0


def monotonic():
    return time.monotonic()
