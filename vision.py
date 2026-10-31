"""游戏画面识别与操作：截图、OCR、模板匹配、点击。"""
import os
import time

import cv2
import numpy as np

from . import winapi
from .geom import normalize_text
from .ocr_engine import OcrEngine


class Automation:
    def __init__(self, cfg, logger=None):
        self.cfg = cfg
        self.logger = logger or (lambda message: None)
        self.ocr = OcrEngine(float(cfg.get("ocr_confidence", 0.55)))
        self.window = 0
        self.mask_provider = None
        self._last_frame = None
        self._last_origin = None
        self._last_time = 0.0

    # ------------------------------------------------------------ base --
    def log(self, message):
        self.logger(str(message))

    def refresh_window(self):
        self.window = winapi.find_window(
            self.cfg.get("game_title", ""),
            self.cfg.get("window_class") or None,
            self.cfg.get("game_process", ""),
        )
        return self.window

    def ensure_window(self):
        if self.window and winapi.user32.IsWindow(self.window):
            return self.window
        if self.refresh_window():
            return self.window
        raise RuntimeError("未找到游戏窗口，请先启动游戏")

    def focus(self):
        hwnd = self.ensure_window()
        if self.cfg.get("bring_to_front", True):
            winapi.activate_window(hwnd)
        return hwnd

    def grab(self, crop=(0.0, 0.0, 1.0, 1.0)):
        """截取游戏客户区（可裁剪），返回 (RGB ndarray, (left, top), (width, height))。"""
        hwnd = self.ensure_window()
        winapi.restore_window(hwnd)
        image, region = winapi.capture_window(hwnd)
        if image is None or region is None:
            raise RuntimeError("截图失败：无法获取游戏画面")
        left, top, width, height = region
        # np.array 生成可写副本：浮窗遮罩需要写入；np.asarray 在部分 Pillow 版本下是只读的
        frame = np.array(image)
        if crop and tuple(crop) != (0.0, 0.0, 1.0, 1.0):
            cx = int(width * crop[0])
            cy = int(height * crop[1])
            cw = max(1, int(width * crop[2]))
            ch = max(1, int(height * crop[3]))
            cx = max(0, min(cx, width - 1))
            cy = max(0, min(cy, height - 1))
            cw = min(cw, width - cx)
            ch = min(ch, height - cy)
            frame = frame[cy : cy + ch, cx : cx + cw]
            left += cx
            top += cy
            width, height = cw, ch
        # 涂黑状态浮窗区域，避免浮窗文字被 OCR/模板匹配当成游戏内容
        if self.mask_provider:
            try:
                rect = self.mask_provider()
            except Exception:
                rect = None
            if rect:
                mx, my, mw, mh = rect
                x1 = max(left, mx)
                y1 = max(top, my)
                x2 = min(left + width, mx + mw)
                y2 = min(top + height, my + mh)
                if x2 > x1 and y2 > y1:
                    frame[y1 - top : y2 - top, x1 - left : x2 - left] = 0
        self._last_frame = frame
        self._last_origin = (left, top)
        self._last_time = time.monotonic()
        return frame, (left, top), (width, height)

    def screenshot_to_file(self, path):
        image, _ = winapi.capture_window(self.ensure_window())
        if image is None:
            raise RuntimeError("截图失败")
        image.save(path)
        return path

    # ------------------------------------------------------------ find --
    def find_any_text(self, targets, include=False, crop=(0.0, 0.0, 1.0, 1.0)):
        """一次截图/OCR，匹配多个候选文字，返回第一个命中的结果。"""
        if isinstance(targets, str):
            targets = [targets]
        normalized_targets = [normalize_text(item) for item in targets if normalize_text(item)]
        if not normalized_targets:
            return None
        frame, origin, _ = self.grab(crop)
        lines = self.ocr.recognize(frame)
        for target in normalized_targets:
            for x1, y1, x2, y2, text, score in lines:
                normalized = normalize_text(text)
                matched = target in normalized if include else normalized == target
                if not matched:
                    continue
                center = (origin[0] + (x1 + x2) / 2.0, origin[1] + (y1 + y2) / 2.0)
                return {
                    "center": center,
                    "box": (origin[0] + x1, origin[1] + y1, origin[0] + x2, origin[1] + y2),
                    "text": text,
                    "score": score,
                    "target": target,
                }
        return None

    def find_text(self, targets, include=False, crop=(0.0, 0.0, 1.0, 1.0), retries=1):
        if isinstance(targets, str):
            targets = [targets]
        last_error = None
        for attempt in range(max(1, int(retries))):
            try:
                found = self.find_any_text(targets, include=include, crop=crop)
                if found:
                    return found
            except Exception as exc:
                last_error = exc
            if attempt < int(retries) - 1:
                time.sleep(float(self.cfg.get("retry_delay", 0.8)))
        if last_error:
            self.log(f"文字识别出错：{last_error}")
        return None

    def ocr_lines(self, crop=(0.0, 0.0, 1.0, 1.0)):
        frame, origin, _ = self.grab(crop)
        lines = []
        for x1, y1, x2, y2, text, score in self.ocr.recognize(frame):
            lines.append((int(origin[0] + x1), int(origin[1] + y1), text, float(score)))
        return lines

    @staticmethod
    def _read_image(path):
        if not path or not os.path.isfile(path):
            return None
        try:
            data = np.fromfile(path, dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            return None

    def find_image(self, template_path, threshold=0.9, crop=(0.0, 0.0, 1.0, 1.0), retries=1):
        template = self._read_image(template_path)
        if template is None:
            self.log(f"读取模板失败：{template_path}")
            return None
        last_error = None
        for attempt in range(max(1, int(retries))):
            try:
                frame, origin, _ = self.grab(crop)
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                if (
                    gray_template.shape[0] > gray_frame.shape[0]
                    or gray_template.shape[1] > gray_frame.shape[1]
                ):
                    self.log("模板尺寸大于截图区域，请缩小检测区域或重新采集模板")
                    return None
                result = cv2.matchTemplate(gray_frame, gray_template, cv2.TM_CCOEFF_NORMED)
                _, max_value, _, max_location = cv2.minMaxLoc(result)
                self.log(f"图片匹配度 {max_value:.3f}（阈值 {float(threshold):.2f}）")
                if max_value >= float(threshold):
                    x, y = max_location
                    height, width = gray_template.shape[:2]
                    return {
                        "center": (origin[0] + x + width / 2.0, origin[1] + y + height / 2.0),
                        "box": (origin[0] + x, origin[1] + y, origin[0] + x + width, origin[1] + y + height),
                        "score": float(max_value),
                    }
            except Exception as exc:
                last_error = exc
            if attempt < int(retries) - 1:
                time.sleep(float(self.cfg.get("retry_delay", 0.8)))
        if last_error:
            self.log(f"图片识别出错：{last_error}")
        return None

    # ----------------------------------------------------------- click --
    def click_point(self, x, y, action="click", press_duration=0.0):
        self.focus()
        x, y = int(x), int(y)
        duration = max(0.0, float(press_duration or 0.0))
        if action == "down":
            winapi.mouse_down(x, y)
            if duration:
                time.sleep(duration)
        elif action == "up":
            winapi.move_mouse(x, y)
            winapi.mouse_up()
        elif action == "move":
            winapi.move_mouse(x, y)
        elif duration > 0:
            winapi.mouse_down(x, y)
            time.sleep(duration)
            winapi.mouse_up()
        else:
            winapi.click(x, y)
        return True

    def click_element(self, find_type, target, threshold=0.9, crop=(0.0, 0.0, 1.0, 1.0),
                      retries=1, include=False, action="click", press_duration=0.0):
        if find_type == "text":
            found = self.find_text(target, include=include, crop=crop, retries=retries)
        elif find_type == "image":
            found = self.find_image(target, threshold, crop, retries)
        else:
            raise ValueError(f"未知查找类型：{find_type}")
        if not found:
            return False
        x, y = found["center"]
        if action == "click" and float(press_duration or 0) > 0:
            self.focus()
            winapi.mouse_down(int(x), int(y))
            time.sleep(float(press_duration))
            winapi.mouse_up()
        else:
            self.click_point(x, y, action, press_duration)
        time.sleep(float(self.cfg.get("click_delay", 0.35)))
        return True

    def drag_mouse(self, start, end, duration=0.5):
        frame, origin, (width, height) = self.grab()
        sx = origin[0] + min(int(start[0] * width), width - 1)
        sy = origin[1] + min(int(start[1] * height), height - 1)
        ex = origin[0] + min(int(end[0] * width), width - 1)
        ey = origin[1] + min(int(end[1] * height), height - 1)
        self.focus()
        winapi.drag(sx, sy, ex, ey, duration)
        return True
