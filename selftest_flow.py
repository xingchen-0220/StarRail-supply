"""固定签到流程端到端自测：假游戏窗口（仅测试用）。"""
import sys
import threading
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import winapi
from app.signin import SigninRunner

winapi.set_dpi_aware()
TITLE = "崩坏：星穹铁道"
state = {"enter": 0, "reward": 0, "ok": False}


class Cfg:
    data = {
        "game_title": TITLE,
        "window_class": "",
        "game_process": "",
        "game_path": r"C:\Windows\System32\notepad.exe",
        "launch_timeout": 10,
        "title_timeout": 20,
        "reward_timeout": 20,
        "ocr_confidence": 0.5,
        "click_delay": 0.25,
        "after_enter_wait": 1.0,
        "after_click_wait": 0.6,
        "exit_game": False,
        "exit_app": False,
        "minimize_on_run": False,
    }

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


def build_window():
    root = tk.Tk()
    root.title(TITLE)
    root.geometry("900x600+180+140")
    root.configure(bg="#1d1f26")

    enter = tk.Label(root, text="点击进入", font=("Microsoft YaHei", 30), fg="white", bg="#3b5bdb",
                     width=12, height=2)
    enter.place(x=80, y=70)

    def show_reward():
        enter.destroy()
        reward = tk.Label(root, text="点击领取今日补给", font=("Microsoft YaHei", 26), fg="white",
                          bg="#2f9e44", width=16, height=2)
        reward.place(x=280, y=320)
        reward.bind("<Button-1>", lambda event: on_reward())

    def on_enter(event):
        state["enter"] += 1
        root.after(600, show_reward)

    def on_reward():
        state["reward"] += 1
        tk.Label(root, text="领取成功", font=("Microsoft YaHei", 24), fg="#ffd43b",
                 bg="#1d1f26").place(x=360, y=480)

    enter.bind("<Button-1>", on_enter)
    return root


def worker(root):
    cfg = Cfg()
    log = lambda message: print(message, flush=True)
    runner = SigninRunner(cfg, log, on_step=lambda text: print("[状态]", text, flush=True))
    ok = runner.run()
    state["ok"] = bool(ok)
    print("RESULT", ok, dict(state), flush=True)
    root.after(500, root.destroy)


def main():
    root = build_window()
    root.after(800, lambda: threading.Thread(target=worker, args=(root,), daemon=True).start())
    root.mainloop()
    passed = state["ok"] and state["enter"] == 1 and state["reward"] == 1
    print("FLOW", "PASS" if passed else "FAIL", passed, dict(state))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
