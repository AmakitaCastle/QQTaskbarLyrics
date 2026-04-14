# Playback Control Bar Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vertical button layout with a horizontal control bar (prev/play-pause/next buttons + divider + lyrics) in a single rectangular container at 32px height.

**Architecture:** Single `tk.Frame` container with `pack(side=tk.LEFT)` children: button group (86px fixed), divider (1px), lyrics Canvas (flex). Buttons are circular `tk.Canvas` items with hover effects.

**Tech Stack:** Python 3, tkinter, winsdk (GSMTC API)

---

### Task 1: Add playback control to MediaInfoProvider

**Files:**
- Modify: `src/media/provider.py` (entire file, ~67 lines → ~113 lines)

- [ ] **Step 1: Update docstring and add state tracking**

Replace the docstring and `__init__` to add `_state` dict:

```python
"""
媒体信息 Provider — Windows GSMTC API 轮询 + 播放控制
"""

import asyncio
import threading
import time


class MediaInfoProvider:
    def __init__(self):
        self._info = {"title": "", "artist": "", "position_ms": 0, "duration_ms": 0}
        self._lock = threading.Lock()
        self._running = False
        self._update_ts = 0.0
        self._state = {"playing": True}  # track play/pause state
```

- [ ] **Step 2: Keep existing methods unchanged**

`_fetch`, `_poll`, `start`, `stop`, `get_info` — no changes needed.

- [ ] **Step 3: Add control methods at end of class**

After `get_info()`, add:

```python
    # ---- 播放控制 ----

    def _run_control(self, action: str):
        """在临时 event loop 中执行 GSMTC 控制命令"""
        async def _do():
            try:
                from winsdk.windows.media.control import \
                    GlobalSystemMediaTransportControlsSessionManager as SM
                mgr = await SM.request_async()
                s = mgr.get_current_session()
                if not s:
                    return
                if action == "play_pause":
                    await s.try_toggle_play_pause_async()
                elif action == "next":
                    await s.try_skip_next_async()
                elif action == "prev":
                    await s.try_skip_previous_async()
                elif action == "stop":
                    await s.try_stop_async()
            except Exception:
                pass
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_do())
            loop.close()
        except Exception:
            pass

    def play_pause(self):
        self._run_control("play_pause")
        with self._lock:
            self._state["playing"] = not self._state["playing"]

    def next_track(self):
        self._run_control("next")

    def prev_track(self):
        self._run_control("prev")

    def is_playing(self):
        with self._lock:
            return self._state.get("playing", True)
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/media/provider.py','rb').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/media/provider.py
git commit -m "feat: add GSMTC playback control (play_pause, next, prev)"
```

---

### Task 2: Add offset_x to KaraokeEngine

**Files:**
- Modify: `src/display/karaoke.py` (lines 10-29 for `__init__`, lines 77-120 for `_paint`)

- [ ] **Step 1: Add offset_x parameter to `__init__`**

Replace lines 10-29:

```python
class KaraokeEngine:
    """像素级卡拉OK渲染"""

    def __init__(self, canvas: tk.Canvas, colors: dict, fonts: dict, offset_x: int = 0):
        self.canvas = canvas
        self.colors = colors
        self.fonts = fonts
        self.offset_x = offset_x  # 左侧按钮区域占用的宽度

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
```

- [ ] **Step 2: Update `_paint` to use offset_x**

Replace lines 77-119 with:

```python
    def _paint(self, text: str, progress: float):
        """每帧更新：像素级分割 + 边界渐变"""
        if not text or not self._sung_id:
            return

        progress = max(0.0, min(1.0, progress))
        highlight_px = self._total_px * progress
        cw = (self._canvas_w or 860) - self.offset_x  # 减去按钮区宽度
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
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/display/karaoke.py','rb').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/display/karaoke.py
git commit -m "refactor: add offset_x parameter to KaraokeEngine for button area"
```

---

### Task 3: Rewrite window.py layout (container + buttons + divider)

**Files:**
- Modify: `src/display/window.py` (complete rewrite of layout section, ~258 lines → ~320 lines)

This is the largest task. It replaces the two-frame layout with a single container.

- [ ] **Step 1: Update class constants and `__init__` signature**

Replace lines 14-33:

```python
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
```

- [ ] **Step 2: Update height defaults and remove old button state init**

The height is now 32px (already set in DEFAULT_SIZE above). Remove old `btn_frame` references — they don't exist in this version of the file, so skip.

- [ ] **Step 3: Replace Canvas section with container + buttons + divider + canvas**

Replace lines 56-68 (from `# ---- Canvas ----` through `self.karaoke = KaraokeEngine`):

```python
        # ---- 容器：按钮 + 分隔线 + 歌词 ----
        self.container = tk.Frame(self.root, bg=_actual_bg, height=wh)
        self.container.pack(fill=tk.X, expand=False)

        # 左侧控制按钮组
        self.ctrl_group = tk.Frame(self.container, bg=_actual_bg,
                                   width=self.BUTTON_AREA_WIDTH)
        self.ctrl_group.pack(side=tk.LEFT, fill=tk.Y)
        self.ctrl_group.pack_propagate(False)

        self._create_control_buttons(_actual_bg, wh)

        # 分隔线
        div_color = self._colors.get("divider", self.DEFAULT_COLORS["divider"])
        self.divider = tk.Frame(self.container, bg=div_color, width=1)
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
```

- [ ] **Step 4: Update drag binding from canvas to container**

Replace lines 65-67 (old drag binding):

```python
        # 拖拽
        self._drag = {"x": 0, "y": 0}
        self.container.bind("<Button-1>", lambda e: self._drag.update(x=e.x, y=e.y))
        self.container.bind("<B1-Motion>", self._drag_move)
```

- [ ] **Step 5: Remove right-click menu code entirely**

Remove lines 69-78 (the `self.menu = tk.Menu...` through `self._ct = False`):

Delete this block:
```python
        # 右键菜单 — 只保留：穿透、颜色、字体、退出
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="鼠标穿透 开/关 (Ctrl+T)", command=self._toggle_ct)
        self.menu.add_separator()
        self.menu.add_command(label="窗口大小", command=self._size_cfg)
        self.menu.add_command(label="颜色设置", command=self._color_cfg)
        self.menu.add_command(label="字体设置", command=self._font_cfg)
        self.menu.add_separator()
        self.menu.add_command(label="退出 (Esc)", command=self._quit)
        self.root.bind("<Button-3>", self._show_menu)
        self._ct = False
```

- [ ] **Step 6: Remove `_show_menu` method**

Delete lines 89-107 (the entire `_show_menu` method):

```python
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
```

- [ ] **Step 7: Add button creation and interaction methods**

Insert after `_ensure_topmost` (after line 149), before `_drag_move`:

```python
    # ---- 播放控制按钮 ----

    def _create_control_buttons(self, bg_color: str, container_h: int):
        """创建水平排列的 prev / play-pause / next 圆形按钮"""
        btn_size = 26
        btn_fg = "#ccccdd"
        btn_padding = 13  # (26 + 0) / 2 for first, then 0 gap

        # 垂直居中
        start_x = (self.BUTTON_AREA_WIDTH - btn_size * 3) // 2
        start_y = (container_h - btn_size) // 2

        self._btn_prev = self._make_circle_btn(
            "⏮", start_x, start_y, btn_size, btn_fg, self._on_prev
        )
        self._btn_play = self._make_circle_btn(
            "⏸", start_x + btn_size, start_y, btn_size, btn_fg, self._on_play_pause
        )
        self._btn_next = self._make_circle_btn(
            "⏭", start_x + btn_size * 2, start_y, btn_size, btn_fg, self._on_next
        )

    def _make_circle_btn(self, text: str, x: int, y: int, size: int,
                         fg: str, command):
        """创建一个圆形按钮（Canvas + oval + text + hover）"""
        canvas = tk.Canvas(self.ctrl_group, width=size, height=size,
                           bg=self._colors.get("bg", self.DEFAULT_COLORS["bg"]),
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
                               fill="rgba(255,255,255,0.1)", outline="", tags="bg")
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
            icon = "▶" if not self._playing else "⏸"
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
```

