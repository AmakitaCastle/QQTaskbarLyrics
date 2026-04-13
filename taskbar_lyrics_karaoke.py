#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows 任务栏歌词显示工具 - 卡拉OK逐字高亮版本
功能：
- 从 QQ音乐/网易云/Spotify 等获取播放信息
- 自动下载并匹配 LRC 歌词
- 卡拉OK风格：逐字高亮显示
- 原文+翻译双行显示
- 可拖拽、置顶、鼠标穿透

依赖：
    pip install winsdk requests
"""

import asyncio
import ctypes
import json
import re
import threading
import time
from pathlib import Path

import requests
import tkinter as tk
from tkinter import font as tkfont

# winsdk 用于获取系统媒体信息 (GSMTC)
try:
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as GSMTCManager,
    )
    from winsdk.windows.storage.streams import DataReader
except ImportError:
    print("请先安装 winsdk: pip install winsdk")
    raise


# ============================================================
# 第一部分：媒体信息获取（GSMTC）
# ============================================================

class MediaInfoProvider:
    """通过 Windows GSMTC API 获取当前播放的媒体信息"""

    def __init__(self):
        self._current_info = {"title": "", "artist": "", "position_ms": 0, "duration_ms": 0}
        self._lock = threading.Lock()
        self._running = False

    async def _get_media_session(self):
        """获取当前媒体会话"""
        try:
            manager = await GSMTCManager.request_async()
            sessions = manager.get_sessions()
            if not sessions:
                return None
            # 返回第一个会话（通常是当前活动的播放器）
            return sessions[0]
        except Exception as e:
            print(f"[MediaInfo] 获取媒体会话失败: {e}")
            return None

    async def _fetch_info(self):
        """从 GSMTC 拉取一次媒体信息"""
        session = await self._get_media_session()
        if session is None:
            return None

        try:
            info = await session.try_get_media_properties_async()
            title = info.title or ""
            artist = info.artist or ""

            timeline = session.get_timeline_properties()
            position_ms = int(timeline.position.total_seconds() * 1000)
            duration_ms = int(timeline.end_time.total_seconds() * 1000)

            return {
                "title": title,
                "artist": artist,
                "position_ms": position_ms,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            print(f"[MediaInfo] 读取媒体属性失败: {e}")
            return None

    def _poll_loop(self):
        """后台轮询线程"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        consecutive_failures = 0
        while self._running:
            try:
                info = loop.run_until_complete(self._fetch_info())
                if info:
                    with self._lock:
                        self._current_info = info
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 10:
                        with self._lock:
                            if self._current_info["title"]:
                                print(f"[MediaInfo] 播放器可能已停止")
                            self._current_info = {"title": "", "artist": "", "position_ms": 0, "duration_ms": 0}
                        consecutive_failures = 0
            except Exception as e:
                print(f"[MediaInfo] 轮询异常: {e}")
            time.sleep(0.5)

    def start(self):
        self._running = True
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def get_info(self):
        with self._lock:
            return self._current_info.copy()


# ============================================================
# 第二部分：歌词获取与解析
# ============================================================

