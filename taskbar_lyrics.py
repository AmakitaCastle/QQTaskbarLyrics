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

# 日志同时输出到文件和控制台（解决后台线程 print 丢失问题）
import os, threading, datetime
_log_lock = threading.Lock()
_log_file = None

def _init_log():
    global _log_file
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'taskbar_lyrics.log')
    _log_file = open(path, 'w', encoding='utf-8')
    # 同时初始化 lyrics_api 的日志
    try:
        from lyrics_api import _init_lyrics_log
        _init_lyrics_log()
    except: pass

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
    line = f"[{ts}] {msg}"
    # 终端输出
    try: print(line, flush=True)
    except: pass
    # 文件输出
    with _log_lock:
        if _log_file:
            try:
                _log_file.write(line + '\n')
                _log_file.flush()
            except: pass

import asyncio, ctypes, json, re, threading, time, bisect
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path

# ============================================================
# GSMTC 媒体信息（带时间插值）
# ============================================================

class MediaInfoProvider:
    def __init__(self):
        self._info = {"title":"","artist":"","position_ms":0,"duration_ms":0}
        self._lock = threading.Lock()
        self._running = False
        self._update_ts = 0.0

    async def _fetch(self):
        try:
            from winsdk.windows.media.control import \
                GlobalSystemMediaTransportControlsSessionManager as SM
            mgr = await SM.request_async()
            s = mgr.get_current_session()
            if not s: return None
            p = await s.try_get_media_properties_async()
            tl = s.get_timeline_properties()
            return {"title":p.title or "","artist":p.artist or "",
                    "album":getattr(p, 'album_title', '') or "",
                    "position_ms":int(tl.position.total_seconds()*1000),
                    "duration_ms":int(tl.end_time.total_seconds()*1000)}
        except: return None

    def _poll(self):
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        fails = 0
        while self._running:
            r = loop.run_until_complete(self._fetch())
            if r:
                with self._lock: self._info = r; self._update_ts = time.time()
                fails = 0
            else:
                fails += 1
                if fails >= 10:
                    with self._lock:
                        self._info = {"title":"","artist":"","position_ms":0,"duration_ms":0}
                    fails = 0
            time.sleep(0.5)

    def start(self):
        self._running = True
        threading.Thread(target=self._poll, daemon=True).start()
    def stop(self): self._running = False

    def get_info(self):
        with self._lock:
            info = self._info.copy(); ts = self._update_ts
        # 在两次 GSMTC 轮询之间插值，让进度更丝滑
        if info["title"] and ts > 0:
            info["position_ms"] = int(info["position_ms"] + (time.time()-ts)*1000)
        return info

# ============================================================
# 歌词管理
# ============================================================

