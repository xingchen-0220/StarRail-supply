"""固定签到流程：启动游戏 → 点击进入 → 领取今日奖励 → 关闭游戏。"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

from . import launcher, winapi
from .config import SHOT_DIR
from .vision import Automation

TITLE_TEXTS = ["点击进入", "点击屏幕", "开始游戏"]
REWARD_TEXTS = [
    "点击领取今日补给",
    "点击领取今日奖励",
    "领取今日补给",
    "领取今日奖励",
    "今日补给",
    "今日奖励",
]
MAIN_TEXTS = ["开拓力", "每日实训", "跃迁", "编队", "三月七"]
SUCCESS_TEXTS = ["签到成功", "领取成功", "已领取", "领取完成", "今日补给已领取"]

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE


def _acquire_lock():
    """跨进程互斥，避免图形界面和计划任务同时操作游戏。"""
    handle = _kernel32.CreateMutexW(None, False, "Local\\StarRailDaily_Signin")
    if not handle:
        return None
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        _kernel32.CloseHandle(handle)
        return None
    return handle


def _release_lock(handle):
    if handle:
        try:
            _kernel32.ReleaseMutex(handle)
            _kernel32.CloseHandle(handle)
        except Exception:
            pass


class SigninRunner:
    def __init__(self, cfg, log, stop_event=None, on_step=None, on_progress=None,
                 mask_provider=None, defer_close=False):
        self.cfg = cfg
        self.log = log
        self.stop_event = stop_event
        self.on_step = on_step or (lambda text: None)
        self.on_progress = on_progress or (lambda index, total, text: None)
        self.mask_provider = mask_provider
        self.auto = None
        self.skipped = False
        self.defer_close = defer_close
        self.shots = {}
        self.was_running = False
        self.game_closed = False
        self.last_message = ""

    # ------------------------------------------------------------ 基础 --
    def stopped(self):
        return bool(self.stop_event and self.stop_event.is_set())

    def step(self, text):
        self.on_step(text)
        self.log(text)

    def stage(self, index, total, text):
        """同时更新日志与左下角浮窗的步骤进度。"""
        try:
            self.on_progress(index, total, text)
        except Exception:
            pass
        self.step(text)

    def _sleep(self, seconds):
        end = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < end:
            if self.stopped():
                return False
            time.sleep(min(0.2, max(0.0, end - time.monotonic())))
        return not self.stopped()

    def _wait_text(self, texts, timeout, include=True, interval=1.5):
        """在 timeout 内轮询识别候选文字，返回命中的结果或 None。"""
        deadline = time.monotonic() + max(1.0, float(timeout))
        while time.monotonic() < deadline:
            if self.stopped():
                return None
            try:
                found = self.auto.find_any_text(texts, include=include)
                if found:
                    return found
            except Exception as exc:
                self.log(f"识别失败：{exc}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if not self._sleep(min(interval, remaining)):
                return None
        return None

    def _exists(self, texts, include=False):
        try:
            return self.auto.find_any_text(texts, include=include)
        except Exception:
            return None

    def _click(self, found, label):
        x, y = found["center"]
        self.log(f"点击「{found['text']}」 ({int(x)}, {int(y)})")
        self.auto.focus()
        winapi.click(int(x), int(y))
        self._sleep(float(self.cfg.get("click_delay", 0.6)))

    def _click_center(self):
        hwnd = self.auto.ensure_window()
        region = winapi.client_rect(hwnd)
        if not region:
            return
        left, top, width, height = region
        winapi.click(left + width // 2, top + height // 2)
        self._sleep(0.8)

    def capture(self, kind):
        """把当前游戏画面保存为指定类型的截图。"""
        if self.auto is None:
            return None
        try:
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            path = SHOT_DIR / f"{kind}_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.auto.screenshot_to_file(str(path))
            self.shots[kind] = str(path)
            self.log(f"已保存截图：{path}")
            return str(path)
        except Exception as exc:
            self.log(f"保存截图失败：{exc}")
            return None

    def _save_failure_shot(self):
        self.capture("failure")
        try:
            lines = self.auto.ocr_lines()
            if lines:
                self.log("当前画面识别到的文字：")
                for x, y, text, score in lines[:20]:
                    self.log(f"  ({x}, {y}) {text} [{score:.2f}]")
        except Exception:
            pass

    # ------------------------------------------------------------ 流程 --
    def run(self):
        lock = _acquire_lock()
        if lock is None:
            self.skipped = True
            self.log("已有签到任务正在进行，本次跳过")
            return False
        try:
            return self._run()
        finally:
            _release_lock(lock)

    def _run(self):
        self.stage(1, 7, "启动游戏")
        was_running = bool(launcher.game_window(self.cfg))
        self.was_running = was_running
        if was_running:
            self.step("游戏已在运行，直接使用当前窗口")
            hwnd = launcher.game_window(self.cfg)
        else:
            path = self.cfg.get("game_path", "") or launcher.detect_game_path(self.cfg)
            if not path or not os.path.isfile(path):
                self.last_message = "未找到游戏路径"
                self.log("未找到游戏路径，请在主界面选择 StarRail.exe")
                return False
            self.cfg.set("game_path", path)
            self.step("正在启动游戏…")
            ok, hwnd = launcher.launch_game(self.cfg, self.log, wait=False)
            if not ok:
                return False
            hwnd = launcher.wait_for_game(
                self.cfg, float(self.cfg.get("launch_timeout", 180)), self.log
            )
            if not hwnd:
                self.log("等待游戏窗口超时")
                return False

        winapi.activate_window(hwnd)
        self.auto = Automation(self.cfg, logger=self.log)
        self.auto.window = hwnd
        if self.mask_provider:
            self.auto.mask_provider = self.mask_provider
        self._sleep(1.0)

        # 1. 找「点击进入」
        self.stage(2, 7, "等待游戏加载…")
        title = self._wait_text(TITLE_TEXTS, 8 if was_running else float(self.cfg.get("title_timeout", 120)))
        if not title:
            if self._exists(MAIN_TEXTS):
                self.step("游戏已登录，跳过「点击进入」")
            elif was_running:
                title = self._wait_text(TITLE_TEXTS, float(self.cfg.get("title_timeout", 120)))
            if not title and not self._exists(MAIN_TEXTS):
                self.last_message = "等待「点击进入」超时"
                self.step("签到失败：等待「点击进入」超时")
                self._save_failure_shot()
                return False

        if title:
            self.stage(3, 7, "正在进入游戏…")
            self._click(title, "点击进入")
            if self.stopped():
                return False
            self.step(f"等待 {float(self.cfg.get('after_enter_wait', 4.0)):.0f} 秒进入游戏…")
            if not self._sleep(float(self.cfg.get("after_enter_wait", 4.0))):
                return False

        # 2. 找「点击领取今日奖励」
        self.stage(4, 7, "等待领取入口…")
        reward = self._wait_text(
            REWARD_TEXTS, float(self.cfg.get("reward_timeout", 60)) * 0.5
        )
        if not reward:
            self.step("暂未找到领取入口，点击屏幕后继续等待…")
            prompt = self._wait_text(["点击屏幕"], 3)
            if prompt:
                self._click(prompt, "点击屏幕")
            self._click_center()
            reward = self._wait_text(REWARD_TEXTS, float(self.cfg.get("reward_timeout", 60)) * 0.5)
        if not reward:
            self.step("签到失败：等待「点击领取今日奖励」超时")
            self.last_message = "未发现签到弹窗（可能今日已领取，或未开通列车补给/月卡）"
            self.capture("no_popup")
            self._save_failure_shot()
            return False

        self.stage(5, 7, "正在领取…")
        self._click(reward, "领取今日奖励")
        if self.stopped():
            return False

        # 等待「领取成功」出现的那一瞬间截图
        success = self._wait_text(SUCCESS_TEXTS, 5.0, include=True, interval=0.5)
        self.capture("success")
        if success:
            self.log(f"出现领取成功提示：「{success['text']}」")
        else:
            self.log("未识别到「领取成功」文字，已按当前画面保存截图")

        self.step(f"等待 {float(self.cfg.get('after_click_wait', 2.5)):.1f} 秒领取…")
        if not self._sleep(float(self.cfg.get("after_click_wait", 2.5))):
            return False

        # 3. 点一下屏幕完成领取
        self.stage(6, 7, "确认领取…")
        self._click_center()
        if not self._sleep(2.0):
            return False

        if self.defer_close:
            self.stage(7, 7, "签到完成（等待日常）")
            self.step("签到完成，保留游戏窗口等待日常任务")
        elif self.cfg.get("exit_game", True) and not was_running:
            self.stage(7, 7, "关闭游戏")
            self._close_game()
        else:
            self.stage(7, 7, "签到完成")
            if self.cfg.get("exit_game", True):
                self.log("游戏原本已在运行，签到后保持游戏开启")
        self.last_message = "已领取今日列车补给"
        self.step("签到完成")
        return True

    def close_game(self):
        """签到/日常流程结束后，按配置关闭游戏（仅当游戏由本次流程启动）。"""
        if self.game_closed:
            return
        if self.was_running:
            self.log("游戏原本已在运行，保持开启")
            return
        if not self.cfg.get("exit_game", True):
            return
        self.stage(7, 7, "关闭游戏")
        self._close_game()
        self.game_closed = True

    def _close_game(self):
        process = self.cfg.get("game_process", "StarRail.exe")
        self.step(f"关闭游戏：{process}")
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/IM", process],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=0x08000000,
            )
        except Exception as exc:
            self.log(f"关闭游戏失败：{exc}")
            return
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if not winapi.is_process_running(process):
                self.log("游戏已关闭")
                return
            time.sleep(1.0)
        self.log("游戏关闭超时，请手动检查")