class LyricsManager:
    """管理歌词的加载、解析和匹配"""

    def __init__(self, local_dir: Path | None = None):
        self.local_dir = Path(local_dir) if local_dir else None
        self._cache = {}  # 缓存已加载的歌词

    def _parse_lrc(self, lrc_text: str) -> list:
        """解析 LRC 格式歌词，返回 [(time_ms, text), ...]"""
        lines = []
        pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')
        for line in lrc_text.splitlines():
            m = pattern.match(line.strip())
            if m:
                minutes, seconds, centis, text = m.groups()
                if len(centis) == 2:
                    ms = int(centis) * 10
                else:
                    ms = int(centis)
                time_ms = int(minutes) * 60000 + int(seconds) * 1000 + ms
                if text.strip():
                    lines.append((time_ms, text.strip()))
        lines.sort(key=lambda x: x[0])
        return lines

    def _generate_search_variants(self, title: str, artist: str) -> list:
        """生成多种搜索变体，提高匹配率"""
        variants = []
        # 原始组合
        variants.append((title, artist))
        # 去掉括号内容
        clean_title = re.sub(r'\s*[（(][^)）]*[)）]', '', title).strip()
        clean_artist = re.sub(r'\s*[（(][^)）]*[)）]', '', artist).strip()
        if (clean_title, clean_artist) not in variants:
            variants.append((clean_title, clean_artist))
        # 只使用标题
        if title:
            variants.append((title, ""))
        if clean_title and clean_title != title:
            variants.append((clean_title, ""))
        return variants

    def _try_load_local(self, title: str, artist: str) -> list | None:
        """尝试从本地目录加载 LRC 文件"""
        if not self.local_dir or not self.local_dir.exists():
            return None

        candidates = [
            f"{artist} - {title}.lrc",
            f"{title} - {artist}.lrc",
            f"{title}.lrc",
        ]
        clean_title = re.sub(r'\s*[（(][^)）]*[)）]', '', title).strip()
        clean_artist = re.sub(r'\s*[（(][^)）]*[)）]', '', artist).strip()
        if clean_title != title:
            candidates.extend([
                f"{clean_artist} - {clean_title}.lrc",
                f"{clean_title} - {clean_artist}.lrc",
                f"{clean_title}.lrc",
            ])

        for name in candidates:
            path = self.local_dir / name
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8")
                    parsed = self._parse_lrc(text)
                    return [(t, txt, "") for t, txt in parsed]
                except Exception:
                    pass
        return None

    def _search_netease(self, track: str, artist: str) -> list | None:
        """网易云音乐搜索 + 歌词"""
        import requests

        headers = {
            "Referer": "https://music.163.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            resp = requests.post(
                "https://music.163.com/api/search/get/",
                data={"s": f"{track} {artist}".strip(), "type": 1, "limit": 5, "offset": 0},
                headers=headers, timeout=8,
            )
            songs = resp.json().get("result", {}).get("songs", [])
            if not songs:
                return None

            song = songs[0]
            song_id = song["id"]
            print(f"    [网易云] 匹配到: {song.get('name','')} (id={song_id})")

            lresp = requests.get(
                f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1",
                headers=headers, timeout=8,
            )
            ldata = lresp.json()
            lrc_text = ldata.get("lrc", {}).get("lyric", "")
            if not lrc_text:
                return None
            original = self._parse_lrc(lrc_text)
            if not original:
                return None

            trans_map = {}
            trans_lrc = ldata.get("tlyric", {}).get("lyric", "")
            if trans_lrc:
                for t, txt in self._parse_lrc(trans_lrc):
                    trans_map[t] = txt

            merged = [(t, text, trans_map.get(t, "")) for t, text in original]
            has_trans = sum(1 for _, _, tr in merged if tr)
            print(f"    [网易云] 歌词 {len(merged)} 行，翻译 {has_trans} 行")
            return merged
        except Exception as e:
            print(f"    [网易云] 失败: {e}")
            return None

    def _search_kuwo(self, track: str, artist: str) -> list | None:
        """酷我音乐搜索 + KRC歌词（支持逐字时间戳）"""
        import requests
        import base64

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://kuwo.cn/",
        }

        try:
            # 1. 搜索歌曲
            search_url = "https://search.kuwo.cn/r.s"
            params = {
                "all": f"{track} {artist}".strip(),
                "ft": "music",
                "itemset": "web_2013",
                "client": "kt",
                "pn": 0,
                "rn": 5,
                "rformat": "json",
                "encoding": "utf8",
            }
            resp = requests.get(search_url, params=params, headers=headers, timeout=8)
            data = resp.json()

            songs = data.get("abslist", [])
            if not songs:
                return None

            song = songs[0]
            song_id = song.get("MUSICRID", "").replace("MUSIC_", "")
            song_name = song.get("NAME", "")
            artist_name = song.get("ARTIST", "")
            print(f"    [酷我] 匹配到: {artist_name} - {song_name} (id={song_id})")

            if not song_id:
                return None

            # 2. 获取 KRC 歌词
            # 尝试多个 API 端点
            krc_apis = [
                f"https://m.kuwo.cn/newh5/singles/songinfoandlrc?musicId={song_id}",
                f"https://kuwo.cn/api/v1/www/music/musicInfo?mid={song_id}",
            ]

            for api_url in krc_apis:
                try:
                    lresp = requests.get(api_url, headers=headers, timeout=8)
                    ldata = lresp.json()

                    # 尝试解析不同格式的响应
                    krc_data = None
                    if "data" in ldata and "lrclist" in ldata["data"]:
                        krc_data = ldata["data"]["lrclist"]
                    elif "data" in ldata and "songinfo" in ldata["data"]:
                        # 可能需要另一个请求获取歌词
                        pass

                    if krc_data:
                        # 解析 KRC 格式
                        return self._parse_krc(krc_data)

                except Exception as e:
                    print(f"    [酷我] API尝试失败: {e}")
                    continue

            # 3. 回退到普通 LRC
            print(f"    [酷我] KRC获取失败，尝试LRC")
            return None

        except Exception as e:
            print(f"    [酷我] 失败: {e}")
            return None

    def _parse_krc(self, krc_data: list) -> list:
        """
        解析 KRC 格式歌词
        KRC格式: [{"time": 1000, "lineLyric": "歌词", "word": [{"startTime": 1000, "duration": 200, "word": "字"}, ...]}, ...]
        返回: [(time_ms, text, word_timings), ...]
        其中 word_timings: [(char_start_ms, char_duration_ms, char), ...]
        """
        lines = []
        for item in krc_data:
            try:
                time_ms = int(float(item.get("time", 0)) * 1000)
                text = item.get("lineLyric", "").strip()
                if not text:
                    continue

                # 解析逐字时间戳
                word_timings = []
                words = item.get("word", [])
                if words:
                    for word in words:
                        char_start = int(word.get("startTime", 0))
                        char_duration = int(word.get("duration", 0))
                        char_text = word.get("word", "")
                        if char_text:
                            word_timings.append((char_start, char_duration, char_text))

                # 存储格式: (time_ms, text, word_timings)
                lines.append((time_ms, text, word_timings))
            except Exception as e:
                print(f"    [KRC解析] 行解析失败: {e}")
                continue

        lines.sort(key=lambda x: x[0])
        print(f"    [酷我] KRC歌词 {len(lines)} 行，含逐字时间戳")
        return lines

    def _try_fetch_online(self, title: str, artist: str) -> list | None:
        """尝试在线获取歌词 - 优先获取KRC逐字歌词"""
        variants = self._generate_search_variants(title, artist)

        # 1. 优先尝试酷我音乐获取KRC逐字歌词
        print("  >> 尝试酷我音乐 (KRC逐字歌词)")
        for i, (t, a) in enumerate(variants):
            print(f"  [酷我 {i+1}/{len(variants)}] title=\"{t}\"  artist=\"{a}\"")
            result = self._search_kuwo(t, a)
            if result:
                print(f"  ✓ 酷我匹配成功 (KRC逐字歌词)!")
                return result

        # 2. 回退到网易云音乐
        print("  >> 尝试网易云音乐 (LRC普通歌词)")
        for i, (t, a) in enumerate(variants):
            print(f"  [网易云 {i+1}/{len(variants)}] title=\"{t}\"  artist=\"{a}\"")
            result = self._search_netease(t, a)
            if result:
                print(f"  ✓ 网易云匹配成功!")
                return result

        print(f"  ✗ 所有来源均未匹配到歌词")
        return None

    def load_lyrics(self, title: str, artist: str) -> list:
        """
        加载歌词（同步版本，用于后台线程）
        返回: [(time_ms, original, translation), ...]
        """
        cache_key = f"{artist}|{title}"
        if cache_key in self._cache:
            print(f"[Lyrics] 使用缓存: {artist} - {title}")
            return self._cache[cache_key]

        print(f"\n[Lyrics] 开始加载歌词: {artist} - {title}")

        # 1. 尝试本地
        result = self._try_load_local(title, artist)
        if result:
            print(f"[Lyrics] 本地加载成功: {len(result)} 行")
            self._cache[cache_key] = result
            return result

        # 2. 在线获取
        result = self._try_fetch_online(title, artist)
        if result:
            self._cache[cache_key] = result
            return result

        return []

    def load_lyrics_async(self, title: str, artist: str, callback):
        """后台线程加载歌词，完成后回调"""
        def _load():
            lyrics = self.load_lyrics(title, artist)
            callback(lyrics)
        t = threading.Thread(target=_load, daemon=True)
        t.start()

    def get_current_line(self, lyrics: list, position_ms: int) -> tuple:
        """
        根据播放进度，返回 (当前原文, 当前翻译, 进度信息)
        进度信息: 对于KRC格式是逐字进度列表，对于LRC是整体进度百分比
        """
        if not lyrics:
            return ("♪ 暂无歌词 ♪", "", 0)

        current_orig = ""
        current_trans = ""
        current_time = 0
        next_time = 0
        word_timings = []  # KRC逐字时间戳
        matched_index = -1

        for i, item in enumerate(lyrics):
            t = item[0]
            if t <= position_ms:
                current_orig = item[1]
                # 检查是否有逐字时间戳（KRC格式）或翻译（LRC格式）
                if len(item) > 2:
                    if isinstance(item[2], list):
                        # KRC格式: item[2] 是 word_timings 列表
                        word_timings = item[2]
                        current_trans = ""
                    else:
                        # LRC格式: item[2] 是翻译字符串
                        current_trans = item[2]
                        word_timings = []
                current_time = t
                matched_index = i
                # 获取下一句的时间
                if i + 1 < len(lyrics):
                    next_time = lyrics[i + 1][0]
                else:
                    next_time = t + 5000
            else:
                break

        # 还没到第一句
        if not current_orig and lyrics:
            current_orig = lyrics[0][1]
            if len(lyrics[0]) > 2:
                if isinstance(lyrics[0][2], list):
                    word_timings = lyrics[0][2]
                else:
                    current_trans = lyrics[0][2]
            current_time = lyrics[0][0]
            if len(lyrics) > 1:
                next_time = lyrics[1][0]
            else:
                next_time = current_time + 5000
            matched_index = 0

        # 如果有逐字时间戳（KRC格式），计算每个字的进度
        if word_timings:
            # 返回逐字进度列表: [(char, progress_0_to_100), ...]
            char_progress = []
            for char_start, char_duration, char_text in word_timings:
                # 计算当前字相对于行开始时间的偏移
                relative_pos = position_ms - current_time
                if relative_pos < char_start:
                    progress = 0
                elif relative_pos >= char_start + char_duration:
                    progress = 100
                else:
                    progress = (relative_pos - char_start) / char_duration * 100
                char_progress.append((char_text, progress))
            return (current_orig or "♪ 等待播放 ♪", current_trans, char_progress)
        else:
            # LRC格式: 返回整体进度百分比
            line_duration = next_time - current_time
            if line_duration > 0:
                progress = min(100, max(0, (position_ms - current_time) / line_duration * 100))
            else:
                progress = 0
            return (current_orig or "♪ 等待播放 ♪", current_trans, progress)


