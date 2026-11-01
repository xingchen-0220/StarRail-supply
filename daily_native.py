"""内置日常：邮件、委托、拟造花萼、支援、无名勋礼、每日实训（不依赖三月七）。"""
import re
import time

from . import launcher, winapi
from .config import RESOURCE
from .vision import Automation

ASSETS = RESOURCE / "assets" / "daily"


class NativeDailyRunner:
    def __init__(self, cfg, log, stop_event=None, mask_provider=None):
        self.cfg = cfg
        self.log = log
        self.stop_event = stop_event
        self.mask_provider = mask_provider
        self.auto = None
        self.width = 1920
        self.height = 1080

    def stopped(self):
        return bool(self.stop_event and self.stop_event.is_set())

    def sleep(self, seconds):
        end = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < end:
            if self.stopped():
                return False
            time.sleep(min(0.2, max(0.0, end - time.monotonic())))
        return not self.stopped()

    def run(self):
        hwnd = launcher.game_window(self.cfg)
        if not hwnd:
            self.log("内置日常：游戏未运行")
            return False, "游戏未运行"
        winapi.activate_window(hwnd)
        self.auto = Automation(self.cfg, logger=self.log)
        self.auto.window = hwnd
        if self.mask_provider:
            self.auto.mask_provider = self.mask_provider
        region = winapi.client_rect(hwnd)
        if region:
            self.width, self.height = region[2], region[3]

        self.log("内置日常：确认菜单")
        self._ensure_menu()

        results = []
        results.append(("邮件", self._mail()))
        self._ensure_menu()
        results.append(("委托", self._dispatch()))
        self._ensure_menu()
        results.append(("消耗开拓力", self._consume_stamina()))
        self._ensure_menu()
        results.append(("支援奖励", self._assist()))
        self._ensure_menu()
        results.append(("无名勋礼", self._pass()))
        self._ensure_menu()
        results.append(("每日实训", self._training()))
        self._ensure_menu()
        winapi.press_key("esc", 0.1)
        self.sleep(0.8)

        self.log("内置日常：完成")
        summary = "；".join(f"{name}{'完成' if ok else '未完成'}" for name, ok in results)
        return any(ok for _, ok in results), summary

    # ---------------------------------------------------------- 基础 --
    def _ensure_menu(self):
        """从主界面/任意面板回到手机菜单。"""
        for _ in range(4):
            if self.stopped():
                return False
            try:
                found = self.auto.find_text(
                    ["指南", "委托", "商店"], include=False,
                    crop=(0.65, 0.28, 0.34, 0.62), retries=1,
                )
            except Exception:
                found = None
            if found:
                return True
            winapi.press_key("esc", 0.1)
            self.sleep(1.2)
        self.log("内置日常：无法确认手机菜单")
        return False

    def _click_norm(self, x_ratio, y_ratio):
        self.auto.focus()
        winapi.click(int(self.width * x_ratio), int(self.height * y_ratio))
        self.sleep(0.6)

    def _close_popup(self):
        """点击右下/右上常见关闭按钮。"""
        try:
            found = self.auto.find_image(str(ASSETS / "close.png"), 0.8, retries=2)
            if found:
                x, y = found["center"]
                winapi.click(int(x), int(y))
                self.sleep(0.8)
                return True
        except Exception:
            pass
        return False

    def _click_text(self, text, crop=(0, 0, 1, 1), include=False, retries=3, wait=1.2):
        try:
            found = self.auto.find_text([text], include=include, crop=crop, retries=retries)
        except Exception as exc:
            self.log(f"内置日常：识别「{text}」失败：{exc}")
            return False
        if not found:
            return False
        x, y = found["center"]
        self.log(f"内置日常：点击「{found['text']}」")
        self.auto.focus()
        winapi.click(int(x), int(y))
        self.sleep(wait)
        return True

    # ---------------------------------------------------------- 邮件 --
    def _mail(self):
        self.log("内置日常：领取邮件")
        self._click_norm(0.984, 0.241)
        self.sleep(1.6)
        ok = self._click_text("全部领取", crop=(0, 0.85, 1, 0.15), include=True, retries=4)
        if not ok:
            self.log("内置日常：没有可领取的邮件")
        else:
            self.sleep(1.5)
            self._close_popup()
        self._ensure_menu()
        return ok

    # ---------------------------------------------------------- 委托 --
    def _dispatch(self):
        self.log("内置日常：领取委托奖励")
        self._click_norm(0.889, 0.366)
        self.sleep(1.8)
        ok = self._click_text("领取奖励", crop=(0.55, 0.78, 0.45, 0.2), include=True, retries=4)
        if not ok:
            if self.auto.find_text(["委托派遣中"], include=True, retries=1):
                self.log("内置日常：委托仍在派遣中，暂无可领取奖励")
            else:
                self.log("内置日常：未发现可领取的委托奖励")
        else:
            self.sleep(1.5)
            self._close_popup()
        self._ensure_menu()
        return ok

    def _assist(self):
        """菜单 → ... → 漫游签证 → 领取支援奖励。"""
        self.log("内置日常：领取支援奖励")
        self._ensure_menu()
        found = self.auto.find_image(
            str(ASSETS / "more.png"), 0.8, crop=(0.6, 0.0, 0.4, 0.2), retries=3
        )
        if not found:
            self.log("内置日常：未找到菜单「...」按钮")
            return False
        x, y = found["center"]
        winapi.click(int(x), int(y))
        self.sleep(2.0)
        if not self._click_text("漫游签证", crop=(0.65, 0.0, 0.35, 0.35), include=True, retries=3):
            self.log("内置日常：未找到「漫游签证」")
            winapi.press_key("esc", 0.1)
            return False
        self.sleep(2.0)
        gift = self.auto.find_image(str(ASSETS / "assist_gift.png"), 0.85, retries=4)
        if not gift:
            self.log("内置日常：没有可领取的支援奖励")
            winapi.press_key("esc", 0.1)
            return False
        x, y = gift["center"]
        winapi.click(int(x), int(y))
        self.sleep(1.5)
        self._close_popup()
        winapi.press_key("esc", 0.1)
        self.sleep(1.0)
        return True

    def _pass(self):
        """菜单 → 无名勋礼 → 一键领取。"""
        self.log("内置日常：领取无名勋礼")
        self._ensure_menu()
        if not self._click_text("无名勋礼", crop=(0.65, 0.45, 0.34, 0.35), include=False, retries=3):
            self.log("内置日常：未找到无名勋礼入口")
            return False
        self.sleep(2.5)
        # 第二页「任务」：一键领取本周/本期任务奖励
        self._click_norm(955 / 1920, 62 / 1080)
        self.sleep(1.5)
        claimed = self._click_text("一键领取", crop=(0.62, 0.78, 0.38, 0.18), include=True, retries=2)
        if not claimed:
            claimed = self._click_text("键领取", crop=(0.62, 0.78, 0.38, 0.18), include=True, retries=2)
        if claimed:
            self.sleep(2.0)
            self._close_popup()
            self.log("内置日常：无名勋礼任务奖励已领取")
            winapi.press_key("esc", 0.1)
            self.sleep(1.0)
            return True
        if not self.auto.find_image(str(ASSETS / "pass_receive.png"), 0.8, retries=3):
            self.log("内置日常：没有可领取的无名勋礼奖励")
            winapi.press_key("esc", 0.1)
            return False
        found = self.auto.find_image(str(ASSETS / "pass_receive.png"), 0.8, retries=1)
        if found:
            x, y = found["center"]
            winapi.click(int(x), int(y))
        self.sleep(1.5)
        self._close_popup()
        winapi.press_key("esc", 0.1)
        self.sleep(1.0)
        return True

    def _open_daily_guide(self):
        if not self._click_text("指南", crop=(0.65, 0.55, 0.34, 0.35), include=False, retries=3):
            self._click_norm(0.687, 0.726)
        self.sleep(2.2)
        found = self.auto.find_image(str(ASSETS / "enter_guide2.png"), 0.8, retries=2)
        if found:
            x, y = found["center"]
            winapi.click(int(x), int(y))
            self.sleep(1.5)

    # ------------------------------------------------------ 每日实训 --
    def _read_stamina(self):
        try:
            for x, y, text, _ in self.auto.ocr_lines():
                if x < self.width * 0.72 or y > self.height * 0.12:
                    continue
                match = re.search(r"(\d+)\s*/\s*(\d+)", text)
                if match and int(match.group(2)) >= 100:
                    return int(match.group(1)), int(match.group(2))
        except Exception as exc:
            self.log(f"内置日常：读取开拓力失败：{exc}")
        return None, None

    def _set_challenge_count(self, runs):
        current = 1
        try:
            for x, y, text, _ in self.auto.ocr_lines():
                match = re.search(r"挑战次数\s*(\d+)", text)
                if match:
                    current = int(match.group(1))
                    break
        except Exception:
            pass
        for _ in range(max(0, runs - current)):
            self._click_norm(1832 / 1920, 879 / 1080)
            self.sleep(0.18)
        self.log(f"内置日常：挑战次数 {current} → {runs}")

    def _consume_stamina(self):
        """前往拟造花萼，按剩余开拓力挑战，顺便完成击杀/支援任务。"""
        self.log("内置日常：进入拟造花萼消耗开拓力")
        self._open_daily_guide()
        if not self.auto.find_text(["累计消耗120"], include=True, crop=(0.1, 0.38, 0.8, 0.16), retries=3):
            self.log("内置日常：没有找到「累计消耗120点开拓力」任务")
            return False
        self._click_norm(410 / 1920, 813 / 1080)
        self.sleep(4.0)
        if not self.auto.find_text(["生存索引"], include=True, retries=4):
            self.log("内置日常：未进入生存索引")
            winapi.press_key("esc", 0.1)
            return False
        # 左侧切换到「拟造花萼（金）」，默认可能停在培养目标页
        self._click_norm(302 / 1920, 570 / 1080)
        self.sleep(1.5)
        if not self.auto.find_text(["回忆之蕾"], include=True, crop=(0.4, 0.3, 0.3, 0.16), retries=3):
            self.log("内置日常：未找到回忆之蕾")
            winapi.press_key("esc", 0.1)
            return False
        self._click_norm(1531 / 1920, 433 / 1080)
        self.sleep(4.0)
        runs = 12
        if self.cfg.get("daily_clear_power", False):
            stamina, _ = self._read_stamina()
            if stamina is not None:
                if stamina < 10:
                    self.log(f"内置日常：开拓力不足（{stamina}），跳过清体力")
                    winapi.press_key("esc", 0.1)
                    return False
                runs = max(1, min(24, stamina // 10))
                self.log(f"内置日常：当前开拓力 {stamina}，计划挑战 {runs} 次")
        self._set_challenge_count(runs)
        if not self._click_text("挑战", crop=(0.72, 0.86, 0.22, 0.12), include=False, retries=4):
            self._click_norm(1567 / 1920, 967 / 1080)
        self.sleep(3.0)
        if self.auto.find_text(["支援"], include=False, crop=(0.5, 0.85, 0.25, 0.12), retries=2):
            self._click_norm(1053 / 1920, 969 / 1080)
            self.sleep(2.0)
            self._click_norm(200 / 1920, 250 / 1080)
            self.sleep(0.8)
            self._click_text("确认", crop=(0.75, 0.86, 0.2, 0.12), include=False, retries=2)
        if not self._click_text("开始挑战", crop=(0.75, 0.86, 0.2, 0.12), include=True, retries=5):
            self.log("内置日常：无法开始挑战")
            winapi.press_key("esc", 0.1)
            return False
        self.log("内置日常：战斗开始，等待自动战斗")
        self.sleep(8.0)
        if self.auto.find_image(str(ASSETS / "not_auto.png"), 0.8, crop=(0, 0.82, 0.1, 0.15), retries=2):
            winapi.press_key("v", 0.1)
            self.log("内置日常：已开启自动战斗")
        deadline = time.monotonic() + 900
        result = ""
        while time.monotonic() < deadline and not self.stopped():
            self.sleep(3.0)
            if self.auto.find_image(str(ASSETS / "fight_again.png"), 0.85, retries=1):
                result = "again"
                break
            if self.auto.find_image(str(ASSETS / "fight_fail.png"), 0.85, retries=1):
                result = "fail"
                break
            if self.auto.find_text(["挑战成功", "战斗胜利"], include=True, retries=1):
                result = "again"
                break
        if result == "fail":
            self.log("内置日常：战斗失败")
            return False
        if not result:
            self.log("内置日常：等待战斗结果超时")
            return False
        if self.auto.find_image(str(ASSETS / "fight_exit.png"), 0.85, retries=4):
            found = self.auto.find_image(str(ASSETS / "fight_exit.png"), 0.85, retries=1)
            if found:
                x, y = found["center"]
                winapi.click(int(x), int(y))
        self.sleep(4.0)
        winapi.press_key("esc", 0.1)
        self.sleep(2.0)
        self.log("内置日常：消耗开拓力完成")
        return True

    def _training(self):
        self.log("内置日常：领取每日实训奖励")
        self._open_daily_guide()
        self.sleep(0.5)
        got = False
        for _ in range(8):
            if self.stopped():
                break
            if not self._click_text("领取", crop=(0.1, 0.7, 0.8, 0.16), include=False, retries=1, wait=1.0):
                break
            got = True
            self._close_popup()
            self.sleep(0.5)
        # 活跃度进度条上的礼物
        for ratio in (0.32, 0.447, 0.574, 0.70, 0.827):
            if self.stopped():
                break
            self._click_norm(ratio, 0.318)
            self._close_popup()
            self.sleep(0.3)
        return got
