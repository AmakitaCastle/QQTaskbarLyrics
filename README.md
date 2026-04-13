# Windows 任务栏歌词显示工具

在 Windows 任务栏上方显示当前播放歌曲的实时滚动歌词，支持 QQ音乐、网易云音乐、Spotify 等主流播放器。

## 原理（无需 OCR）

```
QQ音乐/网易云 → Windows GSMTC API → 获取歌名+歌手+进度
                                         ↓
lrclib.net / 本地LRC文件 ← 匹配歌词 ← 歌名+歌手
                                         ↓
                              透明悬浮窗显示在任务栏上方
```

**GSMTC (Global System Media Transport Controls)** 是 Windows 10 1809+ 的系统级 API。
当你按键盘上的媒体键（播放/暂停）时看到的那个弹窗，背后就是这个 API。
QQ音乐等播放器会主动向系统上报：歌名、歌手、专辑、播放进度等信息。

## 安装

### 1. 安装 Python 3.9+

从 https://python.org 下载安装，勾选 "Add Python to PATH"。

### 2. 安装依赖

```bash
pip install winsdk pywin32 requests
```

> `tkinter` 是 Python 自带的，无需额外安装。

### 3. 运行

```bash
python taskbar_lyrics.py
```

## 使用

| 操作           | 说明                       |
| -------------- | -------------------------- |
| **左键拖拽**   | 移动歌词窗口位置           |
| **右键点击**   | 弹出菜单（穿透/退出）      |
| **鼠标穿透**   | 开启后点击可以穿透到任务栏 |

## 本地歌词

如果你有 `.lrc` 歌词文件，可以在代码末尾指定目录：

```python
local_dir = r"D:\Music\Lyrics"
```

文件命名格式（任选）：
- `歌手 - 歌名.lrc`
- `歌名 - 歌手.lrc`
- `歌名.lrc`

本地歌词优先于在线歌词。

## 进阶玩法

### 替换为 QQ 音乐歌词 API

如果 lrclib.net 匹配不到中文歌词，可以替换 `_try_fetch_online` 方法，
使用 QQ 音乐的歌词接口：

```python
# 1. 搜索歌曲 ID
search_url = f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp?w={title} {artist}&format=json"

# 2. 获取歌词
lyric_url = f"https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg?songmid={mid}&format=json"
```

### 打包成 EXE

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name "TaskbarLyrics" taskbar_lyrics.py
```

打包后双击即可运行，无需 Python 环境。

## 常见问题

**Q: 显示"等待播放"但已经在播放了？**
A: 确保你的播放器支持 Windows 媒体会话。可以测试：按键盘上的播放/暂停键，如果能控制播放器，说明支持。

**Q: 歌词匹配不上？**
A: lrclib.net 对英文歌支持较好，中文歌建议下载 LRC 文件放到本地目录，或替换为 QQ 音乐歌词 API。

**Q: Windows 7 能用吗？**
A: 不能。GSMTC API 需要 Windows 10 1809 (2018年10月更新) 或更高版本。
