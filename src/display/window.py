"""
任务栏歌词窗口 — 封装窗口管理、拖拽、菜单、配置对话框
"""

import ctypes
import tkinter as tk
from tkinter import font as tkfont

from src.display.config import load_config, save_config
from src.display.karaoke import KaraokeEngine
from src.display.config import show_color_config, show_font_config


class TaskbarLyricsWindow:
    DEFAULT_COLORS = {"bg": "#1a1a2e", "sung": "#FFD700", "unsung": "#555566"}
    DEFAULT_FONTS = {"lyric": ("Microsoft YaHei UI", 14, "bold")}

    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except:
                pass

        self.root = tk.Tk()
        self.root.title("TaskbarLyrics")
        self._config = load_config()
        self._colors = self._config.get("colors", self.DEFAULT_COLORS.copy())
        self._fonts = self._config.get("fonts", self.DEFAULT_FONTS.copy())

        # 透明模式：用一个极罕见颜色作为透明色
        self._TRANSPARENT_MAGIC = "#000001"
        _bg = self._colors.get("bg", self.DEFAULT_COLORS["bg"])
        _actual_bg = self._TRANSPARENT_MAGIC if _bg == "transparent" else _bg

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        ww, wh = min(900, sw - 200), 42
        pos = self._config.get("position", {})
        x = max(0, min(pos.get("x", (sw - ww) // 2), sw - ww))
        y = max(0, min(pos.get("y", sh - wh - 50), sh - wh))
        self.root.geometry(f"{ww}x{wh}+{x}+{y}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=_actual_bg)
        if _bg == "transparent":
            self.root.attributes("-transparentcolor", self._TRANSPARENT_MAGIC)
        self.root.after(100, self._setup_style)
        self.root.after(500, self._ensure_topmost)

        # ---- Canvas ----
        self.canvas = tk.Canvas(self.root, bg=_actual_bg,
                                height=wh, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=12)

        # Karaoke engine
        self.karaoke = KaraokeEngine(self.canvas, self._colors, self._fonts)

        # 拖拽
        self._drag = {"x": 0, "y": 0}
        self.canvas.bind("<Button-1>", lambda e: self._drag.update(x=e.x, y=e.y))
        self.canvas.bind("<B1-Motion>", self._drag_move)

        # 右键菜单 — 只保留：穿透、颜色、字体、退出
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="鼠标穿透 开/关 (Ctrl+T)", command=self._toggle_ct)
        self.menu.add_separator()
        self.menu.add_command(label="颜色设置", command=self._color_cfg)
        self.menu.add_command(label="字体设置", command=self._font_cfg)
        self.menu.add_separator()
        self.menu.add_command(label="退出 (Esc)", command=self._quit)
        self.root.bind("<Button-3>", self._show_menu)
        self._ct = False

        # 键盘快捷键：Esc 退出，Ctrl+T 切换穿透
        self.root.bind("<Escape>", lambda e: self._quit())
        self.root.bind("<Control-t>", lambda e: self._toggle_ct())
        self.root.bind("<Control-T>", lambda e: self._toggle_ct())

        self.root.bind("<Configure>", self._on_move)
        self.root.bind("<FocusOut>", lambda e: self._restore_topmost())

    def _show_menu(self, event):
        """弹出右键菜单，贴在鼠标上方，不挡住歌词"""
        try:
            spi = ctypes.windll.user32.SystemParametersInfoW
            work_area = ctypes.c_int * 4
            wa = work_area()
            spi(0x0030, 0, wa, 0)
            screen_top = wa[1]
            screen_bottom = wa[3]
        except:
            screen_top = 0
            screen_bottom = self.root.winfo_screenheight()

        menu_h = self.menu.winfo_reqheight()
        x, y = event.x_root, event.y_root
        y = y - menu_h - 2
        if y < screen_top:
            y = screen_top
        self.menu.post(x, y)

    def _hwnd(self):
        try:
            h = ctypes.windll.user32.FindWindowW(None, "TaskbarLyrics")
            return h or self.root.winfo_id()
        except:
            return None

    def _setup_style(self):
        try:
            h = self._hwnd()
            if not h:
                return
            s = ctypes.windll.user32.GetWindowLongW(h, -20)
            s |= 0x08000000 | 0x00000080
            ctypes.windll.user32.SetWindowLongW(h, -20, s)
            ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0,
                                              0x0001 | 0x0002 | 0x0010 | 0x0040)
        except:
            pass

    def _restore_topmost(self):
        """失焦时立即恢复最顶层，防止窗口短暂消失"""
        try:
            h = self._hwnd()
            if h:
                ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0,
                                                  0x0001 | 0x0002 | 0x0010 | 0x0040)
                self.root.attributes("-topmost", True)
        except:
            pass

    def _ensure_topmost(self):
        try:
            h = self._hwnd()
            if h:
                ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0,
                                                  0x0001 | 0x0002 | 0x0010)
                self.root.attributes("-topmost", True)
        except:
            pass
        self.root.after(500, self._ensure_topmost)

    def _drag_move(self, e):
        self.root.geometry(f"+{self.root.winfo_x() + e.x - self._drag['x']}+"
                           f"{self.root.winfo_y() + e.y - self._drag['y']}")

    def _on_move(self, e):
        if e.widget == self.root:
            if hasattr(self, '_sid'):
                self.root.after_cancel(self._sid)
            self._sid = self.root.after(500, self._save_pos)

    def _save_pos(self):
        try:
            self._config["position"] = {"x": self.root.winfo_x(), "y": self.root.winfo_y()}
            self._save_config()
        except:
            pass

    def _toggle_ct(self):
        self._ct = not self._ct
        try:
            h = self._hwnd()
            if h:
                s = ctypes.windll.user32.GetWindowLongW(h, -20)
                if self._ct:
                    s |= 0x20
                else:
                    s &= ~0x20
                ctypes.windll.user32.SetWindowLongW(h, -20, s)
        except:
            pass

    def _quit(self):
        self.root.quit()
        self.root.destroy()

    def _color_cfg(self):
        show_color_config(self.root, self._colors, self._apply_colors, self.root, self.canvas)

    def _apply_colors(self):
        """应用颜色配置到窗口"""
        self._TRANSPARENT_MAGIC = "#000001"
        _bg = self._colors.get("bg", self.DEFAULT_COLORS["bg"])
        _actual_bg = self._TRANSPARENT_MAGIC if _bg == "transparent" else _bg
        self.root.configure(bg=_actual_bg)
        self.canvas.configure(bg=_actual_bg)
        if _bg == "transparent":
            self.root.attributes("-transparentcolor", self._TRANSPARENT_MAGIC)
        else:
            self.root.attributes("-transparentcolor", "")
        self.karaoke._text = ""  # force rebuild
        self._save_config()

    def _font_cfg(self):
        show_font_config(self.root, self._fonts, self._save_config, self.karaoke)

    def _save_config(self):
        self._config["colors"] = self._colors
        self._config["fonts"] = self._fonts
        save_config(self._config)

    def update_display(self, orig: str, trans: str, progress: float):
        self.karaoke.update_display(orig, trans, progress)

    def run(self):
        self.root.mainloop()
