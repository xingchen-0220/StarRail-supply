"""日志：控制台 + 文件 + GUI 回调。"""
import sys
import threading
import time

from .config import LOG_DIR, ensure_dirs


class AppLog:
    def __init__(self, callback=None):
        ensure_dirs()
        self.callback = callback
        self.lock = threading.Lock()
        self.path = LOG_DIR / f"app_{time.strftime('%Y%m%d')}.log"

    def __call__(self, message):
        text = str(message)
        line = f"[{time.strftime('%H:%M:%S')}] {text}"
        with self.lock:
            try:
                with open(self.path, "a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except Exception:
                pass
        if self.callback:
            try:
                self.callback(line)
            except Exception:
                pass
        try:
            print(line, flush=True)
        except Exception:
            pass