# ============================================================
# 第三部分：卡拉OK歌词显示窗口
# ============================================================

class KaraokeLyricsWindow:
    """
    卡拉OK风格歌词显示窗口
    - 逐字高亮效果
    - 原文+翻译双行显示
    """

    DEFAULT_COLORS = {
        "bg": "#1a1a2e",
        "text_unplayed": "#666666",  # 未播放的文字颜色
        "text_played": "#00ff88",    # 已播放的文字颜色（高亮）
        "trans": "#aaaaaa",          # 翻译文字颜色
    }

    DEFAULT_FONTS = {
        "lyric": ("Microsoft YaHei UI", 16, "bold"),
        "trans": ("Microsoft YaHei UI", 12, "normal"),
    }

    CONFIG_FILE = Path.home() / ".taskbar_lyrics_karaoke_config.json"

    def __init__(self):
        # DPI 感知
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except:
                pass

        self.root = tk.Tk()
        self.root.title("TaskbarLyricsKaraoke")

        self._config = self._load_config()
        self._colors = self._config.get("colors", self.DEFAULT_COLORS.copy())
        self._fonts = self._config.get("fonts", self.DEFAULT_FONTS.copy())

        # 窗口尺寸
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(1000, screen_w - 200)
        win_h = 80

        pos = self._config.get("position", {})
        x = max(0, min(pos.get("x", (screen_w - win_w) // 2), screen_w - win_w))
        y = max(0, min(pos.get("y", screen_h - win_h - 50), screen_h - win_h))

        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=self._colors["bg"])

        # 窗口样式设置
        self._setup_window_style()

        # ---- 布局 ----
        self.frame = tk.Frame(self.root, bg=self._colors["bg"])
        self.frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        # 原文行 - 使用 Canvas 实现逐字高亮
        self.lyric_canvas = tk.Canvas(
            self.frame, bg=self._colors["bg"],
            highlightthickness=0, height=35
        )
        self.lyric_canvas.pack(fill=tk.X, expand=False)

        # 翻译行
        self.trans_label = tk.Label(
            self.frame, text="",
            fg=self._colors["trans"], bg=self._colors["bg"],
            font=self._fonts["trans"],
            anchor="center",
        )
        self.trans_label.pack(fill=tk.X, expand=False)

        # 当前显示状态
        self._current_text = ""
        self._current_progress = 0

        # ---- 拖拽 ----
        self._drag_data = {"x": 0, "y": 0}
        for w in [self.frame, self.lyric_canvas, self.trans_label]:
            w.bind("<Button-1>", self._on_drag_start)
            w.bind("<B1-Motion>", self._on_drag_motion)

        # ---- 右键菜单 ----
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="鼠标穿透 开/关", command=self._toggle_click_through)
        self.menu.add_separator()
        self.menu.add_command(label="颜色设置", command=self._show_color_config)
        self.menu.add_command(label="字体设置", command=self._show_font_config)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self._quit)
        self.root.bind("<Button-3>", self._show_menu)

        self._click_through = False
        self.root.bind("<Configure>", self._on_window_move)

    def _setup_window_style(self):
        """使用 Windows API 设置窗口样式"""
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.FindWindowW(None, "TaskbarLyricsKaraoke")
            if not hwnd:
                hwnd = self.root.winfo_id()
                if not hwnd:
                    return

            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080

            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

            HWND_TOPMOST = -1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                               SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW)
        except Exception as e:
            print(f"[Window] 设置窗口样式失败: {e}")

    def _load_config(self):
        try:
            if self.CONFIG_FILE.exists():
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_config(self):
        try:
            self._config["colors"] = self._colors
            self._config["fonts"] = self._fonts
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _show_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def _toggle_click_through(self):
        self._click_through = not self._click_through
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "TaskbarLyricsKaraoke")
            if hwnd:
                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT = 0x00000020
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if self._click_through:
                    style |= WS_EX_TRANSPARENT
                else:
                    style &= ~WS_EX_TRANSPARENT
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception as e:
            print(f"[Window] 切换鼠标穿透失败: {e}")

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        x = self.root.winfo_x() + event.x - self._drag_data["x"]
        y = self.root.winfo_y() + event.y - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def _on_window_move(self, event):
        if event.widget == self.root:
            if hasattr(self, '_save_pos_id'):
                self.root.after_cancel(self._save_pos_id)
            self._save_pos_id = self.root.after(200, self._save_position)

    def _save_position(self):
        try:
            self._config["position"] = {"x": self.root.winfo_x(), "y": self.root.winfo_y()}
            self._save_config()
        except Exception:
            pass

    def _quit(self):
        self.root.destroy()

    def _show_color_config(self):
        """颜色配置窗口"""
        config_window = tk.Toplevel(self.root)
        config_window.title("颜色设置")
        config_window.geometry("350x200")
        config_window.configure(bg="#2a2a3e")
        config_window.transient(self.root)
        config_window.grab_set()

        colors = [
            ("背景色", "bg"),
            ("已播放颜色", "text_played"),
            ("未播放颜色", "text_unplayed"),
            ("翻译颜色", "trans"),
        ]

        self._color_vars = {}

        for i, (label, key) in enumerate(colors):
            frame = tk.Frame(config_window, bg="#2a2a3e")
            frame.pack(fill=tk.X, padx=20, pady=8)

            tk.Label(frame, text=label, fg="#FFFFFF", bg="#2a2a3e",
                    font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT)

            var = tk.StringVar(value=self._colors[key])
            self._color_vars[key] = var

            entry = tk.Entry(frame, textvariable=var, width=10,
                           font=("Microsoft YaHei UI", 10))
            entry.pack(side=tk.RIGHT)

        btn_frame = tk.Frame(config_window, bg="#2a2a3e")
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        tk.Button(btn_frame, text="应用", command=lambda: self._apply_colors(config_window),
                 bg="#4a4a6e", fg="#FFFFFF", font=("Microsoft YaHei UI", 10)).pack(side=tk.RIGHT, padx=5)

    def _apply_colors(self, window):
        try:
            for key, var in self._color_vars.items():
                self._colors[key] = var.get()

            self.root.configure(bg=self._colors["bg"])
            self.frame.configure(bg=self._colors["bg"])
            self.lyric_canvas.config(bg=self._colors["bg"])
            self.trans_label.config(fg=self._colors["trans"], bg=self._colors["bg"])

            self._save_config()
            window.destroy()
        except Exception as e:
            print(f"[UI] 应用颜色失败: {e}")

    def _show_font_config(self):
        """字体配置窗口"""
        config_window = tk.Toplevel(self.root)
        config_window.title("字体设置")
        config_window.geometry("400x200")
        config_window.configure(bg="#2a2a3e")
        config_window.transient(self.root)
        config_window.grab_set()

        # 获取系统字体列表
        try:
            from tkinter import font as tkfont
            system_fonts = sorted(set(tkfont.families()))
        except:
            system_fonts = ["Microsoft YaHei UI", "SimHei", "Arial", "Times New Roman"]

        font_options = [
            ("歌词字体", "lyric", 16),
            ("翻译字体", "trans", 12),
        ]

        self._font_vars = {}

        for i, (label, key, default_size) in enumerate(font_options):
            frame = tk.Frame(config_window, bg="#2a2a3e")
            frame.pack(fill=tk.X, padx=20, pady=8)

            tk.Label(frame, text=label, fg="#FFFFFF", bg="#2a2a3e",
                    font=("Microsoft YaHei UI", 11)).pack(side=tk.LEFT)

            current_font = self._fonts[key]
            var = tk.StringVar(value=current_font[0])
            self._font_vars[key] = var

            combo = tk.OptionMenu(frame, var, *system_fonts[:20])
            combo.config(bg="#4a4a6e", fg="#FFFFFF", font=("Microsoft YaHei UI", 10))
            combo.pack(side=tk.RIGHT)

        btn_frame = tk.Frame(config_window, bg="#2a2a3e")
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        tk.Button(btn_frame, text="应用", command=lambda: self._apply_fonts(config_window),
                 bg="#4a4a6e", fg="#FFFFFF", font=("Microsoft YaHei UI", 10)).pack(side=tk.RIGHT, padx=5)

        tk.Button(btn_frame, text="重置",
                 command=self._reset_fonts,
                 bg="#6a4a4e", fg="#FFFFFF", font=("Microsoft YaHei UI", 10)).pack(side=tk.RIGHT, padx=5)

    def _apply_fonts(self, window):
        try:
            for key, var in self._font_vars.items():
                family = var.get()
                size = self._fonts[key][1]
                weight = self._fonts[key][2]
                self._fonts[key] = (family, size, weight)

            self.lyric_canvas.delete("all")
            self.trans_label.config(font=self._fonts["trans"])

            self._save_config()
            window.destroy()
        except Exception as e:
            print(f"[UI] 应用字体失败: {e}")

    def _reset_fonts(self):
        self._fonts = self.DEFAULT_FONTS.copy()
        self.lyric_canvas.delete("all")
        self.trans_label.config(font=self._fonts["trans"])
        self._save_config()
        print("[UI] 字体已重置为默认值")

    def update_display(self, current_orig: str, trans_text: str, progress):
        """
        更新显示：卡拉OK逐字高亮效果
        progress: 可以是 float (LRC整体进度) 或 list [(char, progress), ...] (KRC逐字进度)
        """
        try:
            # 更新翻译
            self.trans_label.config(text=trans_text if trans_text else "")

            # 如果歌词变化，重新绘制
            if current_orig != self._current_text:
                self._current_text = current_orig
                # 判断是KRC还是LRC格式
                if isinstance(progress, list):
                    self._draw_karaoke_text_krc(current_orig, progress)
                else:
                    self._draw_karaoke_text_lrc(current_orig, 0)

            # 更新高亮进度
            if isinstance(progress, list):
                self._update_highlight_krc(progress)
            else:
                self._update_highlight_lrc(progress)

        except tk.TclError:
            pass

    def _draw_karaoke_text_lrc(self, text: str, progress: float):
        """绘制LRC格式歌词（整体高亮）"""
        self.lyric_canvas.delete("all")

        if not text:
            return

        canvas_w = self.lyric_canvas.winfo_width()
        canvas_h = self.lyric_canvas.winfo_height()
        font_family, font_size, font_weight = self._fonts["lyric"]

        temp_font = tkfont.Font(family=font_family, size=font_size, weight=font_weight)
        text_width = temp_font.measure(text)

        start_x = max(10, (canvas_w - text_width) // 2)
        y = canvas_h // 2

        # 未播放层
        self.lyric_canvas.create_text(
            start_x, y, text=text,
            font=(font_family, font_size, font_weight),
            fill=self._colors["text_unplayed"],
            anchor="w", tags="unplayed"
        )

        # 已播放层
        self.lyric_canvas.create_text(
            start_x, y, text=text,
            font=(font_family, font_size, font_weight),
            fill=self._colors["text_played"],
            anchor="w", tags="played"
        )

        self._text_start_x = start_x
        self._text_width = text_width
        self._highlight_rect = self.lyric_canvas.create_rectangle(
            start_x, 0, start_x, canvas_h, fill="", outline=""
        )
        self.lyric_canvas.itemconfig("played", clip=self._highlight_rect)

    def _draw_karaoke_text_krc(self, text: str, char_progress: list):
        """绘制KRC格式歌词（逐字高亮）"""
        self.lyric_canvas.delete("all")

        if not text or not char_progress:
            return

        canvas_w = self.lyric_canvas.winfo_width()
        canvas_h = self.lyric_canvas.winfo_height()
        font_family, font_size, font_weight = self._fonts["lyric"]

        temp_font = tkfont.Font(family=font_family, size=font_size, weight=font_weight)

        # 计算每个字的位置
        total_width = 0
        char_positions = []
        for char, _ in char_progress:
            char_w = temp_font.measure(char)
            char_positions.append((char, char_w, total_width))
            total_width += char_w

        start_x = max(10, (canvas_w - total_width) // 2)
        y = canvas_h // 2

        self._krc_chars = []  # 保存每个字的信息用于后续更新

        # 绘制每个字（两层：未播放和已播放）
        for i, (char, char_w, offset_x) in enumerate(char_positions):
            x = start_x + offset_x

            # 未播放层
            self.lyric_canvas.create_text(
                x, y, text=char,
                font=(font_family, font_size, font_weight),
                fill=self._colors["text_unplayed"],
                anchor="w"
            )

            # 已播放层（初始clip宽度为0）
            clip_rect = self.lyric_canvas.create_rectangle(
                x, 0, x, canvas_h, fill="", outline=""
            )
            played_text = self.lyric_canvas.create_text(
                x, y, text=char,
                font=(font_family, font_size, font_weight),
                fill=self._colors["text_played"],
                anchor="w"
            )
            self.lyric_canvas.itemconfig(played_text, clip=clip_rect)

            self._krc_chars.append({
                'x': x,
                'width': char_w,
                'clip_rect': clip_rect,
                'played_text': played_text
            })

    def _update_highlight_lrc(self, progress: float):
        """更新LRC整体高亮进度"""
        if not hasattr(self, '_highlight_rect') or not self._text_width:
            return

        highlight_width = int(self._text_width * progress / 100)
        self.lyric_canvas.coords(
            self._highlight_rect,
            self._text_start_x, 0,
            self._text_start_x + highlight_width, self.lyric_canvas.winfo_height()
        )

    def _update_highlight_krc(self, char_progress: list):
        """更新KRC逐字高亮进度"""
        if not hasattr(self, '_krc_chars') or not self._krc_chars:
            return

        canvas_h = self.lyric_canvas.winfo_height()

        for i, (char_info, (char_text, progress)) in enumerate(zip(self._krc_chars, char_progress)):
            highlight_width = int(char_info['width'] * progress / 100)
            self.lyric_canvas.coords(
                char_info['clip_rect'],
                char_info['x'], 0,
                char_info['x'] + highlight_width, canvas_h
            )

    def run(self):
        self.root.mainloop()


# ============================================================
# 第四部分：主程序
# ============================================================

class KaraokeLyricsApp:
    """主应用：串联媒体信息获取、歌词匹配、UI 显示"""

    def __init__(self, local_lyrics_dir=None):
        self.media = MediaInfoProvider()
        self.lyrics = LyricsManager(local_lyrics_dir)
        self.window = KaraokeLyricsWindow()
        self._last_song = ""
        self._current_lyrics = []
        self._lyrics_loading = False

    def _on_lyrics_loaded(self, lyrics):
        """歌词后台加载完成"""
        def _apply():
            self._current_lyrics = lyrics
            self._lyrics_loading = False
            print(f"[App] 歌词已就绪: {len(lyrics)} 行")
        self.window.root.after(0, _apply)

    def _update_tick(self):
        """定时刷新"""
        try:
            info = self.media.get_info()
            title = info.get("title", "")
            artist = info.get("artist", "")
            position = info.get("position_ms", 0)

            # 歌曲切换
            song_key = f"{artist}|{title}"
            if song_key != self._last_song:
                self._last_song = song_key
                if title:
                    print(f"[App] 歌曲切换: {artist} - {title}")
                    self._current_lyrics = []
                    self._lyrics_loading = True
                    self.lyrics.load_lyrics_async(title, artist, self._on_lyrics_loaded)
                else:
                    self._current_lyrics = []
                    self._lyrics_loading = False

            # 更新 UI
            if title:
                if self._lyrics_loading:
                    self.window.update_display("♪ 正在加载歌词...", "", 0)
                elif self._current_lyrics:
                    orig, trans, progress = self.lyrics.get_current_line(self._current_lyrics, position)
                    self.window.update_display(orig, trans, progress)
                else:
                    self.window.update_display("♪ 暂无歌词 ♪", "", 0)
            else:
                self.window.update_display("♪ 等待播放...", "", 0)

        except Exception as e:
            print(f"[Error] 更新失败: {e}")
            import traceback
            traceback.print_exc()

        self.window.root.after(100, self._update_tick)  # 100ms 更新一次，更流畅

    def run(self):
        print("=" * 50)
        print("  Windows 任务栏歌词显示工具 - 卡拉OK版")
        print("=" * 50)
        print()
        print("  操作说明:")
        print("  - 左键拖拽 → 移动位置")
        print("  - 右键菜单 → 穿透 / 颜色 / 字体 / 退出")
        print("  - 支持 QQ音乐/网易云/Spotify 等主流播放器")
        print()

        self.media.start()
        self.window.root.after(100, self._update_tick)
        try:
            self.window.run()
        finally:
            self.media.stop()


if __name__ == "__main__":
    local_dir = None
    app = KaraokeLyricsApp(local_lyrics_dir=local_dir)
    app.run()
