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
    DEFAULT_COLORS = {"bg": "#1a1a2e", "sung": "#FFD700", "unsung": "#555566",
                      "divider": "#2a2a38"}
    DEFAULT_FONTS = {"lyric": ("Microsoft YaHei UI", 14, "bold")}
    DEFAULT_SIZE = {"width": 900, "height": 32}
    BUTTON_AREA_WIDTH = 86  # 3×26 + spacing for control buttons

    def __init__(self, on_play_pause=None, on_next=None, on_prev=None):
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
        self._callbacks = {
            "play_pause": on_play_pause,
            "next": on_next,
            "prev": on_prev,
        }
        self._playing = True  # current play state for button icon
        self._btn_prev = None
        self._btn_play = None
        self._btn_next = None
        self._ct = False

        # 透明模式：用一个极罕见颜色作为透明色
        self._TRANSPARENT_MAGIC = "#000001"
        _bg = self._colors.get("bg", self.DEFAULT_COLORS["bg"])
        _actual_bg = self._TRANSPARENT_MAGIC if _bg == "transparent" else _bg
        self._actual_bg = _actual_bg

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        _size = self._config.get("size", {})
        ww = max(200, min(_size.get("width", self.DEFAULT_SIZE["width"]), sw))
        wh = max(20, min(_size.get("height", self.DEFAULT_SIZE["height"]), 200))
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

        # ---- 容器：按钮 + 分隔线 + 歌词 ----
        self.container = tk.Frame(self.root, bg=_actual_bg, height=wh)
        self.container.pack(fill=tk.X, expand=False)

        # 左侧控制按钮组
        self.ctrl_group = tk.Frame(self.container, bg=_actual_bg,
                                   width=self.BUTTON_AREA_WIDTH)
        self.ctrl_group.pack(side=tk.LEFT, fill=tk.Y)
        self.ctrl_group.pack_propagate(False)

        self._create_control_buttons(wh)

        # 分隔线
        div_color = self._colors.get("divider", self.DEFAULT_COLORS["divider"])
        self.divider = tk.Frame(self.container, bg=div_color, width=1, height=wh)
        self.divider.pack(side=tk.LEFT, padx=8)

        # 歌词 Canvas
        self.canvas = tk.Canvas(self.container, bg=_actual_bg,
                                height=wh, highlightthickness=0, bd=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Karaoke engine（传入按钮区偏移）
        self.karaoke = KaraokeEngine(
            self.canvas, self._colors, self._fonts,
            offset_x=self.BUTTON_AREA_WIDTH + 1 + 16  # buttons + divider + padding
        )

        # 拖拽 — bind to each widget so events are not swallowed by children
        self._drag = {"x": 0, "y": 0}
        for w in (self.container, self.ctrl_group, self.divider, self.canvas):
            w.bind("<Button-1>", lambda e: self._drag.update(x=e.x, y=e.y))
            w.bind("<B1-Motion>", self._drag_move)

        # 键盘快捷键：Esc 退出，Ctrl+T 切换穿透
        self.root.bind("<Escape>", lambda e: self._quit())
        self.root.bind("<Control-t>", lambda e: self._toggle_ct())
        self.root.bind("<Control-T>", lambda e: self._toggle_ct())

        self.root.bind("<Configure>", self._on_move)
        self.root.bind("<FocusOut>", lambda e: self._restore_topmost())

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

    # ---- 播放控制按钮 ----

    def _create_control_buttons(self, container_h: int):
        """创建水平排列的 prev / play-pause / next 圆形按钮"""
        btn_size = 26
        btn_fg = "#ccccdd"

        # 垂直居中
        start_x = (self.BUTTON_AREA_WIDTH - btn_size * 3) // 2
        start_y = (container_h - btn_size) // 2

        self._btn_prev = self._make_circle_btn(
            "\u23ee", start_x, start_y, btn_size, btn_fg, self._on_prev
        )
        self._btn_play = self._make_circle_btn(
            "\u23f8", start_x + btn_size, start_y, btn_size, btn_fg, self._on_play_pause
        )
        self._btn_next = self._make_circle_btn(
            "\u23ed", start_x + btn_size * 2, start_y, btn_size, btn_fg, self._on_next
        )

    def _make_circle_btn(self, text: str, x: int, y: int, size: int,
                         fg: str, command):
        """创建一个圆形按钮（Canvas + oval + text + hover）"""
        canvas = tk.Canvas(self.ctrl_group, width=size, height=size,
                           bg=self._actual_bg,
                           highlightthickness=0, bd=0)
        canvas.place(x=x, y=y)

        r = size // 2
        canvas.create_oval(0, 0, size, size, fill="", outline="", tags="bg")
        canvas.create_text(r, r, text=text, fill=fg,
                           font=("Segoe UI Symbol", 11), anchor="center", tags="icon")

        canvas._fg = fg
        canvas.bind("<Enter>", lambda e, c=canvas: self._btn_hover(c, True))
        canvas.bind("<Leave>", lambda e, c=canvas: self._btn_hover(c, False))
        canvas.bind("<Button-1>", lambda e, cmd=command: cmd())

        return canvas

    def _btn_hover(self, canvas: tk.Canvas, enter: bool):
        """按钮 hover 效果：显示/隐藏半透明圆形背景"""
        if enter:
            canvas.delete("bg")
            canvas.create_oval(0, 0, int(canvas["width"]), int(canvas["height"]),
                               fill="#33334a", outline="", tags="bg")
        else:
            canvas.delete("bg")
            canvas.create_oval(0, 0, int(canvas["width"]), int(canvas["height"]),
                               fill="", outline="", tags="bg")

    def _on_play_pause(self):
        if self._callbacks["play_pause"]:
            self._callbacks["play_pause"]()
            self._playing = not self._playing
            self._update_play_button()

    def _on_next(self):
        if self._callbacks["next"]:
            self._callbacks["next"]()

    def _on_prev(self):
        if self._callbacks["prev"]:
            self._callbacks["prev"]()

    def _update_play_button(self):
        """更新播放/暂停按钮图标和颜色"""
        if self._btn_play:
            icon = "\u25b6" if not self._playing else "\u23f8"
            color = "#FFD700" if self._playing else "#ccccdd"
            for item_id in self._btn_play.find_all():
                tags = self._btn_play.gettags(item_id)
                if "icon" in tags:
                    self._btn_play.itemconfig(item_id, text=icon, fill=color)
                    break

    def set_play_state(self, playing: bool):
        """外部调用：同步播放状态"""
        if self._playing != playing:
            self._playing = playing
            self._update_play_button()

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
            self._config["size"] = {"width": self.root.winfo_width(), "height": self.root.winfo_height()}
            self._save_config()
        except:
            pass

    def _toggle_ct(self):
        try:
            h = self._hwnd()
            if h:
                s = ctypes.windll.user32.GetWindowLongW(h, -20)
                s ^= 0x20  # toggle WS_EX_TRANSPARENT
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
        _bg = self._colors.get("bg", self.DEFAULT_COLORS["bg"])
        _actual_bg = self._TRANSPARENT_MAGIC if _bg == "transparent" else _bg
        self._actual_bg = _actual_bg
        self.root.configure(bg=_actual_bg)
        self.container.configure(bg=_actual_bg)
        self.ctrl_group.configure(bg=_actual_bg)
        self.canvas.configure(bg=_actual_bg)
        for btn in (self._btn_prev, self._btn_play, self._btn_next):
            if btn:
                btn.configure(bg=_actual_bg)
        if _bg == "transparent":
            self.root.attributes("-transparentcolor", self._TRANSPARENT_MAGIC)
        else:
            self.root.attributes("-transparentcolor", "")
        self.karaoke._text = ""  # force rebuild
        # 更新分隔线颜色
        div_color = self._colors.get("divider", self.DEFAULT_COLORS["divider"])
        self.divider.configure(bg=div_color)
        self._save_config()

    def _font_cfg(self):
        show_font_config(self.root, self._fonts, self._save_config, self.karaoke)

    def _size_cfg(self):
        """窗口大小设置"""
        sw = self.root.winfo_screenwidth()
        cur_w = self.root.winfo_width()
        cur_h = self.root.winfo_height()
        win = tk.Toplevel(self.root)
        win.title("窗口大小")
        win.geometry("340x120")
        win.configure(bg="#2a2a3e")
        win.transient(self.root)
        win.grab_set()

        f = tk.Frame(win, bg="#2a2a3e")
        f.pack(fill=tk.X, padx=20, pady=10)
        vw = tk.IntVar(value=cur_w)
        vh = tk.IntVar(value=cur_h)
        tk.Label(f, text="宽", fg="#FFF", bg="#2a2a3e",
                 font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
        tk.Spinbox(f, from_=200, to=sw, textvariable=vw, width=6,
                   font=("Consolas", 11)).pack(side=tk.LEFT, padx=8)
        tk.Label(f, text="高", fg="#FFF", bg="#2a2a3e",
                 font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT, padx=(12, 0))
        tk.Spinbox(f, from_=20, to=200, textvariable=vh, width=6,
                   font=("Consolas", 11)).pack(side=tk.LEFT, padx=8)

        bf = tk.Frame(win, bg="#2a2a3e")
        bf.pack(fill=tk.X, padx=20, pady=10)

        def apply():
            w = max(200, min(vw.get(), sw))
            h = max(20, min(vh.get(), 200))
            self.root.geometry(f"{w}x{h}")
            self._config["size"] = {"width": w, "height": h}
            self._save_config()
            win.destroy()

        tk.Button(bf, text="应用", command=apply, bg="#4a4a6e", fg="#FFF",
                  width=10).pack(side=tk.LEFT)
        tk.Button(bf, text="关闭", command=win.destroy, bg="#6a4a4e", fg="#FFF",
                  width=10).pack(side=tk.RIGHT)

    def _save_config(self):
        self._config["colors"] = self._colors
        self._config["fonts"] = self._fonts
        save_config(self._config)

    def update_display(self, orig: str, trans: str, progress: float):
        self.karaoke.update_display(orig, trans, progress)

    def run(self):
        self.root.mainloop()
