# 任务栏歌词 & 音频可视化工具

在 Windows 任务栏上方实时显示当前播放歌曲的歌词，支持逐字卡拉 OK 风格的歌词高亮和音频可视化。

![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Windows 10+](https://img.shields.io/badge/Windows-10%2B-0078D6?logo=windows)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

## 功能特性

### 任务栏歌词
- **实时同步** — 通过 Windows GSMTC API 获取精确播放进度，歌词逐字同步
- **多源歌词** — 支持网易云音乐、QQ 音乐 (QRC)、酷狗 (KRC)、Lrclib 四大在线源，自动降级匹配
- **本地歌词** — 支持加载 `.lrc` 文件，本地优先
- **卡拉 OK 渲染** — 像素级逐字高亮，已唱/当前/未唱三色渐变过渡
- **双行模式** — 卡拉 OK 版本支持原文 + 翻译双行显示
- **点击穿透** — 开启后鼠标操作不受歌词窗口影响
- **拖拽定位** — 左键拖动调整窗口位置，右键菜单配置
- **永不抢焦** — 窗口不干扰任务栏正常操作

### 音频可视化
- **实时 FFT 分析** — 将系统音频分为低音 (20-250Hz)、中音 (250-4kHz)、高音 (4-20kHz) 三个频段
- **节拍检测** — 基于能量阈值的自动节拍识别
- **6 种预设调色板** — rainbow / ocean / fire / neon / pastel / gold
- **HSL 颜色映射** — 低音→红橙 / 中音→绿黄 / 高音→蓝紫
- **可配置敏感度** — 自定义过渡速度和各频段阈值

## 截图

### 卡拉 OK 逐字高亮
![Karaoke Lyrics](QQ20260413-222628.png)

### 双行显示模式
![Dual-line Lyrics](QQ20260413-222949.png)

## 快速开始

### 安装依赖

```bash
pip install winsdk pywin32 requests numpy
```

> `tkinter` 是 Python 自带的，无需额外安装。
> `pycaw` 是音频可视化的可选依赖，用于真实音频捕获：
> ```bash
> pip install pycaw
> ```

### 运行

```bash
# 主歌词显示（像素级卡拉 OK 风格）
python taskbar_lyrics.py

# 双行卡拉 OK 版本（原文 + 翻译）
python taskbar_lyrics_karaoke.py

# 音频可视化（FFT 频谱分析 + 动态颜色）
python audio_visualizer.py
```

## 使用方式

| 操作     | 说明                         |
| -------- | ---------------------------- |
| 左键拖拽 | 移动歌词窗口位置             |
| 右键点击 | 弹出菜单（穿透 / 配置 / 退出）|
| 鼠标穿透 | 开启后点击可以穿透到任务栏   |

### 本地歌词

如果你有 `.lrc` 歌词文件，在代码末尾指定目录：

```python
local_dir = r"D:\Music\Lyrics"
```

文件命名格式（任选）：
- `歌手 - 歌名.lrc`
- `歌名 - 歌手.lrc`
- `歌名.lrc`

本地歌词优先级高于在线歌词。

## 架构

### 三层架构

| 层级     | 类                  | 作用                                          |
| -------- | ------------------- | --------------------------------------------- |
| 媒体信息 | `MediaInfoProvider` | 后台线程每 500ms 轮询 GSMTC API 获取歌名/歌手/进度 |
| 歌词管理 | `LyricsManager`     | 从在线 API 或本地 LRC 加载歌词，带缓存           |
| 显示渲染 | `TaskbarLyricsWindow` / `KaraokeLyricsWindow` | Tkinter 透明悬浮窗口，支持拖拽和穿透 |

### 数据流

```
GSMTC API → MediaInfoProvider (500ms轮询) → get_info()
    → _tick() (50ms/100ms刷新) → get_current_line() → Canvas重绘
```

### 歌词源优先级

```
网易云音乐 → Lrclib → QQ 音乐 → 酷狗
```

### 渲染模式对比

| 文件                      | 模式         | 刷新率 | 特点                               |
| ------------------------- | ------------ | ------ | ---------------------------------- |
| `taskbar_lyrics.py`       | 像素级渐变   | 20fps  | 三色渐变（已唱/边界/未唱），20fps    |
| `taskbar_lyrics_karaoke.py` | 双行卡拉 OK | 10fps  | 原文+翻译，支持 KRC 逐字裁剪和 LRC   |

## 歌词格式支持

| 格式 | 来源     | 特点                           |
| ---- | -------- | ------------------------------ |
| LRC  | 通用     | 行级时间戳 + 可选翻译          |
| QRC  | QQ 音乐  | 加密逐字歌词，字符级时间戳      |
| KRC  | 酷狗     | XOR 加密 + zlib 压缩，词级时间戳 |

## 打包成 EXE

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name "TaskbarLyrics" taskbar_lyrics.py
```

打包后双击即可运行，无需 Python 环境。

## 常见问题

**Q: 显示"等待播放"但已经在播放了？**
A: 确保你的播放器支持 Windows 媒体会话。测试方法：按键盘上的播放/暂停键，如果能控制播放器，说明支持。

**Q: 歌词匹配不上？**
A: Lrclib 对英文歌支持较好，中文歌建议下载 LRC 文件放到本地目录，或使用网易云音乐/QQ 音乐源。

**Q: Windows 7 能用吗？**
A: 不能。GSMTC API 需要 Windows 10 1809 (2018年10月更新) 或更高版本。

**Q: 音频可视化没有反应？**
A: 安装 `pycaw` 用于真实音频捕获。未安装时会自动回退到模拟模式。

## 技术栈

- **Python 3.9+** — 核心语言
- **winsdk** — Windows GSMTC API 绑定
- **pywin32** — Windows API 调用（窗口样式、穿透、置顶）
- **requests** — HTTP 歌词获取
- **numpy** — FFT 音频分析
- **pycaw** (可选) — Windows Core Audio API 绑定
- **Tkinter** — GUI 渲染

## 项目结构

```
.
├── taskbar_lyrics.py          # 主歌词显示（像素级卡拉 OK）
├── taskbar_lyrics_karaoke.py  # 双行卡拉 OK 版本
├── audio_visualizer.py        # 音频 FFT 可视化
├── lyrics_api.py              # 多平台歌词提供者（网易/QQ/酷狗/Lrclib）
├── qq-music-api-main/         # QQ 音乐 API（独立 Node.js 服务）
└── README.md
```

## 相关项目

- [qq-music-api](https://github.com/jsososo/QQMusicApi) — QQ 音乐 Node.js API 服务
- [lrclib](https://lrclib.net) — 开放歌词数据库
