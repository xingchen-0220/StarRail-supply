"""全局配置：路径、默认值、JSON 读写。"""
import copy
import json
import os
import sys
from pathlib import Path

APP_NAME = "星穹签到助手"
APP_VERSION = "1.3.1"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """可写数据目录的根（EXE 所在目录 / 源码根目录）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    """打包资源根目录（PyInstaller 解包目录）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_root()))
    return app_root()


ROOT = app_root()
RESOURCE = resource_root()
DATA_DIR = ROOT / "data"
CONFIG_PATH = DATA_DIR / "config.json"
LOG_DIR = DATA_DIR / "logs"
SHOT_DIR = DATA_DIR / "screenshots"

DEFAULTS = {
    "game_path": "",
    "game_title": "崩坏：星穹铁道",
    "game_process": "StarRail.exe",
    "window_class": "UnityWndClass",
    "launch_timeout": 180,
    "title_timeout": 120,
    "reward_timeout": 60,
    "ocr_confidence": 0.5,
    "click_delay": 0.6,
    "after_enter_wait": 4.0,
    "after_click_wait": 2.5,
    "exit_game": True,
    "exit_app": True,
    "minimize_on_run": True,
    "schedule_enabled": False,
    "schedule_time": "08:00",
    "schedule_days": [1, 2, 3, 4, 5, 6, 7],
    "last_run": "",
}


def ensure_dirs():
    for path in (DATA_DIR, LOG_DIR, SHOT_DIR):
        path.mkdir(parents=True, exist_ok=True)


class Config:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        ensure_dirs()
        if CONFIG_PATH.is_file():
            try:
                raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
                if isinstance(raw, dict):
                    for key, value in raw.items():
                        if key in self.data:
                            self.data[key] = value
            except Exception:
                pass

    def save(self):
        ensure_dirs()
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, CONFIG_PATH)

    def get(self, key, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self.data[key] = value

    def __getitem__(self, key):
        return self.get(key)


cfg = Config()



