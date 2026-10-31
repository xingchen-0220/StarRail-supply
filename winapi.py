"""Windows 窗口、截图与键鼠输入封装（ctypes，无 pyautogui 依赖）。"""
import ctypes
import subprocess
import time
from ctypes import wintypes

import mss
from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

# ---------------------------------------------------------------- DPI ----
def set_dpi_aware():
    """让进程坐标与物理像素一致，避免缩放导致点击偏移。"""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


# ------------------------------------------------------------- window ----
def _window_text(hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def list_windows():
    result = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = _window_text(hwnd)
            if title:
                result.append((hwnd, title, _window_class(hwnd)))
        return True

    user32.EnumWindows(callback, 0)
    return result


def find_window(title: str, window_class: str | None = None, process_hint: str = ""):
    """按标题查找窗口：优先完全匹配，其次包含匹配。"""
    title = (title or "").strip()
    windows = list_windows()
    if window_class:
        windows = [w for w in windows if w[2].lower() == window_class.lower()]
    if not windows:
        return 0
    for hwnd, text, _ in windows:
        if text.strip() == title:
            return hwnd
    if title:
        for hwnd, text, _ in windows:
            if title in text:
                return hwnd
    if process_hint:
        # 标题可能被游戏改写，退化为进程窗口：找有窗口的进程
        try:
            for hwnd, text, cls in list_windows():
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if process_hint.lower() in _process_name(pid.value).lower():
                    return hwnd
        except Exception:
            pass
    return 0


def _process_name(pid: int) -> str:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1]
    finally:
        kernel32.CloseHandle(handle)
    return ""


def is_process_running(image_name: str) -> bool:
    if not image_name:
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/NH"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=0x08000000,
        ).stdout
        return image_name.lower() in (out or "").lower()
    except Exception:
        return False


def is_iconic(hwnd) -> bool:
    return bool(user32.IsIconic(hwnd))


def restore_window(hwnd):
    if is_iconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.3)


def activate_window(hwnd) -> bool:
    """把游戏窗口切到前台（绕过部分前台锁定限制）。"""
    if not hwnd:
        return False
    restore_window(hwnd)
    if user32.GetForegroundWindow() == hwnd:
        return True
    try:
        current_tid = kernel32.GetCurrentThreadId()
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        attached = False
        if target_tid and target_tid != current_tid:
            attached = bool(user32.AttachThreadInput(current_tid, target_tid, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if attached:
            user32.AttachThreadInput(current_tid, target_tid, False)
    except Exception:
        pass
    time.sleep(0.15)
    return user32.GetForegroundWindow() == hwnd


def client_rect(hwnd):
    """返回窗口客户区在屏幕上的 (left, top, width, height)。"""
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    point = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    return point.x, point.y, width, height


def capture_window(hwnd):
    """截取窗口客户区，返回 (PIL.Image RGB, (left, top, width, height))。"""
    region = client_rect(hwnd)
    if not region:
        return None, None
    left, top, width, height = region
    try:
        with mss.mss() as sct:
            raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
            image = Image.frombytes("RGB", raw.size, raw.rgb)
            return image, region
    except Exception:
        image = _print_window(hwnd, width, height)
        if image is not None:
            return image, region
        return None, None


def _print_window(hwnd, width, height):
    """PrintWindow 兜底截图（部分独占全屏/遮挡场景）。"""
    try:
        import win32con
        import win32gui
        import win32ui

        hdc = win32gui.GetWindowDC(hwnd)
        src = win32ui.CreateDCFromHandle(hdc)
        mem = src.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(src, width, height)
        mem.SelectObject(bitmap)
        result = ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2)
        info = bitmap.GetInfo()
        bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB", (info["bmWidth"], info["bmHeight"]), bits, "raw", "BGRX", 0, 1
        )
        win32gui.DeleteObject(bitmap.GetHandle())
        mem.DeleteDC()
        src.DeleteDC()
        win32gui.ReleaseDC(hwnd, hdc)
        if result != 1:
            return None
        return image
    except Exception:
        return None


# -------------------------------------------------------------- input ----
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _send(*inputs):
    if not inputs:
        return
    array = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))


def _mouse_input(flags, data=0):
    return INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, data, flags, 0, 0))


def _key_input(vk, up=False, scan=False):
    flags = KEYEVENTF_KEYUP if up else 0
    # 使用虚拟键码注入（与 pyautogui 一致），Windows 会自动补全扫描码；
    # 部分游戏对纯扫描码注入不响应。
    return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, user32.MapVirtualKeyW(vk, 0), flags, 0, 0))


def move_mouse(x, y):
    user32.SetCursorPos(int(x), int(y))


def mouse_down(x=None, y=None):
    if x is not None and y is not None:
        move_mouse(x, y)
    _send(_mouse_input(MOUSEEVENTF_LEFTDOWN))


def mouse_up():
    _send(_mouse_input(MOUSEEVENTF_LEFTUP))


def click(x, y, count=1, interval=0.06):
    move_mouse(x, y)
    time.sleep(0.03)
    for _ in range(max(1, int(count))):
        _send(_mouse_input(MOUSEEVENTF_LEFTDOWN))
        time.sleep(0.02)
        _send(_mouse_input(MOUSEEVENTF_LEFTUP))
        time.sleep(interval)


def right_click(x, y):
    move_mouse(x, y)
    time.sleep(0.03)
    _send(_mouse_input(MOUSEEVENTF_RIGHTDOWN))
    time.sleep(0.02)
    _send(_mouse_input(MOUSEEVENTF_RIGHTUP))


def drag(x1, y1, x2, y2, duration=0.5):
    duration = max(0.0, float(duration or 0.0))
    move_mouse(x1, y1)
    time.sleep(0.05)
    _send(_mouse_input(MOUSEEVENTF_LEFTDOWN))
    time.sleep(0.05)
    steps = max(1, int(duration * 60))
    for index in range(1, steps + 1):
        ratio = index / steps
        move_mouse(x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio)
        time.sleep(duration / steps)
    time.sleep(0.05)
    _send(_mouse_input(MOUSEEVENTF_LEFTUP))


KEY_NAMES = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "menu": 0x12,
    "backspace": 0x08,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "`": 0xC0,
    "~": 0xC0,
    "-": 0xBD,
    "=": 0xBB,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
    ";": 0xBA,
    "'": 0xDE,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    "capslock": 0x14,
    "insert": 0x2D,
    "delete": 0x2E,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}


def vk_of(key: str):
    key = (key or "").strip()
    if not key:
        return None
    lower = key.lower()
    if lower in KEY_NAMES:
        return KEY_NAMES[lower]
    if len(key) == 1:
        if key.isdigit():
            return ord(key)
        if key.isalpha():
            return ord(key.upper())
    if lower.startswith("f") and lower[1:].isdigit():
        number = int(lower[1:])
        if 1 <= number <= 12:
            return 0x70 + number - 1
    return None


def key_down(key: str) -> bool:
    vk = vk_of(key)
    if vk is None:
        return False
    _send(_key_input(vk, scan=True))
    return True


def key_up(key: str) -> bool:
    vk = vk_of(key)
    if vk is None:
        return False
    _send(_key_input(vk, up=True, scan=True))
    return True


def press_key(key: str, duration=0.1) -> bool:
    vk = vk_of(key)
    if vk is None:
        return False
    _send(_key_input(vk, scan=True))
    time.sleep(max(0.02, float(duration or 0.0)))
    _send(_key_input(vk, up=True, scan=True))
    return True
