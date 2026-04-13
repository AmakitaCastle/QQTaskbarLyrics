# Taskbar Lyrics 模块化重构设计

## 概述

将当前臃肿的单文件项目重构为按模块、按领域拆分的可复用、可扩展架构。

**核心目标：**
- 按领域拆分：utils / media / lyrics / display
- 可复用：每个模块职责单一，可独立使用
- 可扩展：Provider 插件接口，当前只接 QQ，后续可接网易云等平台
- 消除重复：删除 `taskbar_lyrics_karaoke.py`，只保留 `taskbar_lyrics.py`
- 删除无用：删除 `audio_visualizer.py`（未被主程序调用）

## 重构策略

- **方案 A — 渐进式拆分**：逐个模块抽取，每步完成后可运行验证
- **Worktree 模式**：新结构在 worktree 中隔离开发，主分支旧文件不动
- **行为不变**：所有功能保持现有行为，只改变代码组织方式

## 目标目录结构

```
.
├── taskbar_lyrics.py           # 唯一入口（瘦入口，只做组装+启动）
├── src/
│   ├── __init__.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── log.py              # 日志（文件+控制台输出）
│   │   └── crypto.py           # TripleDES / QMC1 解密
│   │
│   ├── media/
│   │   ├── __init__.py
│   │   └── provider.py         # MediaInfoProvider — GSMTC 轮询
│   │
│   ├── lyrics/
│   │   ├── __init__.py
│   │   ├── cache.py            # 磁盘缓存（JSON + TTL）
│   │   ├── parsers.py          # QRC / LRC / KRC 格式解析
│   │   ├── manager.py          # LyricsManager — 缓存+加载+当前行匹配
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py         # 抽象接口 BaseLyricsProvider
│   │       └── qq.py           # QQMusicProvider 实现
│   │
│   └── display/
│       ├── __init__.py
│       ├── config.py           # 配置加载/保存 + 配置 UI
│       ├── window.py           # TaskbarLyricsWindow — Tkinter 窗口
│       └── karaoke.py          # 像素级卡拉OK渲染引擎
│
└── config.json                 # 用户配置（迁移自 ~/.taskbar_lyrics_config.json）
```

## 模块职责

### `src/utils/`

| 文件 | 职责 |
|---|---|
| `log.py` | 日志初始化、文件输出、线程安全 |
| `crypto.py` | `_tripledes_crypt`, `_qmc1_decrypt`, `_qrc_cloud_decrypt` — 纯函数，无外部依赖 |

### `src/media/provider.py`

`MediaInfoProvider` — 独立模块，从 Windows GSMTC API 轮询媒体信息。对外暴露 `get_info() -> dict` 和 `start()/stop()`。

### `src/lyrics/` — Provider 插件接口

#### 抽象基类 `src/lyrics/providers/base.py`

```python
class BaseLyricsProvider(ABC):
    """歌词数据源抽象基类"""

    @abstractmethod
    async def search(self, title: str, artist: str, album: str = "") -> Optional[SongInfo]:
        """搜索歌曲"""
        ...

    @abstractmethod
    async def get_lyrics(self, song_info: SongInfo) -> Optional[List[LyricLine]]:
        """获取歌词，返回统一的 (time_ms, text, translation, word_timings) 格式"""
        ...
```

#### 统一数据格式

```python
# 搜索返回
SongInfo = {
    "id": str,          # 平台歌曲ID/MID
    "songID": int,      # 平台歌曲数字ID（用于缓存key）
    "title": str,
    "artist": str,
    "album": str,
    "duration": int,    # 毫秒
}

# 歌词行
LyricLine = (time_ms: int, text: str, translation: str, word_timings: list)
# word_timings = [(char_offset_ms, char_duration_ms, char), ...]  逐字时间戳，无则为 []
```

#### `src/lyrics/manager.py`

`LyricsManager` 负责：
- 本地 LRC 文件扫描
- 调用 provider 列表（按优先级）获取在线歌词
- 磁盘缓存（读写 + TTL）
- `get_current_line(lyrics, position_ms)` — 当前行匹配 + progress 计算