- [ ] **Step 8: Update `_toggle_ct` to use XOR toggle**

Replace the `_toggle_ct` method (old line 169-181) with:

```python
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
```

Note: Also need to add `self._ct = False` initialization back in `__init__` since `_toggle_ct` references it. Add it right after `self._callbacks` assignment:

```python
        self._ct = False
```

- [ ] **Step 9: Update `_apply_colors` for new layout**

Replace the `_apply_colors` method (old line 190-202) with:

```python
    def _apply_colors(self):
        """应用颜色配置到窗口"""
        self._TRANSPARENT_MAGIC = "#000001"
        _bg = self._colors.get("bg", self.DEFAULT_COLORS["bg"])
        _actual_bg = self._TRANSPARENT_MAGIC if _bg == "transparent" else _bg
        self.root.configure(bg=_actual_bg)
        self.container.configure(bg=_actual_bg)
        self.ctrl_group.configure(bg=_actual_bg)
        self.canvas.configure(bg=_actual_bg)
        if _bg == "transparent":
            self.root.attributes("-transparentcolor", self._TRANSPARENT_MAGIC)
        else:
            self.root.attributes("-transparentcolor", "")
        self.karaoke._text = ""  # force rebuild
        # 更新分隔线颜色
        div_color = self._colors.get("divider", self.DEFAULT_COLORS["divider"])
        self.divider.configure(bg=div_color)
        self._save_config()
```

- [ ] **Step 10: Update `_size_cfg` for new default height**

In `_size_cfg`, change the Spinbox range for height from `from_=20, to=200` (already correct, min 20 is fine). No changes needed.

- [ ] **Step 11: Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/display/window.py','rb').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 12: Commit**

```bash
git add src/display/window.py
git commit -m "feat: redesign layout as horizontal control bar with circular buttons"
```

---

### Task 4: Wire up playback controls in taskbar_lyrics.py

**Files:**
- Modify: `taskbar_lyrics.py` (lines 20-34 for `__init__`, lines 39-65 for `_tick`, line 72 for log message)

- [ ] **Step 1: Update TaskbarLyricsApp `__init__` to pass callbacks**

Replace lines 20-33:

```python
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
```

- [ ] **Step 2: Add play state sync in `_tick`**

Replace lines 39-65:

```python
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
```

- [ ] **Step 3: Update startup log message**

Replace line 72:

```python
        log("  左键拖拽 | 托盘菜单 | Esc退出 | Ctrl+T穿透")
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "import ast; ast.parse(open('taskbar_lyrics.py','rb').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add taskbar_lyrics.py
git commit -m "feat: wire playback control callbacks to TaskbarLyricsWindow"
```

---

### Task 5: Verify full import chain

**Files:**
- All modified files

- [ ] **Step 1: Verify all modules import cleanly**

Run:
```bash
python -c "
from src.media.provider import MediaInfoProvider
from src.display.karaoke import KaraokeEngine
from src.display.window import TaskbarLyricsWindow
print('All imports OK')
"
```
Expected: `All imports OK`

Note: This may fail at runtime due to tkinter/GSMTC dependencies on Windows, but syntax-level imports should pass.

- [ ] **Step 2: Final commit if all clean**

```bash
git status
```

---

## Summary of changes

| File | Lines changed | Description |
|------|--------------|-------------|
| `src/media/provider.py` | +46 | GSMTC playback control methods |
| `src/display/karaoke.py` | +1 / -1 | `offset_x` parameter |
| `src/display/window.py` | +100 / -50 | Complete layout rewrite |
| `taskbar_lyrics.py` | +10 / -3 | Wire callbacks + state sync |
