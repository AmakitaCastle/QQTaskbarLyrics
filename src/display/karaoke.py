"""
像素级卡拉OK渲染引擎 — 3 Canvas text item + 边界渐变
"""

import bisect
import tkinter as tk
from tkinter import font as tkfont


class KaraokeEngine:
    """像素级卡拉OK渲染"""

    def __init__(self, canvas: tk.Canvas, colors: dict, fonts: dict, offset_x: int = 0):
        self.canvas = canvas
        self.colors = colors
        self.fonts = fonts
        self.offset_x = offset_x

        self._text = ""
        self._sung_id = None
        self._mid_id = None
        self._unsung_id = None
        self._font_obj = None
        self._cum_widths = []
        self._total_px = 0
        self._canvas_w = 0
        self._last_split = -1
        self._last_mid_color = ""

        self.canvas.bind("<Configure>", lambda e: setattr(self, '_canvas_w', e.width))

    def update_display(self, orig: str, trans: str, progress: float):
        # // 是 QQ 音乐日文歌词的翻译分隔线，视为无效
        if trans in ("", "//"):
            trans = ""
        display = trans if trans else (orig or "♪ 等待播放 ♪")

        if display != self._text:
            self._text = display
            self._last_split = -1
            self._last_mid_color = ""
            self._rebuild(display)

        self._paint(display, progress)

    def _rebuild(self, text: str):
        """文本变化时：重建 Canvas 元素 + 预计算字符宽度"""
        self.canvas.delete("all")
        self._sung_id = self._mid_id = self._unsung_id = None
        if not text:
            return

        ft = self.fonts.get("lyric", ("Microsoft YaHei UI", 14, "bold"))
        if isinstance(ft, list):
            ft = tuple(ft)
        self._font_obj = tkfont.Font(family=ft[0], size=ft[1],
                                     weight=ft[2] if len(ft) > 2 else "normal")

        cum = [0]
        for ch in text:
            cum.append(cum[-1] + self._font_obj.measure(ch))
        self._cum_widths = cum
        self._total_px = cum[-1]

        # 垂直居中
        canvas_h = self.canvas.winfo_height() or 42
        cy = canvas_h // 2
        col_sung = self.colors.get("sung", "#FFD700")
        col_unsung = self.colors.get("unsung", "#555566")

        self._sung_id = self.canvas.create_text(0, cy, text="",
                                                 fill=col_sung, font=ft, anchor="w")
        self._mid_id = self.canvas.create_text(0, cy, text="",
                                                fill=col_unsung, font=ft, anchor="w")
        self._unsung_id = self.canvas.create_text(0, cy, text=text,
                                                   fill=col_unsung, font=ft, anchor="w")

    def _paint(self, text: str, progress: float):
        """每帧更新：像素级分割 + 边界渐变"""
        if not text or not self._sung_id:
            return

        progress = max(0.0, min(1.0, progress))
        highlight_px = self._total_px * progress
        cw = (self._canvas_w or 860) - self.offset_x
        cum = self._cum_widths
        n = len(text)

        split_idx = bisect.bisect_right(cum, highlight_px) - 1
        split_idx = max(0, min(split_idx, n - 1))

        ch_start = cum[split_idx]
        ch_end = cum[split_idx + 1] if split_idx < n else ch_start
        ch_w = ch_end - ch_start
        char_t = (highlight_px - ch_start) / ch_w if ch_w > 0 else 1.0
        char_t = max(0.0, min(1.0, char_t))

        col_sung = self.colors.get("sung", "#FFD700")
        col_unsung = self.colors.get("unsung", "#555566")
        mid_color = self._lerp_color(col_unsung, col_sung, char_t)

        if split_idx == self._last_split and mid_color == self._last_mid_color:
            return
        self._last_split = split_idx
        self._last_mid_color = mid_color

        sung_part = text[:split_idx]
        mid_char = text[split_idx] if split_idx < n else ""
        unsung_part = text[split_idx + 1:] if split_idx + 1 < n else ""

        sung_px = cum[split_idx]
        mid_px = ch_w

        if self._total_px <= cw:
            x0 = self.offset_x + (cw - self._total_px) / 2
        else:
            target = self.offset_x + cw * 0.4
            x0 = target - highlight_px
            x0 = max(self.offset_x + cw - self._total_px - 10, x0)
            x0 = min(self.offset_x + 10, x0)

        cy = self.canvas.winfo_height() // 2
        try:
            self.canvas.itemconfig(self._sung_id, text=sung_part)
            self.canvas.coords(self._sung_id, x0, cy)
            self.canvas.itemconfig(self._mid_id, text=mid_char, fill=mid_color)
            self.canvas.coords(self._mid_id, x0 + sung_px, cy)
            self.canvas.itemconfig(self._unsung_id, text=unsung_part)
            self.canvas.coords(self._unsung_id, x0 + sung_px + mid_px, cy)
        except tk.TclError:
            pass

    @staticmethod
    def _lerp_color(c1: str, c2: str, t: float) -> str:
        """线性插值两个 hex 颜色，t=0 返回 c1，t=1 返回 c2"""
        def norm_color(c):
            if not c or not isinstance(c, str) or not c.startswith('#'):
                return None
            if len(c) == 7:
                return c
            if len(c) == 4:
                return f"#{c[1]*2}{c[2]*2}{c[3]*2}"
            return None

        c1n = norm_color(c1)
        if c1n is None:
            c1n = "#FFD700"
        c2n = norm_color(c2)
        if c2n is None:
            c2n = "#555566"
        r1, g1, b1 = int(c1n[1:3], 16), int(c1n[3:5], 16), int(c1n[5:7], 16)
        r2, g2, b2 = int(c2n[1:3], 16), int(c2n[3:5], 16), int(c2n[5:7], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"
