"""
Windows 任务栏歌词 — 丝滑卡拉OK版
===================================
像素级逐字高亮 + 边界字符渐变 + 时间插值
依赖：pip install winsdk pywin32 requests
"""

import sys
import io

# 设置 stdout 编码为 utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.utils.log import log, _init_log
from src.media.provider import MediaInfoProvider
from src.lyrics.cache import load_disk_lyrics, save_disk_lyrics, disk_cache_key
from src.lyrics.manager import LyricsManager
from src.display.window import TaskbarLyricsWindow

import re, threading


# ============================================================
# 主程序
# ============================================================

class TaskbarLyricsApp:
    def __init__(self, local_dir=None):
        self.media = MediaInfoProvider()
        self.lyrics = LyricsManager([], local_dir)
        self.window = TaskbarLyricsWindow()
        self._last_song = ""; self._ly = []; self._loading = False

    def _on_loaded(self, ly):
        def a(): self._ly=ly; self._loading=False; print(f"[App] {len(ly)} 行")
        self.window.root.after(0, a)

    def _tick(self):
        try:
            info = self.media.get_info()
            title,artist,album = info["title"],info["artist"],info.get("album","")
            pos_raw = info["position_ms"]
            pos = pos_raw - self.window._lyric_offset_ms
            key = f"{artist}|{title}"
            if key != self._last_song:
                self._last_song=key; self._ly=[]
                if title:
                    self._loading=True
                    self.lyrics.load_async(title,artist,self._on_loaded,album)
                else: self._loading=False
            if title:
                if self._loading:
                    self.window.update_debug_info(pos_raw, pos, "loading...", 0.0)
                    self.window.update_display("♪ 正在加载歌词...","",0.0)
                elif self._ly:
                    o,t,p = self.lyrics.get_current_line(self._ly, pos)
                    self.window.update_debug_info(pos_raw, pos, o, p)
                    self.window.update_display(o,t,p)
                else:
                    self.window.update_debug_info(pos_raw, pos, "no lyrics", 0.0)
                    self.window.update_display("♪ 暂无歌词 ♪","",0.0)
            else:
                self.window.update_display("♪ 等待播放...","",0.0)
        except Exception as e:
            log(f"[Error] {e}")
        # 50ms = 20fps，卡拉OK丝滑的关键
        self.window.root.after(50, self._tick)

    def run(self):
        _init_log()
        log("="*50)
        log("  Windows 任务栏歌词 — 丝滑卡拉OK")
        log("="*50)
        log("  左键拖拽 | 右键菜单 | 上下箭头调偏移 | 右键菜单开调试")
        log("")
        self.media.start()
        self.window.root.after(500, self._tick)
        try: self.window.run()
        finally: self.media.stop()

if __name__=="__main__":
    TaskbarLyricsApp(local_dir=None).run()