class LyricsManager:
    def __init__(self, local_dir=None):
        self.local_dir = Path(local_dir) if local_dir else None
        self._cache = {}; self._loading_key = ""

    def _parse_lrc(self, text):
        lines = []
        for line in text.splitlines():
            m = re.match(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)', line.strip())
            if m:
                mn,sc,cs,tx = m.groups()
                ms = int(cs)*(10 if len(cs)==2 else 1)
                t = int(mn)*60000+int(sc)*1000+ms
                if tx.strip(): lines.append((t, tx.strip()))
        lines.sort(key=lambda x: x[0]); return lines

    def _try_local(self, title, artist):
        if not self.local_dir or not self.local_dir.exists(): return None
        ct = re.sub(r'\s*[（(][^)）]*[)）]','',title).strip()
        ca = re.sub(r'\s*[（(][^)）]*[)）]','',artist).strip()
        for n in [f"{artist} - {title}.lrc",f"{title}.lrc",f"{ca} - {ct}.lrc",f"{ct}.lrc"]:
            p = self.local_dir / n
            if p.exists():
                try: return [(t,x,"",[]) for t,x in self._parse_lrc(p.read_text(encoding="utf-8"))]
                except: pass
        return None

    @staticmethod
    def _variants(title, artist):
        vs = []; parens = lambda t: re.findall(r'[（(]([^)）]+)[)）]',t)
        strip = lambda t: re.sub(r'\s*[（(][^)）]*[)）]','',t).strip()
        ct,ca = strip(title),strip(artist)
        vs.append((title,artist))
        if ct: vs+=[(ct,ca),(ct,"")]
        for a in parens(artist): vs.append((ct,a))
        for t in parens(title):
            if any(k in t.lower() for k in ["live","ver","remix","inst","cover"]): continue
            vs.append((t,ca))
        seen=set()
        return [(t,a) for t,a in vs if t.strip() and (t.strip(),a.strip()) not in seen
                and not seen.add((t.strip(),a.strip()))]

    def _fetch_online(self, title, artist, album=""):
        """使用 LDDC 歌词 API 获取歌词"""
        try:
            from lyrics_api import LyricsProvider
            provider = LyricsProvider()

            lyrics = provider.get_lyrics(title, artist, album)
            if lyrics:
                result = []
                for item in lyrics:
                    if len(item) >= 4:
                        # 格式: (time_ms, text, translation, word_timings)
                        time_ms, text, trans, word_timings = item
                        result.append((time_ms, text, trans, word_timings))
                    elif len(item) == 3:
                        # 格式: (time_ms, text, word_timings) — 纯逐字无翻译
                        result.append((item[0], item[1], "", item[2]))
                    else:
                        result.append((item[0], item[1], "", []))
                return result

            return None
        except Exception as e:
            log(f"    [LDDC API] 失败: {e}")
            return None

    def load_async(self, title, artist, cb, album=""):
        key=f"{artist}|{title}"
        if key in self._cache: cb(self._cache[key]); return
        if self._loading_key==key: return
        self._loading_key=key
        def w():
            log(f"\n[Lyrics] {artist} - {title}" + (f" ({album})" if album else ""))
            ly=self._try_local(title,artist) or self._fetch_online(title,artist,album) or []
            self._cache[key]=ly; self._loading_key=""
            log(f"[Lyrics] {len(ly)} 行"); cb(ly)
        threading.Thread(target=w,daemon=True).start()

    def get_current_line(self, lyrics, position_ms):
        """返回 (原文, 翻译, progress 0.0~1.0)
        如果有逐字时间(word_timings)，用逐字精度计算 progress。
        否则退化为行间插值。
        """
        if not lyrics: return ("♪ 暂无歌词 ♪","",0.0)
        idx=-1
        for i,item in enumerate(lyrics):
            if item[0]<=position_ms: idx=i
            else: break
        if idx<0: return (lyrics[0][1], lyrics[0][2] if len(lyrics[0])>2 else "", 0.0)
        item = lyrics[idx]
        orig = item[1]
        trans = item[2] if len(item)>2 else ""
        # 检查是否有逐字时间戳 (word_timings 在第4个元素，索引3)
        word_timings = item[3] if len(item)>3 else []
        if word_timings:
            # 用逐字时间计算 progress
            line_start = item[0]  # 行起始时间(毫秒)
            # word_timings: [(char_offset_ms, char_duration_ms, char), ...]
            abs_position = position_ms - line_start  # 在当前行内的绝对位置
            if abs_position < 0:
                progress = 0.0
            else:
                # 计算已经唱了多少个字符的总时长
                elapsed_chars = 0
                total_chars = len(word_timings)
                for char_offset, char_dur, _ in word_timings:
                    char_end = char_offset + char_dur
                    if abs_position >= char_end:
                        elapsed_chars += 1
                    elif abs_position > char_offset:
                        # 在当前字符内
                        elapsed_chars += (abs_position - char_offset) / char_dur
                        break
                    else:
                        break
                progress = elapsed_chars / total_chars if total_chars > 0 else 0.0
            progress = max(0.0, min(1.0, progress))
        else:
            # 退化为行间插值
            t0=lyrics[idx][0]; t1=lyrics[idx+1][0] if idx+1<len(lyrics) else t0+5000
            d=t1-t0; progress=max(0.0,min(1.0,(position_ms-t0)/d)) if d>0 else 1.0
        return (orig,trans,progress)


