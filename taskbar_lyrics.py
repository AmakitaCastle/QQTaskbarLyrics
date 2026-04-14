"""
Windows 任务栏歌词 — 模块化架构
入口文件，组装各模块
"""

import sys
import io

# 设置 stdout 编码为 utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.utils.log import log, _init_log
from src.media.provider import MediaInfoProvider
from src.lyrics.manager import LyricsManager
from src.lyrics.providers.qq import QQMusicProvider
from src.display.window import TaskbarLyricsWindow


class TaskbarLyricsApp:
    def __init__(self, local_dir=None):
        self.media = MediaInfoProvider()
        self.lyrics = LyricsManager(
            providers=[QQMusicProvider()],
            local_dir=local_dir
        )
        self.window = TaskbarLyricsWindow(
            on_play_pause=self.media.play_pause,
            on_next=self.media.next_track,
            on_prev=self.media.prev_track,
        )
        self._last_song = ""
        self._ly = []
        self._loading = False

    def _on_loaded(self, ly):
        def a():
            self._ly = ly
            self._loading = False
            log(f"[App] {len(ly)} 行")
        self.window.root.after(0, a)

    def _tick(self):
        try:
            info = self.media.get_info()
            title, artist, album = info["title"], info["artist"], info.get("album", "")
            pos = info["position_ms"]
            key = f"{artist}|{title}"
            if key != self._last_song:
                self._last_song = key
                self._ly = []
                if title:
                    self._loading = True
                    self.lyrics.load_async(title, artist, self._on_loaded, album)
                else:
                    self._loading = False
            if title:
                if self._loading:
                    self.window.karaoke.update_display("♪ 正在加载歌词...", "", 0.0)
                elif self._ly:
                    o, t, p = self.lyrics.get_current_line(self._ly, pos)
                    self.window.karaoke.update_display(o, t, p)
                else:
                    self.window.karaoke.update_display("♪ 暂无歌词 ♪", "", 0.0)
            else:
                self.window.karaoke.update_display("♪ 等待播放...", "", 0.0)
            self.window.set_play_state(self.media.is_playing())
        except Exception as e:
            log(f"[Error] {e}")
        self.window.root.after(50, self._tick)

    def run(self):
        _init_log()
        log("=" * 50)
        log("  Windows 任务栏歌词 — 模块化架构")
        log("=" * 50)
        log("  左键拖拽 | 托盘菜单 | Esc退出 | Ctrl+T穿透")
        log("")
        self.media.start()
        self.window.root.after(500, self._tick)
        try:
            self.window.run()
        finally:
            self.media.stop()


if __name__ == "__main__":
    TaskbarLyricsApp(local_dir=None).run()
