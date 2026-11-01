"""图形界面：左侧导航 + 首页 / 定时 / 演示 / 日志 / 设置 / 关于。"""
import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import launcher, winapi
from .config import APP_NAME, APP_VERSION, DATA_DIR, RESOURCE, cfg, ensure_dirs, is_frozen
from .logger import AppLog
from .notifier import OneBotNotifier
from .overlay import StatusOverlay
from .signin import SigninRunner

TASK_NAME = "星穹签到助手-每日签到"
GITHUB_URL = "https://github.com/xingchen-0220/StarRail-supply"
BG = "#f6f7fb"
SIDEBAR = "#0f172a"
SIDEBAR_ACTIVE = "#1e3a8a"
ACCENT = "#2f6fed"
TEXT = "#111827"
MUTED = "#6b7280"
BORDER = "#e5e9f2"
FONT = ("Microsoft YaHei UI", 10)


class App:
    PAGES = {
        "home": ("首页", "启动游戏 · 识别点击 · 领取每日奖励"),
        "daily": ("日常任务", "内置日常：邮件 / 委托 / 清体力 / 支援 / 每日实训 500"),
        "notify": ("QQ 通知", "OneBot v11 私聊通知，发送签到/日常结果与截图"),
        "schedule": ("定时签到", "每天固定时间自动领取，可选程序内定时或 Windows 计划任务"),
        "log": ("运行日志", "实时查看签到过程与错误信息"),
        "settings": ("设置", "游戏路径、窗口与识别参数"),
        "about": ("关于", "作者与支持方式"),
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1180x780")
        self.root.minsize(1080, 720)
        self.root.configure(bg=BG)

        self.messages = queue.Queue()
        self.logger = AppLog(callback=lambda line: self.messages.put(("log", line)))
        self.busy = False
        self.worker = None
        self.stop_event = None
        self.last_ok = False
        self.last_skipped = False
        self.last_signin_ok = False
        self.last_daily_ok = None
        self.plan_task_exists = False
        self.update_checking = False
        self.pages = {}
        self.nav_buttons = {}
        self.current_page = "home"
        self._images = []

        self.path_var = tk.StringVar(value=cfg.get("game_path", ""))
        self.status_var = tk.StringVar(value="准备就绪")

        self._style()
        self._shell()
        self._build_pages()
        self.overlay = StatusOverlay(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if not cfg.get("game_path") or not os.path.isfile(cfg.get("game_path", "")):
            detected = launcher.detect_game_path(cfg)
            if detected:
                cfg.set("game_path", detected)
                cfg.save()
                self.path_var.set(detected)
        self.refresh_status()
        self._sync_plan_task()
        self._show_page("home")

        self.root.after(100, self._poll)
        self.root.after(600, self._tick_schedule)
        self.root.after(1500, self.refresh_status)
        if cfg.get("check_update_on_start", True):
            self.root.after(2500, lambda: self.check_updates(False))

    # ------------------------------------------------------------- 外观 --
    def _style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=FONT, background=BG)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TButton", padding=(10, 6), borderwidth=0, background="#e9edf5")
        style.map("TButton", background=[("active", "#dfe5f1")])
        style.configure("Accent.TButton", background=ACCENT, foreground="white",
                        font=("Microsoft YaHei UI", 10, "bold"), padding=(12, 8))
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("disabled", "#9db4f0")])
        style.configure("TCheckbutton", background="white", font=("Microsoft YaHei UI", 9))
        style.configure("TCombobox", padding=4)

    def _load_image(self, filename, size):
        path = RESOURCE / "assets" / filename
        image = Image.open(path).convert("RGBA")
        image = image.resize((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        self._images.append(photo)
        return photo

    def _shell(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        sidebar = tk.Frame(self.root, bg=SIDEBAR, width=206)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        logo_row = tk.Frame(sidebar, bg=SIDEBAR)
        logo_row.pack(fill="x", padx=16, pady=(20, 18))
        try:
            self.logo_photo = self._load_image("app_icon.png", 38)
            tk.Label(logo_row, image=self.logo_photo, bg=SIDEBAR).pack(side="left")
        except Exception:
            pass
        logo_text = tk.Frame(logo_row, bg=SIDEBAR)
        logo_text.pack(side="left", padx=8)
        tk.Label(logo_text, text="星穹签到助手", bg=SIDEBAR, fg="white",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        tk.Label(logo_text, text=f"v{APP_VERSION}", bg=SIDEBAR, fg="#64748b",
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w")

        tk.Frame(sidebar, bg="#1e293b", height=1).pack(fill="x", padx=16, pady=(0, 10))

        items = [
            ("home", "首页"),
            ("daily", "日常任务"),
            ("notify", "QQ 通知"),
            ("schedule", "定时签到"),
            ("log", "运行日志"),
            ("settings", "设置"),
            ("about", "关于"),
        ]
        for key, label in items:
            button = tk.Button(
                sidebar, text=f"  {label}", anchor="w", relief="flat", bd=0,
                bg=SIDEBAR, fg="#cbd5e1", activebackground="#1e293b", activeforeground="white",
                font=("Microsoft YaHei UI", 10), padx=16, pady=9, cursor="hand2",
                command=lambda name=key: self._show_page(name),
            )
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = button

        bottom = tk.Frame(sidebar, bg=SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=16, pady=16)
        admin_text = "管理员权限" if is_admin() else "非管理员（可能无法操作游戏）"
        self.admin_label = tk.Label(bottom, text=admin_text, bg=SIDEBAR,
                                    fg="#4ade80" if is_admin() else "#fb923c",
                                    font=("Microsoft YaHei UI", 8), anchor="w")
        self.admin_label.pack(fill="x")
        tk.Label(bottom, text="图像识别基于 RapidOCR", bg=SIDEBAR, fg="#475569",
                 font=("Microsoft YaHei UI", 7), anchor="w").pack(fill="x", pady=(4, 0))

        content = tk.Frame(self.root, bg=BG)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        topbar = tk.Frame(content, bg="white", height=78)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)
        topbar.grid_columnconfigure(0, weight=1)
        title_box = tk.Frame(topbar, bg="white")
        title_box.grid(row=0, column=0, sticky="w", padx=26, pady=14)
        self.page_title = tk.Label(title_box, text="首页", bg="white", fg=TEXT,
                                   font=("Microsoft YaHei UI", 17, "bold"))
        self.page_title.pack(anchor="w")
        self.page_subtitle = tk.Label(title_box, text="", bg="white", fg=MUTED,
                                      font=("Microsoft YaHei UI", 9))
        self.page_subtitle.pack(anchor="w", pady=(2, 0))

        self.header_status = tk.Label(topbar, text="游戏未运行", bg="#f1f5f9", fg="#64748b",
                                      font=("Microsoft YaHei UI", 9, "bold"), padx=14, pady=6)
        self.header_status.grid(row=0, column=1, sticky="e", padx=26)
        tk.Frame(topbar, bg=BORDER, height=1).place(relx=0, rely=1, relwidth=1, anchor="sw")

        self.page_container = tk.Frame(content, bg=BG)
        self.page_container.grid(row=1, column=0, sticky="nsew")
        self.page_container.grid_rowconfigure(0, weight=1)
        self.page_container.grid_columnconfigure(0, weight=1)

    def _show_page(self, name):
        if name not in self.pages:
            return
        for key, page in self.pages.items():
            if key == name:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()
        self.current_page = name
        title, subtitle = self.PAGES[name]
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)
        for key, button in self.nav_buttons.items():
            if key == name:
                button.configure(bg=SIDEBAR_ACTIVE, fg="white")
            else:
                button.configure(bg=SIDEBAR, fg="#cbd5e1")

    # ------------------------------------------------------------- 页面 --
    def _new_page(self, key):
        page = tk.Frame(self.page_container, bg=BG)
        page.grid(row=0, column=0, sticky="nsew")
        self.pages[key] = page
        return page

    def _card(self, parent, padx=18, pady=14):
        outer = tk.Frame(parent, bg="white", highlightbackground=BORDER, highlightthickness=1)
        inner = tk.Frame(outer, bg="white")
        inner.pack(fill="both", expand=True, padx=padx, pady=pady)
        return outer, inner

    def _section_title(self, parent, text, sub=""):
        tk.Label(parent, text=text, bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        if sub:
            tk.Label(parent, text=sub, bg="white", fg=MUTED,
                     font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(2, 0))

    def _accent_button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, bg=ACCENT, fg="white",
                         activebackground="#1d4ed8", activeforeground="white", relief="flat",
                         bd=0, padx=18, pady=9, cursor="hand2",
                         font=("Microsoft YaHei UI", 10, "bold"))

    def _light_button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, bg="#eef2ff", fg="#1e40af",
                         activebackground="#dbe4ff", activeforeground="#1e3a8a", relief="flat",
                         bd=0, padx=14, pady=7, cursor="hand2",
                         font=("Microsoft YaHei UI", 9))

    def _build_pages(self):
        self._build_home(self._new_page("home"))
        self._build_daily(self._new_page("daily"))
        self._build_notify(self._new_page("notify"))
        self._build_schedule(self._new_page("schedule"))
        self._build_log(self._new_page("log"))
        self._build_settings(self._new_page("settings"))
        self._build_about(self._new_page("about"))

    def _build_home(self, page):
        wrap = tk.Frame(page, bg=BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=20)

        stats = tk.Frame(wrap, bg=BG)
        stats.pack(fill="x")
        stats.grid_columnconfigure(0, weight=1)
        stats.grid_columnconfigure(1, weight=1)

        game_card, game = self._card(stats)
        game_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(game, text="游戏状态", bg="white", fg=MUTED,
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        self.game_state_label = tk.Label(game, text="○ 未运行", bg="white", fg="#94a3b8",
                                         font=("Microsoft YaHei UI", 20, "bold"))
        self.game_state_label.pack(anchor="w", pady=(2, 4))
        tk.Label(game, textvariable=self.path_var, bg="white", fg=MUTED,
                 font=("Microsoft YaHei UI", 8), wraplength=380, justify="left").pack(anchor="w")
        game_actions = tk.Frame(game, bg="white")
        game_actions.pack(anchor="w", pady=(10, 0))
        self._light_button(game_actions, "浏览路径", self.browse).pack(side="left")
        self._light_button(game_actions, "自动检测", self.detect).pack(side="left", padx=8)
        self._light_button(game_actions, "测试识别", self.test_ocr).pack(side="left")

        time_card, time_inner = self._card(stats)
        time_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(time_inner, text="定时签到", bg="white", fg=MUTED,
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        self.home_schedule_label = tk.Label(time_inner, text="未启用", bg="white", fg=TEXT,
                                            font=("Microsoft YaHei UI", 18, "bold"))
        self.home_schedule_label.pack(anchor="w", pady=(2, 2))
        self.home_next_label = tk.Label(time_inner, text="", bg="white", fg=MUTED,
                                        font=("Microsoft YaHei UI", 9))
        self.home_next_label.pack(anchor="w")
        self._light_button(time_inner, "去设置定时", lambda: self._show_page("schedule")).pack(
            anchor="w", pady=(10, 0)
        )

        action_card, action = self._card(wrap, padx=22, pady=18)
        action_card.pack(fill="x", pady=16)
        self._section_title(action, "一键签到", "启动游戏，识别「点击进入」和「点击领取今日奖励」")
        self.start_button = tk.Button(
            action, text="立即签到", command=self.start_signin, bg=ACCENT, fg="white",
            activebackground="#1d4ed8", activeforeground="white", relief="flat", bd=0,
            padx=24, pady=12, cursor="hand2", font=("Microsoft YaHei UI", 12, "bold"),
        )
        self.start_button.pack(fill="x", pady=(14, 8))

        row = tk.Frame(action, bg="white")
        row.pack(fill="x")
        self.stop_button = tk.Button(
            row, text="停止", command=self.stop_task, bg="#fee2e2", fg="#b91c1c",
            activebackground="#fecaca", activeforeground="#7f1d1d", relief="flat", bd=0,
            padx=16, pady=6, cursor="hand2", font=("Microsoft YaHei UI", 9, "bold"),
            state="disabled",
        )
        self.stop_button.pack(side="left")
        tk.Label(row, textvariable=self.status_var, bg="white", fg=MUTED,
                 font=("Microsoft YaHei UI", 9)).pack(side="left", padx=12)

        options = tk.Frame(action, bg="white")
        options.pack(fill="x", pady=(12, 0))
        self.exit_game_var = tk.BooleanVar(value=bool(cfg.get("exit_game", True)))
        self.exit_app_var = tk.BooleanVar(value=bool(cfg.get("exit_app", True)))
        self.minimize_var = tk.BooleanVar(value=bool(cfg.get("minimize_on_run", True)))
        for text, var in (
            ("签到后关闭游戏", self.exit_game_var),
            ("完成后退出本程序", self.exit_app_var),
            ("运行时最小化窗口", self.minimize_var),
        ):
            tk.Checkbutton(options, text=text, variable=var, command=self.save_options,
                           bg="white", activebackground="white", selectcolor="white",
                           fg=TEXT, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(0, 18))

        log_card, log_inner = self._card(wrap, padx=16, pady=12)
        log_card.pack(fill="both", expand=True)
        log_top = tk.Frame(log_inner, bg="white")
        log_top.pack(fill="x")
        tk.Label(log_top, text="最近日志", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        self._light_button(log_top, "查看完整日志",
                           lambda: self._show_page("log")).pack(side="right")
        self.home_log_text = tk.Text(log_inner, height=7, bg="#0f131b", fg="#d7dce8",
                                     relief="flat", font=("Consolas", 9), padx=10, pady=8,
                                     insertbackground="white")
        self.home_log_text.pack(fill="both", expand=True, pady=(8, 0))
        self.home_log_text.configure(state="disabled")

    def _build_daily(self, page):
        wrap = tk.Frame(page, bg=BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=20)
        card, inner = self._card(wrap, padx=22, pady=18)
        card.pack(fill="x")
        self._section_title(inner, "日常任务", "邮件 / 委托 / 清体力 / 支援 / 无名勋礼 / 每日实训 500")

        self.daily_enabled_var = tk.BooleanVar(value=bool(cfg.get("daily_enabled", False)))
        tk.Checkbutton(inner, text="签到成功后执行日常任务", variable=self.daily_enabled_var,
                       command=self.save_daily_settings, bg="white", activebackground="white",
                       selectcolor="white", fg=TEXT,
                       font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(14, 8))

        self.clear_power_var = tk.BooleanVar(value=bool(cfg.get("daily_clear_power", False)))
        tk.Checkbutton(inner, text="清空剩余开拓力（按当前体力设置花萼挑战次数，最多 24 次）",
                       variable=self.clear_power_var, command=self.save_daily_settings,
                       bg="white", activebackground="white", selectcolor="white", fg=TEXT,
                       font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(2, 8))

        self._accent_button(inner, "保存日常设置", self.save_daily_settings).pack(
            anchor="e", pady=(12, 0))

        note, note_inner = self._card(wrap, padx=20, pady=14)
        note.pack(fill="x", pady=(14, 0))
        tk.Label(note_inner, text="说明", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        for text in (
            "· 内置日常：邮件、委托、清空剩余开拓力花萼、支援战斗、支援奖励、无名勋礼、每日实训 500。",
            "· 不需要安装任何外部程序；模拟宇宙、差分宇宙、货币战争、历战余响不在内置范围内。",
            "· 日常结束后，本程序会按「签到后关闭游戏」选项决定是否关闭游戏。",
        ):
            tk.Label(note_inner, text=text, bg="white", fg=MUTED,
                     font=("Microsoft YaHei UI", 9), anchor="w", justify="left").pack(
                fill="x", pady=2)

    def _build_notify(self, page):
        wrap = tk.Frame(page, bg=BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=20)
        card, inner = self._card(wrap, padx=22, pady=18)
        card.pack(fill="x")
        self._section_title(inner, "QQ 通知", "OneBot v11 私聊通知：先发文字，再发截图")

        self.notify_enabled_var = tk.BooleanVar(value=bool(cfg.get("notify_enabled", False)))
        tk.Checkbutton(inner, text="启用 QQ 通知", variable=self.notify_enabled_var,
                       command=self.save_notify_settings, bg="white", activebackground="white",
                       selectcolor="white", fg=TEXT,
                       font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(14, 8))

        fields = tk.Frame(inner, bg="white")
        fields.pack(fill="x")
        self.onebot_url_var = tk.StringVar(value=cfg.get("onebot_url", "http://127.0.0.1:3000"))
        self.onebot_token_var = tk.StringVar(value=cfg.get("onebot_token", ""))
        self.qq_target_var = tk.StringVar(value=cfg.get("qq_target", ""))
        self.send_shots_var = tk.BooleanVar(value=bool(cfg.get("send_screenshots", True)))
        self._field(fields, "OneBot API", self.onebot_url_var, 0)
        self._field(fields, "Access Token", self.onebot_token_var, 1, show="*")
        self._field(fields, "目标 QQ 号", self.qq_target_var, 2)
        tk.Checkbutton(fields, text="发送截图（签到成功/未弹窗/失败、日常结束）",
                       variable=self.send_shots_var, bg="white", activebackground="white",
                       selectcolor="white", fg=TEXT,
                       font=("Microsoft YaHei UI", 9)).grid(
            row=3, column=1, sticky="w", pady=6, padx=8)

        buttons = tk.Frame(inner, bg="white")
        buttons.pack(fill="x", pady=(10, 0))
        self._accent_button(buttons, "保存通知设置", self.save_notify_settings).pack(side="right")
        self._light_button(buttons, "发送测试消息", self.test_notify).pack(side="right", padx=8)

        note, note_inner = self._card(wrap, padx=20, pady=14)
        note.pack(fill="x", pady=(14, 0))
        tk.Label(note_inner, text="说明", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        for text in (
            "· 支持 NapCat / go-cqhttp / LLOneBot 等 OneBot v11 HTTP 接口。",
            "· 默认地址 http://127.0.0.1:3000；如果机器人设置了 token，请一并填写。",
            "· 目标 QQ 号填你自己的 QQ，机器人会以私聊方式发送文字和图片。",
        ):
            tk.Label(note_inner, text=text, bg="white", fg=MUTED,
                     font=("Microsoft YaHei UI", 9), anchor="w", justify="left").pack(
                fill="x", pady=2)

    def _field(self, parent, label, var, row, show=None):
        tk.Label(parent, text=label, bg="white", fg=MUTED, font=("Microsoft YaHei UI", 9),
                 width=14, anchor="e").grid(row=row, column=0, sticky="e", pady=5, padx=(0, 8))
        entry = tk.Entry(parent, textvariable=var, bg="#f8fafc", relief="flat",
                         highlightthickness=1, highlightbackground=BORDER, font=FONT,
                         show=show or "")
        entry.grid(row=row, column=1, sticky="we", pady=5, padx=(0, 8), ipady=4)
        parent.grid_columnconfigure(1, weight=1)

    def _build_schedule(self, page):
        wrap = tk.Frame(page, bg=BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=20)

        card, inner = self._card(wrap, padx=24, pady=20)
        card.pack(fill="x")
        self._section_title(inner, "定时签到", "到点自动启动游戏、领取奖励并关闭游戏")

        row = tk.Frame(inner, bg="white")
        row.pack(fill="x", pady=(16, 6))
        self.schedule_var = tk.BooleanVar(value=bool(cfg.get("schedule_enabled", False)))
        tk.Checkbutton(row, text="启用程序内定时", variable=self.schedule_var,
                       command=self.save_schedule, bg="white", activebackground="white",
                       selectcolor="white", fg=TEXT,
                       font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.schedule_summary = tk.Label(row, text="", bg="white", fg=TEXT,
                                         font=("Microsoft YaHei UI", 16, "bold"))
        self.schedule_summary.pack(side="left", padx=16)
        self.next_label = tk.Label(row, text="", bg="white", fg=MUTED,
                                   font=("Microsoft YaHei UI", 9))
        self.next_label.pack(side="left", padx=4)

        buttons = tk.Frame(inner, bg="white")
        buttons.pack(fill="x", pady=(12, 4))
        self._accent_button(buttons, "设置定时…", self.open_schedule).pack(side="left")
        self._light_button(buttons, "创建计划任务", self.create_task).pack(side="left", padx=10)
        self._light_button(buttons, "删除计划任务", self.delete_task).pack(side="left")

    def _build_log(self, page):
        wrap = tk.Frame(page, bg=BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=20)
        card, inner = self._card(wrap, padx=16, pady=14)
        card.pack(fill="both", expand=True)
        top = tk.Frame(inner, bg="white")
        top.pack(fill="x")
        tk.Label(top, text="实时日志", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        self._light_button(top, "清空", self.clear_log).pack(side="right")
        self._light_button(top, "打开日志文件", self.open_log).pack(side="right", padx=8)
        self.log_text = tk.Text(inner, bg="#0f131b", fg="#d7dce8", relief="flat",
                                font=("Consolas", 9), padx=12, pady=10, insertbackground="white")
        self.log_text.pack(fill="both", expand=True, pady=(10, 0))
        self.log_text.configure(state="disabled")

    def _build_settings(self, page):
        wrap = tk.Frame(page, bg=BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=20)
        card, inner = self._card(wrap, padx=22, pady=18)
        card.pack(fill="x")
        self._section_title(inner, "游戏路径", "选择 StarRail.exe；也可以点自动检测")

        row = tk.Frame(inner, bg="white")
        row.pack(fill="x", pady=(10, 4))
        tk.Entry(row, textvariable=self.path_var, bg="#f8fafc", relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                 font=FONT).pack(side="left", fill="x", expand=True, ipady=6)
        self._light_button(row, "浏览", self.browse).pack(side="left", padx=(8, 0))
        self._light_button(row, "自动检测", self.detect).pack(side="left", padx=8)
        self._light_button(row, "测试识别", self.test_ocr).pack(side="left")

        advanced, inner2 = self._card(wrap, padx=22, pady=18)
        advanced.pack(fill="x", pady=14)
        self._section_title(inner2, "高级设置", "一般保持默认即可")
        self.setting_vars = {}
        fields = [
            ("窗口标题", "game_title"),
            ("进程名", "game_process"),
            ("窗口类名", "window_class"),
            ("启动超时（秒）", "launch_timeout"),
            ("标题等待（秒）", "title_timeout"),
            ("奖励等待（秒）", "reward_timeout"),
            ("点击后延时", "click_delay"),
            ("OCR 置信度", "ocr_confidence"),
        ]
        grid = tk.Frame(inner2, bg="white")
        grid.pack(fill="x", pady=(10, 0))
        for index, (label, key) in enumerate(fields):
            row = index // 2
            col = (index % 2) * 2
            tk.Label(grid, text=label, bg="white", fg=MUTED, font=("Microsoft YaHei UI", 9),
                     anchor="e", width=14).grid(row=row, column=col, sticky="e", pady=5, padx=(0, 8))
            var = tk.StringVar(value=str(cfg.get(key, "")))
            self.setting_vars[key] = var
            tk.Entry(grid, textvariable=var, bg="#f8fafc", relief="flat", highlightthickness=1,
                     highlightbackground=BORDER, font=FONT, width=24).grid(
                row=row, column=col + 1, sticky="w", pady=5, ipady=4, padx=(0, 24)
            )

        row = tk.Frame(inner2, bg="white")
        row.pack(fill="x", pady=(10, 0))
        self.bring_front_var = tk.BooleanVar(value=bool(cfg.get("bring_to_front", True)))
        tk.Checkbutton(row, text="操作前自动切换到游戏窗口", variable=self.bring_front_var,
                       bg="white", activebackground="white", selectcolor="white",
                       fg=TEXT, font=("Microsoft YaHei UI", 9)).pack(side="left")
        self.update_check_var = tk.BooleanVar(value=bool(cfg.get("check_update_on_start", True)))
        tk.Checkbutton(row, text="启动时检查 GitHub 更新", variable=self.update_check_var,
                       bg="white", activebackground="white", selectcolor="white",
                       fg=TEXT, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=16)
        self._accent_button(row, "保存设置", self.save_settings).pack(side="right")

        data_card, data_inner = self._card(wrap, padx=22, pady=16)
        data_card.pack(fill="x")
        tk.Label(data_inner, text="数据目录", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        tk.Label(data_inner, text=str(DATA_DIR), bg="white", fg=MUTED,
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(4, 8))
        self._light_button(data_inner, "打开数据目录",
                           lambda: os.startfile(str(DATA_DIR))).pack(anchor="w")

    def _build_about(self, page):
        wrap = tk.Frame(page, bg=BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=20)
        wrap.grid_columnconfigure(0, weight=1)

        left_card, left = self._card(wrap, padx=24, pady=22)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        try:
            self.about_icon = self._load_image("app_icon.png", 96)
            tk.Label(left, image=self.about_icon, bg="white").pack(anchor="w", pady=(0, 16))
        except Exception:
            pass

        tk.Label(left, text="觉得好用就支持一下呗！", bg="white", fg="#000000",
                 font=("Microsoft YaHei UI", 22, "bold")).pack(anchor="w")
        tk.Label(left, text="作者：梦和星辰", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 11)).pack(anchor="w", pady=(12, 2))
        row = tk.Frame(left, bg="white")
        row.pack(anchor="w")
        tk.Label(row, text="B站UID：1321645331", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 10)).pack(side="left")
        self._light_button(row, "打开B站主页",
                           lambda: webbrowser.open("https://space.bilibili.com/1321645331")).pack(
            side="left", padx=12
        )

        repo_row = tk.Frame(left, bg="white")
        repo_row.pack(anchor="w", pady=(8, 0))
        tk.Label(repo_row, text="GitHub：xingchen-0220/StarRail-supply", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 10)).pack(side="left")
        self._light_button(repo_row, "打开仓库",
                           lambda: webbrowser.open(GITHUB_URL)).pack(side="left", padx=12)

        version_row = tk.Frame(left, bg="white")
        version_row.pack(anchor="w", pady=(18, 0))
        tk.Label(version_row, text=f"{APP_NAME}  v{APP_VERSION}", bg="white", fg="#94a3b8",
                 font=("Microsoft YaHei UI", 8)).pack(side="left")
        self._light_button(version_row, "检查更新",
                           lambda: self.check_updates(True)).pack(side="left", padx=10)

        qr_card, qr = self._card(wrap, padx=20, pady=18)
        qr_card.grid(row=0, column=1, sticky="n")
        tk.Label(qr, text="赞赏码", bg="white", fg=TEXT,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        try:
            self.qr_photo = self._load_image("reward_qr.png", 340)
            tk.Label(qr, image=self.qr_photo, bg="white").pack(pady=10)
        except Exception:
            tk.Label(qr, text="赞赏码图片加载失败", bg="white", fg=MUTED).pack(pady=20)
        tk.Label(qr, text="微信扫码 · 感谢支持", bg="white", fg=MUTED,
                 font=("Microsoft YaHei UI", 9)).pack()

    # --------------------------------------------------------- 状态/日志 --
    def log(self, message):
        self.logger(message)

    def _poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "log":
                    self._append_log(value)
                elif kind == "status":
                    self.status_var.set(value)
                    self._append_log("[状态] " + value)
                elif kind == "progress":
                    index, total, text = value
                    self.overlay.update_step(index, total, text)
                elif kind == "done":
                    self._signin_done()
                elif kind == "update":
                    self._on_update_result(*value)
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def _append_log(self, line):
        widgets = [self.log_text]
        home_log = getattr(self, "home_log_text", None)
        if home_log is not None:
            widgets.append(home_log)
        for widget in widgets:
            widget.configure(state="normal")
            widget.insert("end", line + "\n")
            if int(widget.index("end-1c").split(".")[0]) > 800:
                widget.delete("1.0", "80.0")
            widget.see("end")
            widget.configure(state="disabled")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def refresh_status(self):
        if self.busy:
            return
        running = bool(launcher.game_window(cfg))
        if running:
            self.game_state_label.configure(text="● 运行中", fg="#16a34a")
            self.header_status.configure(text="游戏运行中", bg="#ecfdf5", fg="#047857")
        else:
            self.game_state_label.configure(text="○ 未运行", fg="#94a3b8")
            self.header_status.configure(text="游戏未运行", bg="#f1f5f9", fg="#64748b")

    def open_log(self):
        os.startfile(str(self.logger.path))

    def check_updates(self, manual=False):
        if self.update_checking:
            return
        self.update_checking = True
        if manual:
            self.log("正在检查 GitHub 更新…")

        def job():
            from .updater import check_for_update

            try:
                info = check_for_update(APP_VERSION)
                error = ""
            except Exception as exc:
                info = None
                error = str(exc)
            self.messages.put(("update", (info, error, manual)))

        threading.Thread(target=job, daemon=True).start()

    def _on_update_result(self, info, error, manual):
        self.update_checking = False
        if error:
            self.log(f"检查更新失败：{error}")
            if manual:
                messagebox.showwarning(
                    "检查更新失败",
                    "无法连接 GitHub。\n请检查网络后重试。\n\n" + error[:300],
                )
            return
        if not info or not info.get("is_new"):
            if manual:
                messagebox.showinfo("检查更新", f"当前已是最新版本 v{APP_VERSION}")
            return
        if not manual and cfg.get("skipped_version") == info["latest"]:
            self.log(f"已跳过版本 v{info['latest']}")
            return
        self.log(f"发现新版本：v{info['latest']}（当前 v{APP_VERSION}）")
        UpdateDialog(self, info)


# ------------------------------------------------------------ 配置 --
    def save_options(self):
        cfg.set("exit_game", bool(self.exit_game_var.get()))
        cfg.set("exit_app", bool(self.exit_app_var.get()))
        cfg.set("minimize_on_run", bool(self.minimize_var.get()))
        cfg.save()

    def save_schedule(self):
        if self.schedule_var.get() and self.task_exists():
            if messagebox.askyesno(
                "提示",
                "已经存在 Windows 计划任务。\n两者同时启用会在同一时间重复执行。\n\n"
                "是否删除计划任务，改用程序内定时？",
            ):
                self.delete_task(silent=True)
            else:
                self.schedule_var.set(False)
                return
        cfg.set("schedule_enabled", bool(self.schedule_var.get()))
        cfg.save()
        self.update_next_label()

    def task_exists(self):
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", TASK_NAME],
                capture_output=True, text=True, timeout=12, creationflags=0x08000000,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _sync_plan_task(self):
        self.plan_task_exists = self.task_exists()
        if self.plan_task_exists and cfg.get("schedule_enabled"):
            cfg.set("schedule_enabled", False)
            cfg.save()
            self.schedule_var.set(False)
            self.log("检测到 Windows 计划任务：程序内定时已自动关闭，避免重复执行。")
        self.update_next_label()

    def open_schedule(self):
        dialog = ScheduleDialog(self)
        self.root.wait_window(dialog)
        self.schedule_var.set(bool(cfg.get("schedule_enabled", False)))
        self.save_schedule()

    def save_daily_settings(self, verbose=True):
        cfg.set("daily_enabled", bool(self.daily_enabled_var.get()))
        cfg.set("daily_clear_power", bool(self.clear_power_var.get()))
        cfg.save()
        if verbose:
            self.log("日常设置已保存")

    def save_notify_settings(self, verbose=True):
        target = self.qq_target_var.get().strip()
        if target and not target.isdigit():
            if verbose:
                messagebox.showwarning("QQ 号格式错误", "目标 QQ 号只能填写数字")
            return
        cfg.set("notify_enabled", bool(self.notify_enabled_var.get()))
        cfg.set("onebot_url", self.onebot_url_var.get().strip() or "http://127.0.0.1:3000")
        cfg.set("onebot_token", self.onebot_token_var.get().strip())
        cfg.set("qq_target", target)
        cfg.set("send_screenshots", bool(self.send_shots_var.get()))
        cfg.save()
        if verbose:
            self.log("QQ 通知设置已保存")

    def test_notify(self):
        self.save_notify_settings(verbose=False)
        self.log("正在发送 QQ 测试消息…")

        def job():
            from .notifier import OneBotNotifier

            ok = OneBotNotifier(cfg, self.log).send_test()
            self.log("QQ 测试消息发送成功" if ok else "QQ 测试消息发送失败，请检查 API 地址/Token/QQ 号")

        threading.Thread(target=job, daemon=True).start()

    def save_settings(self):
        numeric_float = {"click_delay", "ocr_confidence"}
        numeric_int = {"launch_timeout", "title_timeout", "reward_timeout"}
        for key, var in self.setting_vars.items():
            value = var.get().strip()
            try:
                if key in numeric_int:
                    value = int(float(value))
                elif key in numeric_float:
                    value = float(value)
            except ValueError:
                messagebox.showwarning("格式错误", f"「{key}」需要填写数字")
                return
            cfg.set(key, value)
        cfg.set("game_path", self.path_var.get().strip())
        cfg.set("bring_to_front", bool(self.bring_front_var.get()))
        cfg.set("check_update_on_start", bool(self.update_check_var.get()))
        cfg.save()
        self.log("设置已保存")
        self.refresh_status()

    def browse(self):
        path = filedialog.askopenfilename(
            title="选择 StarRail.exe", filetypes=[("游戏程序", "StarRail.exe"), ("可执行文件", "*.exe")]
        )
        if path:
            self.path_var.set(path)
            cfg.set("game_path", path)
            cfg.save()

    def detect(self):
        path = launcher.detect_game_path(cfg)
        if path:
            self.path_var.set(path)
            cfg.set("game_path", path)
            cfg.save()
            self.log(f"已检测到游戏：{path}")
        else:
            messagebox.showwarning("未找到", "没有自动检测到游戏，请手动选择 StarRail.exe")

    def test_ocr(self):
        """不执行签到，只截取当前游戏画面并列出 OCR 到的文字。"""
        if not launcher.game_window(cfg):
            messagebox.showwarning("提示", "游戏未运行。请先启动游戏，再点「测试识别」。")
            return

        def job():
            from .vision import Automation

            self.messages.put(("status", "正在识别当前画面…"))
            try:
                auto = Automation(cfg, logger=self.log)
                auto.focus()
                lines = auto.ocr_lines()
                if not lines:
                    self.log("未识别到文字（画面可能是纯图或截图失败）")
                else:
                    self.log(f"当前画面识别到 {len(lines)} 行文字：")
                    for x, y, text, score in lines:
                        self.log(f"  ({x}, {y}) {text}  [{score:.2f}]")
            except Exception as exc:
                self.log(f"识别失败：{exc}")
            self.messages.put(("status", "识别完成"))

        threading.Thread(target=job, daemon=True).start()

    # ------------------------------------------------------------ 签到 --
    def start_signin(self):
        if self.busy:
            return
        path = self.path_var.get().strip()
        if path:
            cfg.set("game_path", path)
        if not cfg.get("game_path") or not os.path.isfile(cfg.get("game_path", "")):
            detected = launcher.detect_game_path(cfg)
            if detected:
                cfg.set("game_path", detected)
                self.path_var.set(detected)
            else:
                messagebox.showwarning("提示", "请先选择 StarRail.exe 的路径")
                return
        self.save_daily_settings(verbose=False)
        self.save_notify_settings(verbose=False)
        cfg.save()

        if not is_admin():
            self.log("提示：当前不是管理员权限。游戏要求管理员权限，模拟点击可能被系统拦截，建议右键以管理员身份运行本程序。")

        self.busy = True
        self.last_ok = False
        self.last_skipped = False
        self.stop_event = threading.Event()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        self.status_var.set("正在启动…")
        self.overlay.show("准备启动游戏…")
        if cfg.get("minimize_on_run", True):
            self.root.iconify()
            self.overlay.win.lift()

        def job():
            ok = False
            skipped = False
            try:
                from .flow import FullFlow

                flow = FullFlow(
                    cfg, self.log, stop_event=self.stop_event,
                    on_step=lambda text: self.messages.put(("status", text)),
                    on_progress=lambda index, total, text: self.messages.put(
                        ("progress", (index, total, text))
                    ),
                    mask_provider=lambda: self.overlay.rect(),
                )
                ok = flow.run()
                skipped = flow.skipped
                self.last_signin_ok = flow.signin_ok
                self.last_daily_ok = flow.daily_ok
            except Exception as exc:
                import traceback

                self.log(f"流程异常：{exc}")
                self.log(traceback.format_exc())
            self.last_ok = bool(ok)
            self.last_skipped = bool(skipped)
            self.messages.put(("done", None))

        self.worker = threading.Thread(target=job, daemon=True)
        self.worker.start()

    def _signin_done(self):
        self.busy = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        try:
            self.root.deiconify()
        except Exception:
            pass
        if self.last_skipped:
            self.status_var.set("另一个签到任务正在运行，本窗口未重复执行")
            self.overlay.finish("已有签到任务在运行", ok=None, hide_after=5000)
            self.log("—— 已有签到任务在运行，本次跳过 ——")
            return
        if self.last_signin_ok and self.last_daily_ok is False:
            self.status_var.set("签到成功，日常执行失败，请查看日志")
            self.log("—— 签到成功，日常执行失败 ——")
            self.overlay.finish("签到成功，日常失败", ok=False, hide_after=8000)
            return
        if not self.last_signin_ok and self.last_daily_ok:
            self.status_var.set("签到失败，日常已完成")
            self.log("—— 签到失败，日常完成 ——")
            self.overlay.finish("签到失败，日常完成", ok=None, hide_after=8000)
            if cfg.get("exit_app", True):
                self._countdown_exit(5)
            return
        if self.last_ok:
            done_text = "签到与日常完成" if self.last_daily_ok else "签到完成"
            self.status_var.set(done_text)
            self.log("—— " + done_text + " ——")
            self.overlay.finish(done_text, ok=True)
            if cfg.get("exit_app", True):
                self._countdown_exit(5)
        else:
            if self.stop_event and self.stop_event.is_set():

                self.status_var.set("已停止")
                self.overlay.finish("已停止", ok=False, hide_after=6000)
            else:

                self.status_var.set("签到失败，请查看日志")
                self.log("—— 签到失败 ——")

    def _countdown_exit(self, seconds):
        if seconds <= 0:
            self.root.destroy()
            return
        self.status_var.set(f"签到完成，{seconds} 秒后退出程序…")
        self.root.after(1000, lambda: self._countdown_exit(seconds - 1))

    def stop_task(self):
        if self.stop_event:
            self.stop_event.set()
            self.status_var.set("正在停止…")

    # ------------------------------------------------------------ 定时 --
    def _tick_schedule(self):
        try:
            if cfg.get("schedule_enabled") and not self.busy:
                now = datetime.now()
                days = schedule_days()
                if now.strftime("%H:%M") == cfg.get("schedule_time", "08:00"):
                    if now.isoweekday() in days and cfg.get("last_run") != now.date().isoformat():
                        if self.task_exists():
                            self.plan_task_exists = True
                            cfg.set("last_run", now.date().isoformat())
                            cfg.save()
                            self.log("已存在计划任务，跳过程序内定时，避免重复执行")
                            return
                        cfg.set("last_run", now.date().isoformat())
                        cfg.save()
                        self.log(f"定时签到触发：{now.strftime('%Y-%m-%d %H:%M')}")
                        self.start_signin()
        finally:
            self.update_next_label()
            self.root.after(15000, self._tick_schedule)

    def update_next_label(self):
        if not hasattr(self, "next_label"):
            return
        if not cfg.get("schedule_enabled"):
            if hasattr(self, "schedule_summary"):
                if getattr(self, "plan_task_exists", False):
                    time_text = cfg.get("schedule_time", "08:00")
                    self.schedule_summary.configure(text="计划任务已创建")
                    self.next_label.configure(text="由 Windows 计划任务执行")
                else:
                    self.schedule_summary.configure(text="未启用")
                    self.next_label.configure(text="")
            self._sync_home_schedule()
            return
        try:
            hour, minute = [int(part) for part in cfg.get("schedule_time", "08:00").split(":")]
        except Exception:
            return
        days = schedule_days()
        if hasattr(self, "schedule_summary"):
            self.schedule_summary.configure(text=f"{days_text(days)} {hour:02d}:{minute:02d}")

        now = datetime.now()
        for offset in range(0, 8):
            target = (now + timedelta(days=offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now or target.isoweekday() not in days:
                continue
            prefix = "今天" if offset == 0 else "明天" if offset == 1 else DAY_LABELS[target.isoweekday() - 1]
            self.next_label.configure(text=f"下次：{prefix} {target:%H:%M}")
            self._sync_home_schedule()
            return
        self.next_label.configure(text="")
        self._sync_home_schedule()

    def _sync_home_schedule(self):
        if not hasattr(self, "home_schedule_label"):
            return
        if cfg.get("schedule_enabled"):
            self.home_schedule_label.configure(text=self.schedule_summary.cget("text"))
            self.home_next_label.configure(text=self.next_label.cget("text"))
        elif getattr(self, "plan_task_exists", False):
            self.home_schedule_label.configure(text="计划任务已创建")
            self.home_next_label.configure(text="由 Windows 计划任务执行")
        else:
            self.home_schedule_label.configure(text="未启用")
            self.home_next_label.configure(text="")

    def _task_bat(self):
        bat = DATA_DIR / "auto_signin.bat"
        if is_frozen():
            command = f'"{sys.executable}" --auto'
        else:
            command = f'"{sys.executable}" "{os.path.join(os.path.dirname(DATA_DIR), "main.py")}" --auto'
        content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            f'cd /d "{os.path.dirname(DATA_DIR)}"\r\n'
            f"{command} >> \"{DATA_DIR}\\logs\\scheduled.log\" 2>&1\r\n"
        )
        bat.write_text(content, encoding="utf-8")
        return bat

    def create_task(self):
        if not is_admin():
            messagebox.showwarning("需要管理员权限",
                                   "创建计划任务需要管理员权限。\n请关闭本程序，右键选择「以管理员身份运行」后再创建。")
            return
        time_str = cfg.get("schedule_time", "08:00")
        days = schedule_days()
        if not days:
            messagebox.showwarning("提示", "请先在「设置定时」中选择重复日期")
            return
        bat = self._task_bat()
        try:
            if len(days) == 7:
                schedule_args = ["/SC", "DAILY"]
            else:
                schedule_args = ["/SC", "WEEKLY", "/D", ",".join(DAY_KEYS[day - 1] for day in days)]
            result = subprocess.run(
                ["schtasks", "/Create", "/F", *schedule_args, "/ST", time_str, "/RL", "HIGHEST",
                 "/TN", TASK_NAME, "/TR", f'"{bat}"'],
                capture_output=True, text=True, timeout=25, creationflags=0x08000000,
            )
            query = subprocess.run(
                ["schtasks", "/Query", "/TN", TASK_NAME],
                capture_output=True, text=True, timeout=20, creationflags=0x08000000,
            )
            if query.returncode == 0:
                cfg.set("schedule_enabled", False)
                cfg.save()
                self.schedule_var.set(False)
                self.plan_task_exists = True
                self.update_next_label()
                self.log(f"已创建计划任务：{days_text(days)} {time_str}；程序内定时已关闭，避免重复")
                messagebox.showinfo(
                    "成功",
                    f"已创建计划任务：{days_text(days)} {time_str}。\n"
                    "程序不在运行也会执行，程序内定时已自动关闭。",
                )
            else:
                self.log(result.stdout + result.stderr)
                messagebox.showwarning("失败", "创建计划任务失败，请查看日志或尝试以管理员身份运行。")
        except Exception as exc:
            self.log(f"创建计划任务异常：{exc}")
            messagebox.showerror("错误", str(exc))

    def delete_task(self, silent=False):
        try:
            subprocess.run(
                ["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
                capture_output=True, text=True, timeout=20, creationflags=0x08000000,
            )
            self.plan_task_exists = False
            self.update_next_label()
            self.log("已删除计划任务")
            if not silent:
                messagebox.showinfo("完成", "已删除每日签到计划任务。")
        except Exception as exc:
            self.log(f"删除计划任务异常：{exc}")

    # ------------------------------------------------------------ 关闭 --
    def on_close(self):
        if self.busy:
            if not messagebox.askyesno("确认", "签到仍在进行，确定退出吗？"):
                return
            if self.stop_event:
                self.stop_event.set()
        self.save_options()
        cfg.set("schedule_enabled", bool(self.schedule_var.get()))
        cfg.save()
        try:
            self.overlay.destroy()
        except Exception:
            pass
        self.root.destroy()


DAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
DAY_KEYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def schedule_days():
    days = cfg.get("schedule_days") or [1, 2, 3, 4, 5, 6, 7]
    return sorted({int(day) for day in days if 1 <= int(day) <= 7})


def days_text(days):
    days = sorted(set(days))
    if len(days) == 7:
        return "每天"
    if days == [1, 2, 3, 4, 5]:
        return "工作日"
    if days == [6, 7]:
        return "周末"
    return "、".join(DAY_LABELS[day - 1] for day in days)


class UpdateDialog(tk.Toplevel):
    """发现新版本时的弹窗。"""

    def __init__(self, app, info):
        super().__init__(app.root)
        self.app = app
        self.info = info
        self.title("发现新版本")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()
        self.geometry("+%d+%d" % (app.root.winfo_rootx() + 160, app.root.winfo_rooty() + 90))

        body = ttk.Frame(self, padding=(20, 16, 20, 12))
        body.pack(fill="both", expand=True)
        tk.Label(body, text=f"发现新版本 v{info['latest']}", bg=BG, fg=TEXT,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        tk.Label(body,
                 text=f"当前版本 v{info['current']}  →  最新版本 v{info['latest']}（{info.get('source', 'GitHub')}）",
                 bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(4, 12))

        tk.Label(body, text="更新内容", bg=BG, fg=TEXT,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        notes = tk.Text(body, width=72, height=14, bg="#111318", fg="#d7dce8",
                        relief="flat", font=("Microsoft YaHei UI", 9), padx=10, pady=8)
        notes.pack(fill="both", expand=True, pady=(6, 10))
        notes.insert("1.0", str(info.get("notes") or "（该版本没有填写更新说明）"))
        notes.configure(state="disabled")

        self.skip_var = tk.BooleanVar(value=False)
        tk.Checkbutton(body, text=f"跳过此版本（v{info['latest']}）", variable=self.skip_var,
                       bg=BG, activebackground=BG, selectcolor="white", fg=TEXT,
                       font=("Microsoft YaHei UI", 9)).pack(anchor="w")

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="稍后", command=self.close).pack(side="right", padx=6)
        ttk.Button(buttons, text="打开 Release 页面",
                   command=lambda: webbrowser.open(info.get("url") or GITHUB_URL)).pack(
            side="right", padx=6)
        ttk.Button(buttons, text="前往下载", style="Accent.TButton",
                   command=self.download).pack(side="right", padx=6)

        self.protocol("WM_DELETE_WINDOW", self.close)

    def download(self):
        url = self.info.get("download") or self.info.get("url") or GITHUB_URL
        webbrowser.open(url)
        self.close()

    def close(self):
        if self.skip_var.get():
            cfg.set("skipped_version", self.info["latest"])
            cfg.save()
            self.app.log(f"已跳过版本 v{self.info['latest']}")
        self.destroy()


class ScheduleDialog(tk.Toplevel):
    """图形化定时设置：时间 + 星期。"""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("设置定时签到")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()
        self.geometry("+%d+%d" % (app.root.winfo_rootx() + 90, app.root.winfo_rooty() + 120))

        body = ttk.Frame(self, padding=(20, 16, 20, 12))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="定时签到", font=("Microsoft YaHei UI", 14, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 12)
        )

        self.enabled_var = tk.BooleanVar(value=bool(cfg.get("schedule_enabled", False)))
        ttk.Checkbutton(body, text="启用定时", variable=self.enabled_var).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(0, 12)
        )

        ttk.Label(body, text="时间").grid(row=2, column=0, sticky="e", padx=(0, 10))
        hour, minute = [int(part) for part in cfg.get("schedule_time", "08:00").split(":")]
        self.hour_var = tk.StringVar(value=f"{hour:02d}")
        self.minute_var = tk.StringVar(value=f"{minute:02d}")
        time_box = ttk.Frame(body)
        time_box.grid(row=2, column=1, columnspan=3, sticky="w")
        tk.Spinbox(time_box, from_=0, to=23, width=3, font=("Consolas", 18, "bold"), justify="center",
                   textvariable=self.hour_var, format="%02.0f", relief="flat",
                   bg="white", buttonbackground="#e9ecef").pack(side="left", ipady=3)
        tk.Label(time_box, text=":", font=("Consolas", 18, "bold"), bg=BG).pack(side="left", padx=6)
        tk.Spinbox(time_box, from_=0, to=59, width=3, font=("Consolas", 18, "bold"), justify="center",
                   textvariable=self.minute_var, format="%02.0f", relief="flat",
                   bg="white", buttonbackground="#e9ecef").pack(side="left", ipady=3)
        ttk.Button(time_box, text="现在", width=6, command=self.use_now).pack(side="left", padx=12)

        ttk.Label(body, text="重复").grid(row=3, column=0, sticky="ne", padx=(0, 10), pady=(14, 0))
        days_frame = ttk.Frame(body)
        days_frame.grid(row=3, column=1, columnspan=3, sticky="w", pady=(14, 0))
        current = set(schedule_days())
        self.day_vars = {}
        for index in range(1, 8):
            var = tk.BooleanVar(value=index in current)
            self.day_vars[index] = var
            ttk.Checkbutton(days_frame, text=DAY_LABELS[index - 1], variable=var).grid(
                row=0, column=index - 1, padx=(0, 6)
            )
        presets = ttk.Frame(body)
        presets.grid(row=4, column=1, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(presets, text="每天", width=6, style="Small.TButton",
                   command=lambda: self.set_days([1, 2, 3, 4, 5, 6, 7])).pack(side="left")
        ttk.Button(presets, text="工作日", width=7, style="Small.TButton",
                   command=lambda: self.set_days([1, 2, 3, 4, 5])).pack(side="left", padx=6)
        ttk.Button(presets, text="周末", width=6, style="Small.TButton",
                   command=lambda: self.set_days([6, 7])).pack(side="left")

        ttk.Label(
            body,
            text="勾选“启用定时”后，程序需要保持运行；\n如需程序不运行也执行，请在主界面点“创建计划任务”。",
            foreground="#868e96", font=("Microsoft YaHei UI", 9), justify="left",
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(16, 10))

        buttons = ttk.Frame(body)
        buttons.grid(row=6, column=0, columnspan=4, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="保存", style="Accent.TButton", command=self.save).pack(side="left", padx=6)
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="left")

    def use_now(self):
        now = datetime.now()
        self.hour_var.set(f"{now.hour:02d}")
        self.minute_var.set(f"{now.minute:02d}")

    def set_days(self, days):
        for index, var in self.day_vars.items():
            var.set(index in days)

    def save(self):
        try:
            hour = int(self.hour_var.get())
            minute = int(self.minute_var.get())
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "时间格式不正确", parent=self)
            return
        days = [index for index, var in self.day_vars.items() if var.get()]
        if not days:
            messagebox.showwarning("提示", "请至少选择一天", parent=self)
            return
        cfg.set("schedule_enabled", bool(self.enabled_var.get()))
        cfg.set("schedule_time", f"{hour:02d}:{minute:02d}")
        cfg.set("schedule_days", days)
        cfg.save()
        self.destroy()


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_auto_with_overlay(log):
    """无主界面执行完整流程，只显示左下角步骤浮窗（计划任务用）。"""
    from .config import cfg as app_cfg

    root = tk.Tk()
    root.withdraw()
    overlay = StatusOverlay(root)
    overlay.show("准备启动游戏…")
    progress_queue = queue.Queue()
    result = {"ok": False, "signin_ok": False, "daily_ok": None, "done": False, "finished": False}

    def poll():
        try:
            while True:
                index, total, text = progress_queue.get_nowait()
                overlay.update_step(index, total, text)
        except queue.Empty:
            pass
        if result["done"] and not result["finished"]:
            result["finished"] = True
            finish()
        root.after(120, poll)

    def finish():
        if result["signin_ok"] and result["daily_ok"]:
            overlay.finish("签到与日常完成", ok=True)
        elif result["daily_ok"]:
            overlay.finish("签到失败，日常完成", ok=None)
        elif result["signin_ok"] and result["daily_ok"] is False:
            overlay.finish("签到成功，日常失败", ok=False)
        elif result["ok"]:
            overlay.finish("签到完成", ok=True)
        else:
            overlay.finish("签到失败", ok=False)
        root.after(3500, root.destroy)

    def job():
        try:
            from .flow import FullFlow

            flow = FullFlow(
                app_cfg, log,
                on_progress=lambda index, total, text: progress_queue.put((index, total, text)),
                mask_provider=lambda: overlay.rect(),
            )
            result["ok"] = bool(flow.run())
            result["signin_ok"] = bool(flow.signin_ok)
            result["daily_ok"] = flow.daily_ok
        except Exception as exc:
            log(f"流程异常：{exc}")
            result["ok"] = False
        finally:
            result["done"] = True

    root.after(120, poll)
    threading.Thread(target=job, daemon=True).start()
    root.mainloop()
    return result["ok"]


def run_demo_overlay():
    """浮窗预览（不启动游戏，用于检查样式）。"""
    root = tk.Tk()
    root.withdraw()
    overlay = StatusOverlay(root)
    steps = [
        (1, 7, "启动游戏"),
        (2, 7, "等待出现「点击进入」…"),
        (3, 7, "点击「点击进入」"),
        (4, 7, "等待出现「点击领取今日奖励」…"),
        (5, 7, "点击领取今日奖励"),
        (6, 7, "点击屏幕确认领取"),
        (7, 7, "关闭游戏"),
    ]

    def show(index):
        if index >= len(steps):
            overlay.finish("签到完成（演示）", ok=True)
            root.after(3000, root.destroy)
            return
        overlay.update_step(*steps[index])
        root.after(1100, lambda: show(index + 1))

    overlay.show("准备启动游戏…")
    root.after(900, lambda: show(0))
    root.mainloop()


def run_gui():
    winapi.set_dpi_aware()
    ensure_dirs()
    root = tk.Tk()
    icon = RESOURCE / "assets" / "icon.ico"
    if icon.is_file():
        try:
            root.iconbitmap(str(icon))
        except Exception:
            pass
    App(root)
    root.mainloop()



