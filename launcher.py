"""游戏路径检测、启动与等待窗口。"""
import ctypes
import os
import subprocess
import time

from . import winapi

COMMON_PATHS = [
    r"E:\Star Rail Game\StarRail.exe",
    r"D:\Star Rail Game\StarRail.exe",
    r"C:\Star Rail Game\StarRail.exe",
    r"D:\Star Rail\Game\StarRail.exe",
    r"E:\Star Rail\Game\StarRail.exe",
    r"C:\Program Files\Star Rail\Game\StarRail.exe",
    r"C:\Program Files (x86)\Star Rail\Game\StarRail.exe",
    r"D:\Program Files\Star Rail\Game\StarRail.exe",
]

REGISTRY_KEYS = [
    r"Software\miHoYo\HYP\1_1\hkrpg_cn",
    r"Software\Cognosphere\HYP\1_0\hkrpg_global",
]


def _registry_game_path():
    import winreg

    for sub_key in REGISTRY_KEYS:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                install_path, _ = winreg.QueryValueEx(key, "GameInstallPath")
        except Exception:
            continue
        if not install_path:
            continue
        exe = os.path.join(install_path, "StarRail.exe")
        if os.path.isfile(exe):
            return os.path.abspath(exe)
        # 有些安装信息存的是完整 exe 路径
        if os.path.isfile(install_path) and install_path.lower().endswith("starrail.exe"):
            return os.path.abspath(install_path)
    return ""


def detect_game_path(cfg=None):
    candidates = []
    if cfg is not None:
        candidates.append(cfg.get("game_path", ""))
    candidates.append(_registry_game_path())
    candidates.extend(COMMON_PATHS)
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return ""


def game_window(cfg):
    return winapi.find_window(
        cfg.get("game_title", ""),
        cfg.get("window_class") or None,
        cfg.get("game_process", ""),
    )


def is_game_running(cfg):
    return bool(game_window(cfg)) or winapi.is_process_running(cfg.get("game_process", ""))


def launch_game(cfg, log=print, wait=True):
    """启动游戏；已运行则直接复用。返回 (成功, hwnd)。"""
    hwnd = game_window(cfg)
    if hwnd:
        log("游戏已在运行，复用现有窗口")
        winapi.activate_window(hwnd)
        return True, hwnd

    path = cfg.get("game_path", "") or detect_game_path(cfg)
    if not path or not os.path.isfile(path):
        log("未找到游戏路径，请在「设置」中选择 StarRail.exe")
        return False, 0
    cfg.set("game_path", path)

    folder = os.path.dirname(path)
    log(f"启动游戏：{path}")
    try:
        subprocess.Popen(
            [path],
            cwd=folder,
            creationflags=0x00000008 | 0x00000200,  # DETACHED_PROCESS | NEW_PROCESS_GROUP
            close_fds=True,
        )
    except OSError as exc:
        # 游戏清单要求管理员权限（WinError 740）：退化为 ShellExecute + UAC
        if getattr(exc, "winerror", None) == 740 or "740" in str(exc):
            log("游戏需要管理员权限，正在请求 UAC 授权…")
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", path, None, folder, 1
            )
            if result <= 32:
                log(f"UAC 启动失败（代码 {result}），请右键以管理员身份运行本程序")
                return False, 0
            log("已通过 UAC 启动游戏；若模拟点击无效，请以管理员身份运行本程序")
        else:
            log(f"启动失败：{exc}")
            return False, 0
    except Exception as exc:
        log(f"启动失败：{exc}")
        return False, 0

    if not wait:
        return True, 0
    timeout = float(cfg.get("launch_timeout", 180))
    hwnd = wait_for_game(cfg, timeout, log)
    return bool(hwnd), hwnd


def wait_for_game(cfg, timeout=180, log=print):
    title = cfg.get("game_title", "")
    process = cfg.get("game_process", "")
    deadline = time.monotonic() + max(5.0, float(timeout))
    last_tip = 0.0
    while time.monotonic() < deadline:
        hwnd = winapi.find_window(title, cfg.get("window_class") or None, process)
        if hwnd:
            winapi.restore_window(hwnd)
            log("已找到游戏窗口")
            return hwnd
        now = time.monotonic()
        if now - last_tip > 10:
            last_tip = now
            log("等待游戏窗口出现…")
        time.sleep(1.0)
    log("等待游戏窗口超时")
    return 0


def ensure_game(cfg, log=print, timeout=None):
    hwnd = game_window(cfg)
    if hwnd:
        winapi.activate_window(hwnd)
        return hwnd
    ok, hwnd = launch_game(cfg, log, wait=False)
    if not ok:
        return 0
    return wait_for_game(cfg, timeout or cfg.get("launch_timeout", 180), log)
