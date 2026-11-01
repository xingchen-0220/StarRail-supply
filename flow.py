"""完整流程：签到 → QQ 通知 → 内置日常 → QQ 通知 → 关闭游戏。"""
import time

from . import winapi
from .config import SHOT_DIR
from .notifier import OneBotNotifier
from .signin import SigninRunner
from .vision import Automation


class FullFlow:
    def __init__(self, cfg, log, stop_event=None, on_step=None, on_progress=None, mask_provider=None):
        self.cfg = cfg
        self.log = log
        self.stop_event = stop_event
        self.on_step = on_step or (lambda text: None)
        self.on_progress = on_progress or (lambda index, total, text: None)
        self.mask_provider = mask_provider
        self.skipped = False
        self.daily_ok = None
        self.signin_ok = False
        self.notifier = OneBotNotifier(cfg, log)
        self.shots = {}

    def _stage(self, text):
        self.on_progress(7, 7, text)
        self.on_step(text)
        self.log(text)

    def run(self):
        daily_enabled = bool(self.cfg.get("daily_enabled"))
        runner = SigninRunner(
            self.cfg,
            self.log,
            stop_event=self.stop_event,
            on_step=self.on_step,
            on_progress=self.on_progress,
            mask_provider=self.mask_provider,
            defer_close=daily_enabled,
        )
        ok = runner.run()
        self.skipped = runner.skipped
        self.signin_ok = bool(ok)
        self.shots = runner.shots

        if not runner.skipped:
            self.notifier.send_signin(ok, runner.last_message or ("已领取今日列车补给" if ok else "签到未完成"), runner.shots)

        if daily_enabled and not runner.skipped and not (self.stop_event and self.stop_event.is_set()):
            if not ok:
                self.log("签到未成功，仍继续执行日常任务")
            self._stage("执行日常任务…")
            from .daily_native import NativeDailyRunner

            daily = NativeDailyRunner(
                self.cfg, self.log, self.stop_event, mask_provider=self.mask_provider
            )
            self.daily_ok, message = daily.run()
            image = self._capture_after_daily()
            self.notifier.send_daily(self.daily_ok, message, image)
            if not self.daily_ok:
                self.log("日常任务未成功")

        if runner.defer_close:
            runner.close_game()

        if self.daily_ok is False:
            return False
        return bool(ok or self.daily_ok)

    def _capture_after_daily(self):
        try:
            if not winapi.find_window(
                self.cfg.get("game_title", ""),
                self.cfg.get("window_class") or None,
                self.cfg.get("game_process", ""),
            ):
                return None
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            path = SHOT_DIR / f"daily_{time.strftime('%Y%m%d_%H%M%S')}.png"
            automation = Automation(self.cfg, logger=self.log)
            automation.screenshot_to_file(str(path))
            self.log(f"已保存日常结束截图：{path}")
            return str(path)
        except Exception as exc:
            self.log(f"日常结束截图失败：{exc}")
            return None