### `src/display/` 拆分

| 文件 | 职责 |
|---|---|
| `config.py` | 配置加载/保存 + 颜色/字体/偏移 UI 弹窗 |
| `window.py` | Tkinter 窗口生命周期、拖拽、置顶、菜单、配置入口 |
| `karaoke.py` | 像素级渲染引擎（`_rebuild`, `_paint`, `_lerp_color`） |

## 依赖关系

```
taskbar_lyrics.py (入口)
    ├── src.media.provider.MediaInfoProvider
    ├── src.lyrics.manager.LyricsManager
    │   ├── src.lyrics.providers.base.BaseLyricsProvider
    │   ├── src.lyrics.providers.qq.QQMusicProvider
    │   ├── src.lyrics.cache
    │   ├── src.lyrics.parsers
    │   └── 间接依赖 src.utils.crypto
    └── src.display.window.TaskbarLyricsWindow
        ├── src.display.config
        └── src.display.karaoke
```

## 数据流（保持不变）

```
GSMTC → MediaInfoProvider.get_info()
    ↓ 歌曲切换时
LyricsManager.load_async(title, artist, album)
    ├── 1. 检查内存缓存
    ├── 2. 检查磁盘缓存
    ├── 3. 扫描本地 LRC 文件
    └── 4. 遍历 provider 列表获取在线歌词
    ↓ callback → lyrics list
    ↓ 每 50ms
LyricsManager.get_current_line(lyrics, position_ms)
    → (orig, trans, progress)
    ↓
TaskbarLyricsWindow.update_display(orig, trans, progress)
    ↓
KaraokeEngine._paint() → Canvas 更新
```

## 迁移步骤

| 步骤 | 操作 | 验证方式 |
|---|---|---|
| **1** | 创建 worktree，建立 `src/` 骨架 + 所有 `__init__.py` | `import src` 无报错 |
| **2** | 搬移 `log` 到 `src/utils/log.py`，更新所有 import | 日志正常输出 |
| **3** | 搬移加密代码到 `src/utils/crypto.py`，更新 import | QQ 歌词能正常解密 |
| **4** | 搬移歌词解析器到 `src/lyrics/parsers.py`（QRC/LRC/KRC） | 歌词解析结果与之前一致 |
| **5** | 搬移缓存逻辑到 `src/lyrics/cache.py` | 缓存命中/写入正常 |
| **6** | 创建 `src/lyrics/providers/base.py` 抽象接口 | 接口定义无报错 |
| **7** | 搬移 QQ 音乐 API 到 `src/lyrics/providers/qq.py`，实现 `BaseLyricsProvider` | QQ 搜索+歌词获取正常 |
| **8** | 重构 `LyricsManager` 到 `src/lyrics/manager.py`，使用 provider 列表 | 歌词加载全流程正常 |
| **9** | 搬移 `MediaInfoProvider` 到 `src/media/provider.py` | 媒体信息获取正常 |
| **10** | 拆分显示层：`config.py` / `window.py` / `karaoke.py` | 窗口显示、拖拽、菜单正常 |
| **11** | 瘦身 `taskbar_lyrics.py` 为纯入口 | `python taskbar_lyrics.py` 完全正常 |
| **12** | 全局检查：无残留 import、无重复代码 | 最终验收 |

## 当前问题清单（重构中一并解决）

1. `MediaInfoProvider` 在 `taskbar_lyrics.py` 和 `taskbar_lyrics_karaoke.py` 中重复 → 提取到 `src/media/provider.py`
2. `LyricsManager` 两个版本重复 → 合并为 `src/lyrics/manager.py`
3. `lyrics_api.py` 中 TripleDES 解密 + QRC 解析 + QQ API + 缓存全部拆开
4. `taskbar_lyrics.py` 中窗口逻辑 + 配置 + 渲染混在一起 → 拆为 `display/` 三模块
5. 日志系统同时存在 `log()` 和 `lyrics_api.log()` → 统一到 `src/utils/log.py`
