# TaskbarLyrics — Windows 任务栏歌词

在 Windows 任务栏上方实时显示当前播放歌曲的歌词，支持像素级逐字卡拉 OK 高亮。

![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Windows 10+](https://img.shields.io/badge/Windows-10%2B-0078D6?logo=windows)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

## 截图

### 卡拉 OK 逐字高亮
![Karaoke Lyrics](QQ20260413-222628.png)

### 双行显示模式
![Dual-line Lyrics](QQ20260413-222949.png)

## 项目背景

macOS 版 QQ 音乐有一个很实用的功能：在菜单栏/触控栏显示实时歌词。
这个项目的目标就是在 **Windows** 上复刻这个体验——在任务栏上方显示歌词，让你边工作边瞥一眼就能看到。

## 功能

- **实时同步** — 通过 Windows GSMTC API 获取精确播放进度，歌词逐帧同步（20fps）
- **QQ 音乐逐字歌词** — 支持 QRC 格式解密，字符级时间戳，官方翻译合并
- **本地歌词** — 支持 `.lrc` 文件，本地优先
- **像素级卡拉 OK** — 三色渐变渲染（已唱/边界插值/未唱），`bisect` 像素定位
- **点击穿透** — 开启后鼠标操作不受歌词窗口影响
- **拖拽定位** — 左键拖动调整位置，窗口坐标自动保存
- **颜色 & 字体配置** — 右键菜单可自定义已唱颜色、未唱颜色、背景色（含透明模式）、字体族/大小/粗体
- **永不抢焦** — `WS_EX_NOACTIVATE` 确保窗口不干扰任务栏正常操作

## 快速开始

### 安装

```bash
pip install winsdk pywin32 requests
```

> `tkinter` 是 Python 自带的，无需额外安装。

### 运行

```bash
python taskbar_lyrics.py
```

### 本地歌词

```python
# taskbar_lyrics.py 末尾
TaskbarLyricsApp(local_dir=r"D:\Music\Lyrics").run()
```

支持命名格式：`歌手 - 歌名.lrc` / `歌名.lrc`

## 使用

| 操作     | 说明                           |
| -------- | ------------------------------ |
| 左键拖拽 | 移动歌词窗口位置               |
| 右键点击 | 弹出菜单（穿透 / 颜色 / 字体 / 退出）|
| 鼠标穿透 | 开启后点击穿透到任务栏         |

## 架构

```
taskbar_lyrics.py          # 入口：TaskbarLyricsApp 组装各模块
└── src/
    ├── media/
    │   └── provider.py    # MediaInfoProvider — 轮询 Windows GSMTC API
    ├── lyrics/
    │   ├── manager.py     # LyricsManager — 缓存 + 加载 + 当前行匹配
    │   ├── parsers.py     # QRC / LRC 格式解析器
    │   ├── cache.py       # 内存 + 磁盘双层缓存
    │   └── providers/
    │       ├── base.py    # BaseLyricsProvider 抽象基类
    │       └── qq.py      # QQMusicProvider — QRC逐字 + 翻译 + 旧接口回退
    ├── display/
    │   ├── window.py      # TaskbarLyricsWindow — 窗口管理、拖拽、菜单、配置
    │   ├── karaoke.py     # KaraokeEngine — 像素级三色渐变渲染
    │   └── config.py      # 配置加载/保存 + 颜色 & 字体 UI 弹窗
    └── utils/
        ├── crypto.py      # QRC TripleDES 解密 + QMC1 回退
        └── log.py         # 日志工具
```

### 数据流

```
GSMTC API → MediaInfoProvider (500ms轮询) → get_info()
    → _tick() (50ms刷新, 20fps) → get_current_line() → KaraokeEngine.update_display()
    → Canvas 重绘 (sung/mid/unsung 三 text item)
```

### 歌词获取链路

```
歌曲切换 → LyricsManager.load_async()
    → 1. 检查内存缓存
    → 2. 检查磁盘缓存
    → 3. 本地 LRC 文件
    → 4. QQ 音乐在线搜索 + 歌词获取
        → GetPlayLyricInfo (QRC逐字 + 翻译)
        → 旧接口回退 (LRC)
    → 写入磁盘缓存 → 回调更新
```

## QRC 歌词解密

QQ 音乐的 QRC 歌词采用三重加密链路：
1. **网络传输层** — Base64 编码
2. **应用层** — TripleDES 云解密 (`_qrc_cloud_decrypt`)
3. **回退** — QMC1 XOR 解密 (`_qmc1_decrypt`)

翻译歌词支持两种格式：
- **QRC 逐字翻译** — 通过时间戳精确匹配
- **LRC 行级翻译** — 按行序号对齐

## 歌词格式

| 格式 | 特点 | 时间精度 |
| ---- | ---- | -------- |
| QRC  | QQ 音乐加密逐字歌词 + 翻译 | 字符级 |
| LRC  | 标准歌词格式 | 行级 |

## 打包成 EXE

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name "TaskbarLyrics" taskbar_lyrics.py
```

## 系统要求

- **Windows 10 1809+** — GSMTC API 需要此版本或更高
- **Python 3.9+** — 需要 `asyncio` 和 `winsdk` 支持
- **支持的播放器** — QQ 音乐、网易云音乐、Spotify 等注册 Windows 媒体会话的播放器

> **测试方法：** 按键盘播放/暂停键，如果能看到系统弹窗并控制播放器，说明 GSMTC 可用。

## 常见问题

**Q: 显示"等待播放"但已经在播放了？**
A: 确认播放器支持 Windows 媒体会话（见上方测试方法）。

**Q: 歌词匹配不上？**
A: QQ 音乐源对中文歌支持最好，建议优先使用。本地 LRC 作为备选。

**Q: 窗口短暂消失？**
A: 失焦时会自动恢复顶层状态，如果仍有问题可重新右键开启/关闭穿透。

## 对比

### 和 macOS QQ 音乐

| | macOS QQ 音乐 | TaskbarLyrics (本工具) |
|---|---|---|
| 平台 | macOS | Windows |
| 显示位置 | 菜单栏 / Touch Bar | 任务栏上方 |
| 播放器支持 | 仅 QQ 音乐 | QQ 音乐、网易云、Spotify 等 |
| 逐字卡拉 OK | 支持 | 支持（QRC 解密） |
| 翻译 | 支持 | 支持 |
| 自定义 | 有限 | 颜色/字体可配置 |

### 和 Windows QQ 音乐

| | Windows QQ 音乐桌面歌词 | TaskbarLyrics (本工具) |
|---|---|---|
| 显示位置 | 桌面大区域 | 任务栏上方（窄条） |
| 播放器依赖 | 仅限 QQ 音乐客户端 | 任意 GSMTC 支持的播放器 |
| 体积 | 完整客户端 | 几 MB |
| 广告/推广 | 有 | 无 |
| 开机占用 | 需启动完整客户端 | 极低 |

**这不是"替代"关系，而是互补：**
- Windows QQ 音乐的桌面歌词 = KTV 模式，全屏展示
- TaskbarLyrics = 余光模式，任务栏一条，不挡工作区

## 相关项目

### 核心依赖

- [winsdk](https://pypi.org/project/winsdk/) — Python 绑定 Windows Runtime API（GSMTC 媒体控制）
- [pywin32](https://github.com/mhammond/pywin32) — Windows API 调用（窗口样式、穿透、置顶）

### 歌词数据源

- [QQMusicApi](https://github.com/jsososo/QQMusicApi) — QQ 音乐 Node.js API 服务（搜索、歌词、播放链接）
- [LRCLIB](https://lrclib.net) — 开放歌词数据库，多语言 LRC 歌词
- [LDDC](https://github.com/chenmozhijin/LDDC) — 桌面歌词显示控制器
- [QRCD](https://github.com/xmcp/QRCD) — QRC 歌词解码器

### 类似项目

- [Lyricify](https://github.com/steve-xmh/Lyricify) — Windows 桌面歌词工具，支持多音乐平台
- [DesktopLyric](https://github.com/jitwxs/DesktopLyric) — 仿网易云音乐的桌面歌词
- [Lyric-Show](https://github.com/qier222/Lyric-Show) — 直播用歌词滚动展示

### 技术参考

- [Windows GSMTC API](https://learn.microsoft.com/windows/uwp/audio-video-camera/global-system-media-transport-controls) — 系统级媒体传输控制 API
- [QRC 格式规范](https://github.com/lyrically/lyrically/wiki/QRC-Lyrics-Format) — QQ 音乐逐字歌词格式解析

## 许可证

MIT
