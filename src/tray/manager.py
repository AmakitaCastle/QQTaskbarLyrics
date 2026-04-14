"""
系统托盘模块 — 集成现有菜单能力到托盘图标
使用 pystray 库，在后台线程运行托盘，tkinter 保持主线程
"""

import threading
from PIL import Image, ImageDraw

try:
    import pystray
except ImportError:
    pystray = None


def _make_icon():
    """生成托盘图标 — 金色音符 on 深色圆角矩形"""
    size = 128
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 圆角矩形背景
    draw.rounded_rectangle([8, 8, size - 8, size - 8], radius=24, fill=(42, 42, 62, 255))
    cx, cy = size // 2, size // 2
    # 音符 — 八分音符
    gold = (255, 215, 0, 255)
    # 左符头 (椭圆)
    draw.ellipse([cx - 30, cy + 8, cx, cy + 36], fill=gold)
    # 右符头 (椭圆)
    draw.ellipse([cx + 4, cy - 4, cx + 34, cy + 24], fill=gold)
    # 左符干
    draw.rectangle([cx - 24, cy - 16, cx - 16, cy + 14], fill=gold)
    # 右符干
    draw.rectangle([cx + 10, cy - 28, cx + 18, cy + 2], fill=gold)
    # 符尾连线
    draw.polygon([(cx - 24, cy - 16), (cx + 18, cy - 28), (cx + 18, cy - 20), (cx - 24, cy - 8)], fill=gold)
    return img


class TrayManager:
    def __init__(self, root, window, lyrics_manager=None):
        """
        root: tkinter.Tk
        window: TaskbarLyricsWindow
        lyrics_manager: LyricsManager 实例（用于清除缓存）
        """
        self.root = root
        self.window = window
        self.lyrics_manager = lyrics_manager
        self._icon = None
        self._thread = None
        self._visible = True
        self._available = pystray is not None

    def _build_menu(self):
        """构建托盘菜单项"""
        items = [
            pystray.MenuItem(
                "显示 / 隐藏",
                self._toggle_window,
                default=True,
            ),
            pystray.MenuItem(
                "鼠标穿透 开/关",
                lambda: self._invoke(self.window._toggle_ct),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "窗口大小",
                lambda: self._invoke(self.window._size_cfg),
            ),
            pystray.MenuItem(
                "颜色设置",
                lambda: self._invoke(self.window._color_cfg),
            ),
            pystray.MenuItem(
                "字体设置",
                lambda: self._invoke(self.window._font_cfg),
            ),
            pystray.MenuItem(
                "清除缓存",
                lambda: self._invoke(self._clear_cache),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "退出",
                self._quit,
            ),
        ]
        return items

    def start(self):
        """启动系统托盘"""
        if not self._available:
            return

        icon = pystray.Icon(
            "taskbar_lyrics",
            _make_icon(),
            "Taskbar Lyrics — 双击显示/隐藏",
            self._build_menu(),
        )
        # 双击托盘图标切换窗口
        icon.default_action = self._toggle_window

        self._thread = threading.Thread(target=icon.run, daemon=True)
        self._thread.start()
        self._icon = icon

    def stop(self):
        """停止系统托盘"""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._thread = None
            self._icon = None

    def hide_window(self):
        """隐藏窗口到托盘"""
        self._visible = False
        self._invoke(lambda: self.root.withdraw())

    def show_window(self):
        """从托盘显示窗口"""
        self._visible = True
        self._invoke(lambda: self.root.deiconify())

    def _toggle_window(self):
        """切换窗口可见性"""
        if self._visible:
            self.hide_window()
        else:
            self.show_window()

    def _clear_cache(self):
        """清除歌词缓存"""
        if self.lyrics_manager:
            self.lyrics_manager.clear_cache()

    def _invoke(self, fn):
        """安全地在 tkinter 主线程中调用函数"""
        try:
            self.root.after(0, fn)
        except Exception:
            pass

    def _quit(self):
        """退出应用"""
        def _do_quit():
            if self._icon:
                try:
                    self._icon.stop()
                except Exception:
                    pass
            self.window._quit()
        _do_quit()