# ============================================================
# 卡拉OK窗口 — 像素级丝滑高亮
# ============================================================

class TaskbarLyricsWindow:
    CONFIG_FILE = Path.home() / ".taskbar_lyrics_config.json"
    DEFAULT_COLORS = {"bg":"#1a1a2e","sung":"#FFD700","unsung":"#555566"}
    DEFAULT_FONTS = {"lyric":("Microsoft YaHei UI",14,"bold")}

    def __init__(self):
        try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except:
            try: ctypes.windll.user32.SetProcessDPIAware()
            except: pass

        self.root = tk.Tk(); self.root.title("TaskbarLyrics")
        self._config = self._load_config()
        self._colors = self._config.get("colors", self.DEFAULT_COLORS.copy())
        self._fonts = self._config.get("fonts", self.DEFAULT_FONTS.copy())

        sw,sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        ww,wh = min(900,sw-200), 42
        pos=self._config.get("position",{})
        x=max(0,min(pos.get("x",(sw-ww)//2),sw-ww))
        y=max(0,min(pos.get("y",sh-wh-50),sh-wh))
        self.root.geometry(f"{ww}x{wh}+{x}+{y}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost",True)
        self.root.attributes("-alpha",1.0)
        self.root.configure(bg=self._colors["bg"])
        self.root.after(100, self._setup_style)
        self.root.after(500, self._ensure_topmost)

        # ---- Canvas ----
        self.canvas = tk.Canvas(self.root, bg=self._colors["bg"],
            height=wh, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=12)

        # 卡拉OK状态
        self._text = ""              # 当前歌词文本
        self._sung_id = None         # 已唱文字 (亮色)
        self._mid_id = None          # 边界字符 (渐变色)
        self._unsung_id = None       # 未唱文字 (暗色)
        self._font_obj = None        # tkfont.Font 用于测量
        self._cum_widths = []        # 每个字符的累计像素宽度
        self._total_px = 0           # 文本总宽度
        self._canvas_w = 0
        self._last_split = -1        # 上次 split 位置
        self._last_mid_color = ""    # 上次边界色

        self.canvas.bind("<Configure>", lambda e: setattr(self,'_canvas_w',e.width))

        # 拖拽
        self._drag={"x":0,"y":0}
        self.canvas.bind("<Button-1>", lambda e: self._drag.update(x=e.x,y=e.y))
        self.canvas.bind("<B1-Motion>", self._drag_move)
        # 右键菜单
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="鼠标穿透 开/关", command=self._toggle_ct)
        self.menu.add_separator()
        self.menu.add_command(label="调试信息 开/关", command=self._toggle_debug)
        self.menu.add_command(label="歌词偏移 设置", command=self._offset_cfg)
        self.menu.add_command(label="颜色设置", command=self._color_cfg)
        self.menu.add_command(label="字体设置", command=self._font_cfg)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self._quit)
        self.root.bind("<Button-3>", lambda e: self.menu.post(e.x_root,e.y_root))
        self._ct=False
        self._debug_mode = False
        self._debug_label = None
        self._lyric_offset_ms = self._config.get("lyric_offset_ms", 200)  # 默认 200ms 偏移
        # 键盘快捷键调整偏移
        self.root.bind("<Up>", lambda e: self._nudge_offset(50))
        self.root.bind("<Down>", lambda e: self._nudge_offset(-50))
        self.root.bind("<Shift-Up>", lambda e: self._nudge_offset(10))
        self.root.bind("<Shift-Down>", lambda e: self._nudge_offset(-10))
        self.root.bind("<Configure>",self._on_move)
        # 焦点丢失时强制恢复最顶层，防止切到其他软件时窗口消失
        self.root.bind("<FocusOut>",lambda e:self._restore_topmost())

    # ---- 窗口保护 ----
    def _hwnd(self):
        try:
            h=ctypes.windll.user32.FindWindowW(None,"TaskbarLyrics")
            return h or self.root.winfo_id()
        except: return None

    def _setup_style(self):
        try:
            h=self._hwnd()
            if not h: return
            s=ctypes.windll.user32.GetWindowLongW(h,-20)
            s|=0x08000000|0x00000080
            ctypes.windll.user32.SetWindowLongW(h,-20,s)
            ctypes.windll.user32.SetWindowPos(h,-1,0,0,0,0,0x0001|0x0002|0x0010|0x0040)
        except: pass

    def _restore_topmost(self):
        """失焦时立即恢复最顶层，防止窗口短暂消失"""
        try:
            h = self._hwnd()
            if h:
                ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0,
                    0x0001 | 0x0002 | 0x0010 | 0x0040)
                self.root.attributes("-topmost", True)
        except: pass

    def _ensure_topmost(self):
        try:
            h=self._hwnd()
            if h:
                ctypes.windll.user32.SetWindowPos(h,-1,0,0,0,0,0x0001|0x0002|0x0010)
                self.root.attributes("-topmost",True)
        except: pass
        self.root.after(500, self._ensure_topmost)

    def _drag_move(self, e):
        self.root.geometry(f"+{self.root.winfo_x()+e.x-self._drag['x']}+"
                           f"{self.root.winfo_y()+e.y-self._drag['y']}")

    def _on_move(self, e):
        if e.widget==self.root:
            if hasattr(self,'_sid'): self.root.after_cancel(self._sid)
            self._sid=self.root.after(500, self._save_pos)

    def _save_pos(self):
        try:
            self._config["position"]={"x":self.root.winfo_x(),"y":self.root.winfo_y()}
            self._save_config()
        except: pass

    def _toggle_ct(self):
        self._ct=not self._ct
        try:
            h=self._hwnd()
            if h:
                s=ctypes.windll.user32.GetWindowLongW(h,-20)
                if self._ct: s|=0x20
                else: s&=~0x20
                ctypes.windll.user32.SetWindowLongW(h,-20,s)
        except: pass

    def _toggle_debug(self):
        self._debug_mode = not self._debug_mode
        if self._debug_mode:
            if not self._debug_label:
                self._debug_label = self.canvas.create_text(
                    10, 4, text="", fill="#00ff00",
                    font=("Consolas", 9), anchor="nw")
        else:
            if self._debug_label:
                self.canvas.delete(self._debug_label)
                self._debug_label = None

    def update_debug_info(self, pos_raw, pos_adj, line_text, progress):
        if self._debug_mode and self._debug_label:
            self.canvas.itemconfig(self._debug_label,
                text=f"pos={pos_raw}ms adj={pos_adj}ms offset={self._lyric_offset_ms}ms p={progress:.0%}")

    def _nudge_offset(self, delta):
        self._lyric_offset_ms += delta
        self._config["lyric_offset_ms"] = self._lyric_offset_ms
        self._save_config()
        log(f"[Offset] {self._lyric_offset_ms}ms ({'+' if delta>0 else ''}{delta})")

    def _quit(self): self.root.quit(); self.root.destroy()

    def _offset_cfg(self):
        """设置歌词时间偏移"""
        def save():
            try:
                v = int(entry.get())
                self._lyric_offset_ms = v
                self._config["lyric_offset_ms"] = v
                self._save_config()
                top.destroy()
            except ValueError:
                pass
        top = tk.Toplevel(self.root)
        top.title("歌词偏移")
        top.geometry("250x100")
        top.transient(self.root)
        top.grab_set()
        tk.Label(top, text="偏移量 (毫秒):").pack(pady=5)
        entry = tk.Entry(top)
        entry.insert(0, str(self._lyric_offset_ms))
        entry.pack(pady=5)
        entry.select_range(0, tk.END)
        entry.focus()
        tk.Button(top, text="确定", command=save).pack(pady=5)
        entry.bind("<Return>", lambda e: save())

    # ===========================================================
    # 核心：像素级卡拉OK
    #
    # 原理：
    #   3 个 Canvas text item：
    #     sung_id   — 已唱部分，亮色（如金色）
    #     mid_id    — 边界字符，颜色从暗渐变到亮（消除硬边）
    #     unsung_id — 未唱部分，暗色
    #
    #   每帧根据 progress 计算像素级分割点，
    #   边界字符用线性插值色，让高亮"擦过"每个字符。
    # ===========================================================

    def update_display(self, orig: str, trans: str, progress: float):
        display = trans if trans else (orig or "♪ 等待播放 ♪")

        if display != self._text:
            self._text = display
            self._last_split = -1
            self._last_mid_color = ""
            self._rebuild(display)

        self._paint(display, progress)

    def _rebuild(self, text):
        """文本变化时：重建 Canvas 元素 + 预计算字符宽度"""
        self.canvas.delete("all")
        self._sung_id = self._mid_id = self._unsung_id = None

        if not text: return

        ft = self._fonts.get("lyric", self.DEFAULT_FONTS["lyric"])
        if isinstance(ft, list): ft = tuple(ft)
        self._font_obj = tkfont.Font(family=ft[0], size=ft[1],
            weight=ft[2] if len(ft)>2 else "normal")

        # 预计算每个字符的累计宽度（像素级精度的关键）
        cum = [0]
        for ch in text:
            cum.append(cum[-1] + self._font_obj.measure(ch))
        self._cum_widths = cum
        self._total_px = cum[-1]

        cy = 21  # 垂直居中
        col_sung = self._colors.get("sung","#FFD700")
        col_unsung = self._colors.get("unsung","#555566")

        self._sung_id = self.canvas.create_text(0, cy, text="",
            fill=col_sung, font=ft, anchor="w")
        self._mid_id = self.canvas.create_text(0, cy, text="",
            fill=col_unsung, font=ft, anchor="w")
        self._unsung_id = self.canvas.create_text(0, cy, text=text,
            fill=col_unsung, font=ft, anchor="w")

    def _paint(self, text, progress):
        """每帧更新：像素级分割 + 边界渐变"""
        if not text or not self._sung_id: return

        progress = max(0.0, min(1.0, progress))
        highlight_px = self._total_px * progress
        cw = self._canvas_w or 860
        cum = self._cum_widths
        n = len(text)

        # 用二分查找定位分割字符（O(log n)）
        # split_idx: 第一个还未完全唱过的字符
        split_idx = bisect.bisect_right(cum, highlight_px) - 1
        split_idx = max(0, min(split_idx, n - 1))

        # 边界字符内部进度（0.0=刚开始擦过，1.0=完全唱过）
        ch_start = cum[split_idx]
        ch_end = cum[split_idx + 1] if split_idx < n else ch_start
        ch_w = ch_end - ch_start
        char_t = (highlight_px - ch_start) / ch_w if ch_w > 0 else 1.0
        char_t = max(0.0, min(1.0, char_t))

        # 插值边界颜色
        col_sung = self._colors.get("sung", "#FFD700")
        col_unsung = self._colors.get("unsung", "#555566")
        mid_color = self._lerp_color(col_unsung, col_sung, char_t)

        # 如果分割点和颜色都没变，跳过重绘
        if split_idx == self._last_split and mid_color == self._last_mid_color:
            return
        self._last_split = split_idx
        self._last_mid_color = mid_color

        # 拆分文本
        sung_part = text[:split_idx]
        mid_char = text[split_idx] if split_idx < n else ""
        unsung_part = text[split_idx + 1:] if split_idx + 1 < n else ""

        # 像素坐标
        sung_px = cum[split_idx]
        mid_px = ch_w

        # 自动跟随：文本过长时，视口跟随高亮位置
        if self._total_px <= cw:
            x0 = (cw - self._total_px) / 2  # 居中
        else:
            target = cw * 0.4
            x0 = target - highlight_px
            x0 = max(cw - self._total_px - 10, x0)
            x0 = min(10, x0)

        cy = 21

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
    def _lerp_color(c1, c2, t):
        """线性插值两个 hex 颜色，t=0 返回 c1，t=1 返回 c2"""
        def norm_color(c):
            """将颜色规范化为 #RRGGBB 格式"""
            if not c or not isinstance(c, str) or not c.startswith('#'):
                return None
            if len(c) == 7:
                return c
            if len(c) == 4:
                # #RGB → #RRGGBB
                return f"#{c[1]*2}{c[2]*2}{c[3]*2}"
            return None

        c1n = norm_color(c1)
        if c1n is None: c1n = "#FFD700"
        c2n = norm_color(c2)
        if c2n is None: c2n = "#555566"

        r1,g1,b1 = int(c1n[1:3],16), int(c1n[3:5],16), int(c1n[5:7],16)
        r2,g2,b2 = int(c2n[1:3],16), int(c2n[3:5],16), int(c2n[5:7],16)
        r = int(r1 + (r2-r1)*t)
        g = int(g1 + (g2-g1)*t)
        b = int(b1 + (b2-b1)*t)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ---- 配置 ----
    def _load_config(self):
        try:
            if self.CONFIG_FILE.exists():
                return json.load(open(self.CONFIG_FILE,"r",encoding="utf-8"))
        except: pass
        return {}

    def _save_config(self):
        try:
            self._config["colors"]=self._colors; self._config["fonts"]=self._fonts
            self._config["lyric_offset_ms"]=self._lyric_offset_ms
            json.dump(self._config,open(self.CONFIG_FILE,"w",encoding="utf-8"),
                      ensure_ascii=False,indent=2)
        except: pass

    def _offset_cfg(self):
        win=tk.Toplevel(self.root); win.title("歌词偏移"); win.geometry("360x140")
        win.configure(bg="#2a2a3e"); win.transient(self.root); win.grab_set()
        f=tk.Frame(win,bg="#2a2a3e"); f.pack(fill=tk.X,padx=20,pady=12)
        tk.Label(f,text="偏移(ms)",fg="#FFF",bg="#2a2a3e",
                 font=("Microsoft YaHei UI",10)).pack(side=tk.LEFT)
        vs=tk.IntVar(value=self._lyric_offset_ms)
        tk.Spinbox(f,from_=-2000,to=2000,textvariable=vs,width=6,
                   font=("Consolas",11)).pack(side=tk.LEFT,padx=8)
        tk.Label(f,text="(正数=歌词提前，负数=歌词推后)",fg="#aaa",bg="#2a2a3e",
                 font=("Microsoft YaHei UI",9)).pack(side=tk.LEFT,padx=4)
        bf=tk.Frame(win,bg="#2a2a3e"); bf.pack(fill=tk.X,padx=20,pady=10)
        def apply():
            self._lyric_offset_ms=vs.get(); self._save_config(); win.destroy()
        tk.Button(bf,text="应用",command=apply,bg="#4a4a6e",fg="#FFF",
                  width=10).pack(side=tk.LEFT)
        tk.Button(bf,text="关闭",command=win.destroy,bg="#6a4a4e",fg="#FFF",
                  width=10).pack(side=tk.RIGHT)

    def _color_cfg(self):
        win=tk.Toplevel(self.root); win.title("颜色"); win.geometry("380x280")
        win.configure(bg="#2a2a3e"); win.transient(self.root); win.grab_set()
        self._cv={}
        for lb,k in [("背景色","bg"),("已唱(高亮)","sung"),("未唱(暗色)","unsung")]:
            f=tk.Frame(win,bg="#2a2a3e"); f.pack(fill=tk.X,padx=20,pady=6)
            tk.Label(f,text=lb,fg="#FFF",bg="#2a2a3e",font=("Microsoft YaHei UI",10)).pack(side=tk.LEFT)
            v=tk.StringVar(value=self._colors.get(k,"#666")); self._cv[k]=v
            tk.Entry(f,textvariable=v,width=9,font=("Consolas",11)).pack(side=tk.LEFT,padx=8)
            pv=tk.Label(f,text="  ",bg=self._colors.get(k,"#666"),width=3,relief=tk.RIDGE)
            pv.pack(side=tk.LEFT)
            v.trace_add("write",lambda*a,p=pv,vv=v:(p.config(bg=vv.get()) if True else None) or None)
        bf=tk.Frame(win,bg="#2a2a3e"); bf.pack(fill=tk.X,padx=20,pady=12)
        def apply():
            for k,v in self._cv.items(): self._colors[k]=v.get()
            self.root.configure(bg=self._colors["bg"])
            self.canvas.configure(bg=self._colors["bg"])
            self._text=""; self._save_config(); win.destroy()
        tk.Button(bf,text="应用",command=apply,bg="#4a4a6e",fg="#FFF",width=10).pack(side=tk.LEFT)
        tk.Button(bf,text="关闭",command=win.destroy,bg="#6a4a4e",fg="#FFF",width=10).pack(side=tk.RIGHT)

    def _font_cfg(self):
        win=tk.Toplevel(self.root); win.title("字体"); win.geometry("420x160")
        win.configure(bg="#2a2a3e"); win.transient(self.root); win.grab_set()
        FONTS=["Microsoft YaHei UI","微软雅黑","SimHei","黑体","Consolas","Segoe UI","Arial"]
        try: af=FONTS+[f for f in tkfont.families() if f not in FONTS]
        except: af=FONTS
        cur=self._fonts.get("lyric",self.DEFAULT_FONTS["lyric"])
        if isinstance(cur,list): cur=tuple(cur)
        f=tk.Frame(win,bg="#2a2a3e"); f.pack(fill=tk.X,padx=20,pady=10)
        vf=tk.StringVar(value=cur[0]); vs=tk.IntVar(value=cur[1])
        vb=tk.BooleanVar(value=len(cur)>2 and cur[2]=="bold")
        tk.Label(f,text="字体",fg="#FFF",bg="#2a2a3e").pack(side=tk.LEFT)
        om=tk.OptionMenu(f,vf,*af); om.config(width=14,bg="#4a4a6e",fg="#FFF"); om.pack(side=tk.LEFT,padx=5)
        tk.Spinbox(f,from_=8,to=36,textvariable=vs,width=4).pack(side=tk.LEFT,padx=5)
        tk.Checkbutton(f,text="粗",variable=vb,bg="#2a2a3e",fg="#FFF",selectcolor="#4a4a6e").pack(side=tk.LEFT)
        bf=tk.Frame(win,bg="#2a2a3e"); bf.pack(fill=tk.X,padx=20,pady=10)
        def apply():
            self._fonts["lyric"]=(vf.get(),vs.get(),"bold" if vb.get() else "normal")
            self._text=""; self._save_config(); win.destroy()
        tk.Button(bf,text="应用",command=apply,bg="#4a4a6e",fg="#FFF",width=10).pack(side=tk.LEFT)
        tk.Button(bf,text="关闭",command=win.destroy,bg="#6a4a4e",fg="#FFF",width=10).pack(side=tk.RIGHT)

    def run(self): self.root.mainloop()


# ============================================================
# 主程序
# ============================================================

class TaskbarLyricsApp:
    def __init__(self, local_dir=None):
        self.media = MediaInfoProvider()
        self.lyrics = LyricsManager(local_dir)
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