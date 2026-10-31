"""RapidOCR 封装：懒加载、线程安全、中文多行识别。"""
import threading

import cv2
import numpy as np


class OcrEngine:
    def __init__(self, min_confidence: float = 0.55):
        self.min_confidence = min_confidence
        self._engine = None
        self._lock = threading.RLock()

    def _ensure(self):
        if self._engine is not None:
            return self._engine
        with self._lock:
            if self._engine is None:
                from rapidocr_onnxruntime import RapidOCR

                self._engine = RapidOCR()
            return self._engine

    def preload(self):
        try:
            self._ensure()
            return True
        except Exception:
            return False

    def recognize(self, image_rgb: np.ndarray):
        """返回 [(x1, y1, x2, y2, text, score), ...]（输入为 RGB）。"""
        if image_rgb is None or image_rgb.size == 0:
            return []
        engine = self._ensure()
        bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        with self._lock:
            result, _ = engine(bgr)
        lines = []
        for item in result or []:
            try:
                box, text, score = item
                score = float(score)
                if score < self.min_confidence or not str(text).strip():
                    continue
                xs = [float(point[0]) for point in box]
                ys = [float(point[1]) for point in box]
                lines.append(
                    (min(xs), min(ys), max(xs), max(ys), str(text).strip(), score)
                )
            except Exception:
                continue
        return lines
