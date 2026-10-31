"""游戏左下角状态浮窗：显示当前签到步骤。"""
import ctypes
import tkinter as tk

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

BG = "#0f131b"
CARD = "#171c27"
TEXT = "#eef2ff"
MUTED = "#8b95ad"
ACCENT = "#4c6ef5"
OK = "#37b24d"
FAIL = "#f03e3e"


class StatusOverlay:
    """无边框、置顶、鼠标穿透的状态浮窗。"""

    WIDTH = 380
    HEIGHT = 94

    def __init__(self, master):
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.97)
        self.win.configure(bg=BG)

        screen_height = self.win.winfo_screenheight()
        x = 22
        y = max(40, screen_height - self.HEIGHT - 64)
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        self.accent = tk.Frame(self.win, bg=ACCENT, width=4)
        self.accent.pack(side="left", fill="y")

        body = tk.Frame(self.win, bg=CARD)
        body.pack(side="left", fill="both", expand=True)

        top = tk.Frame(body, bg=CARD)
        top.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(top, text="★ 星穹签到助手", bg=CARD, fg=MUTED,
                 font=("Microsoft YaHei UI", 8)).pack(side="left")
        self.step_index = tk.Label(top, text="", bg=CARD, fg=ACCENT,
                                   font=("Microsoft YaHei UI", 8, "bold"))
        self.step_index.pack(side="right")

        self.step_label = tk.Label(body, text="准备中…", bg=CARD, fg=TEXT, anchor="w",
                                   font=("Microsoft YaHei UI", 11, "bold"), wraplength=330,
                                   justify="left")
        self.step_label.pack(fill="x", padx=14, pady=(4, 6))

        self.bar = tk.Canvas(body, width=self.WIDTH - 32, height=4, bg="#262c3a",
                             highlightthickness=0)
        self.bar.pack(fill="x", padx=14, pady=(0, 10))
        self.bar_fill = self.bar.create_rectangle(0, 0, 0, 4, fill=ACCENT, width=0)

        self.win.withdraw()
        self.win.update_idletasks()
        self._rect = None
        self._remember_rect()
        self._make_click_through()

    def _remember_rect(self):
        """缓存屏幕坐标，供工作线程安全读取（避免跨线程调用 Tk）。"""
        try:
            self.win.update_idletasks()
            self._rect = (
                self.win.winfo_rootx(),
                self.win.winfo_rooty(),
                self.win.winfo_width(),
                self.win.winfo_height(),
            )
        except Exception:
            self._rect = None

    def _make_click_through(self):
        try:
            user32 = ctypes.windll.user32
            style_extra = WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            handles = []
            try:
                handles.append(int(self.win.wm_frame(), 16))
            except Exception:
                pass
            try:
                handles.append(self.win.winfo_id())
            except Exception:
                pass

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def enum_child(hwnd, _):
                handles.append(hwnd)
                return True

            for hwnd in list(handles):
                try:
                    user32.EnumChildWindows(hwnd, enum_child, 0)
                except Exception:
                    pass

            for hwnd in set(handles):
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | style_extra)
        except Exception:
            pass

    def show(self, text="准备启动游戏…"):
        self.accent.configure(bg=ACCENT)
        self.step_index.configure(text="", fg=ACCENT)
        self.step_label.configure(text=text, fg=TEXT)
        self.bar.coords(self.bar_fill, 0, 0, 0, 4)
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)
        self._remember_rect()

    def update_step(self, index, total, text):
        self.win.deiconify()
        self.win.attributes("-topmost", True)
        self.win.lift()
        self.accent.configure(bg=ACCENT)
        self.step_index.configure(text=f"{index}/{total}", fg=ACCENT)
        self.step_label.configure(text=text, fg=TEXT)
        width = max(0, self.WIDTH - 32)
        self.bar.coords(self.bar_fill, 0, 0, int(width * index / max(1, total)), 4)
        self._remember_rect()

    def finish(self, text="签到完成", ok=True, hide_after=0):
        if ok is True:
            color, symbol = OK, "✓"
        elif ok is False:
            color, symbol = FAIL, "✕"
        else:
            color, symbol = ACCENT, "•"
        self.win.deiconify()
        self.accent.configure(bg=color)
        self.step_index.configure(text=symbol, fg=color)
        self.step_label.configure(text=text, fg=TEXT)
        width = self.WIDTH - 32
        if ok is True:
            self.bar.coords(self.bar_fill, 0, 0, width, 4)
        self.bar.itemconfigure(self.bar_fill, fill=color)
        self._remember_rect()
        if hide_after:
            self.win.after(hide_after, self.hide)

    def hide(self):
        try:
            self.win.withdraw()
        except Exception:
            pass
        self._rect = None

    def rect(self):
        """返回缓存的浮窗屏幕坐标；隐藏时返回 None。线程安全。"""
        return self._rect

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass
