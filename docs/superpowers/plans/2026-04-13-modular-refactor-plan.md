# Taskbar Lyrics 模块化重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将臃肿的单文件 `taskbar_lyrics.py` + `lyrics_api.py` 重构为 `src/` 下按领域拆分的模块化架构

**Architecture:** 渐进式拆分 — 在 worktree 中按 utils → lyrics → media → display 顺序逐个模块搬移代码，保持每步可运行，最终瘦身入口文件

**Tech Stack:** Python 3.10+, Tkinter, winsdk, requests, abc, dataclasses

---

## 文件清单

### 新建文件

| 文件 | 职责 |
|---|---|
| `src/__init__.py` | 包初始化 |
| `src/utils/__init__.py` | utils 包 |
| `src/utils/log.py` | 统一日志系统 |
| `src/utils/crypto.py` | TripleDES / QMC1 解密（从 `lyrics_api.py:42-210` 搬移） |
| `src/media/__init__.py` | media 包 |
| `src/media/provider.py` | MediaInfoProvider（从 `taskbar_lyrics.py:53-102` 搬移） |
| `src/lyrics/__init__.py` | lyrics 包 |
| `src/lyrics/cache.py` | 磁盘缓存（从 `lyrics_api.py:286-349` + `taskbar_lyrics.py:109-163` 合并） |
| `src/lyrics/parsers.py` | QRC / LRC 解析（从 `lyrics_api.py:213-279` 搬移） |
| `src/lyrics/providers/__init__.py` | providers 包 |
| `src/lyrics/providers/base.py` | 抽象接口 |
| `src/lyrics/providers/qq.py` | QQ 音乐实现（从 `lyrics_api.py:352-808` 搬移 + 适配接口） |
| `src/lyrics/manager.py` | LyricsManager（从 `taskbar_lyrics.py:108-295` 重构，使用 provider） |
| `src/display/__init__.py` | display 包 |
| `src/display/config.py` | 配置加载/保存 + UI 弹窗（从 `taskbar_lyrics.py:661-736` 搬移） |
| `src/display/window.py` | Tkinter 窗口骨架（从 `taskbar_lyrics.py:302-485` 搬移窗口部分） |
| `src/display/karaoke.py` | 像素级卡拉OK渲染（从 `taskbar_lyrics.py:513-658` 搬移） |

### 修改文件

| 文件 | 操作 |
|---|---|
| `taskbar_lyrics.py` | 瘦身为纯入口文件（约 50 行），import src.* |

### 保留不改动（主分支）

| 文件 | 说明 |
|---|---|
| `lyrics_api.py` | worktree 中不再引用，保留在主分支 |
| `taskbar_lyrics_karaoke.py` | worktree 中删除 |
| `audio_visualizer.py` | worktree 中删除 |

---

### Task 1: 创建 Worktree + 骨架

**Files:**
- Create: `src/__init__.py`
- Create: `src/utils/__init__.py`
- Create: `src/media/__init__.py`
- Create: `src/lyrics/__init__.py`
- Create: `src/lyrics/providers/__init__.py`
- Create: `src/display/__init__.py`

- [ ] **Step 1: 创建 worktree**

```bash
git worktree add ../taskbar-refactor -b refactor/modular-structure
```

- [ ] **Step 2: 创建目录骨架和所有 `__init__.py`**

在 worktree `../taskbar-refactor/` 中：

```bash
mkdir -p src/utils src/media src/lyrics/providers src/display
```

每个 `__init__.py` 内容：

```python
# src/__init__.py
# src/utils/__init__.py
# src/media/__init__.py
# src/lyrics/__init__.py
# src/lyrics/providers/__init__.py
# src/display/__init__.py

# 包初始化
```

- [ ] **Step 3: 复制入口文件（临时，后续会删除）**

```bash
cp taskbar_lyrics.py .
cp lyrics_api.py .
```

注意：`lyrics_api.py` 和 `taskbar_lyrics.py` 此时原样复制，保持可运行状态。

- [ ] **Step 4: 从 worktree 删除不需要的文件**

```bash
rm taskbar_lyrics_karaoke.py
rm audio_visualizer.py
```

- [ ] **Step 5: 验证当前状态可运行**

```bash
python taskbar_lyrics.py
# 应该能正常启动（此时还是旧代码）
```

- [ ] **Step 6: 提交骨架**

```bash
git add src/ taskbar_lyrics.py
git rm taskbar_lyrics_karaoke.py audio_visualizer.py
git commit -m "refactor: create modular src/ skeleton, remove karaoke and visualizer"
```

---

### Task 2: 统一日志系统

**Files:**
- Create: `src/utils/log.py`
- Modify: `taskbar_lyrics.py` — 将 `_init_log()` / `log()` 替换为 import
- Modify: `lyrics_api.py` — 将 `_init_lyrics_log()` / `log()` 替换为 import

- [ ] **Step 1: 创建 `src/utils/log.py`**

从 `taskbar_lyrics.py:16-42` 和 `lyrics_api.py:16-35` 合并为统一的日志模块：

```python
"""
统一日志模块 — 终端 + 文件双输出，线程安全
"""

import sys
import io
import os
import threading
import datetime

# 设置 stdout 编码为 utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

_log_lock = threading.Lock()
_log_file = None
_initialized = False


def _init_log():
    """初始化日志（调用一次）"""
    global _log_file, _initialized
    if _initialized:
        return
    _initialized = True
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'taskbar_lyrics.log')
    path = os.path.normpath(path)
    _log_file = open(path, 'a', encoding='utf-8')


def log(msg):
    """输出日志到终端和文件"""
    if not _initialized:
        _init_log()
    ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except:
        pass
    with _log_lock:
        if _log_file:
            try:
                _log_file.write(line + '\n')
                _log_file.flush()
            except:
                pass
```

- [ ] **Step 2: 更新 `taskbar_lyrics.py` 中的日志引用**

将 `taskbar_lyrics.py:15-42` 的 `_init_log()` / `log()` 函数定义替换为：

```python
from src.utils.log import log, _init_log
```

- [ ] **Step 3: 更新 `lyrics_api.py` 中的日志引用**

将 `lyrics_api.py:17-35` 的 `log()` / `_init_lyrics_log()` 函数定义替换为：

```python
from src.utils.log import log
```

（注意：`lyrics_api.py` 中 `_init_lyrics_log` 只在 `taskbar_lyrics.py` 被调用，移除后由 `src.utils.log._init_log()` 统一处理）

- [ ] **Step 4: 验证日志正常**

```bash
python taskbar_lyrics.py
# 日志应正常输出到终端和 taskbar_lyrics.log 文件
```

- [ ] **Step 5: 提交**

```bash
git add src/utils/log.py taskbar_lyrics.py lyrics_api.py
git commit -m "refactor: unify logging into src/utils/log.py"
```

---

### Task 3: 搬移加密模块

**Files:**
- Create: `src/utils/crypto.py`
- Modify: `lyrics_api.py` — 删除加密代码，改为 import

- [ ] **Step 1: 创建 `src/utils/crypto.py`**

从 `lyrics_api.py:42-210` 完整搬移 TripleDES / QMC1 解密代码：

```python
"""
TripleDES / QMC1 歌词解密 — 纯函数，无外部依赖
从 QQ 音乐 QRC 加密歌词解密
"""

import zlib
from typing import Union

# ============================================================
# QQ 音乐 QRC 歌词解密 — TripleDES 实现
# ============================================================

_QRC_3DES_KEY = b"!@#)(*$%123ZXC!@!@#)(NHL"

_ENCRYPT = 1
_DECRYPT = 0

_SBOX = (
    (14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7, 0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8,
     4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0, 15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13),
    (15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10, 3,13,4,7,15,2,8,15,12,0,1,10,6,9,11,5,
     0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15, 13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9),
    (10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8, 13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1,
     13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7, 1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12),
    (7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15, 13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9,
     10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4, 3,15,0,6,10,10,13,8,9,4,5,11,12,7,2,14),
    (2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9, 14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6,
     4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14, 11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3),
    (12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11, 10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8,
     9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6, 4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13),
    (4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1, 13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6,
     1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2, 6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12),
    (13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7, 1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2,
     7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8, 2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11),
)

_des_key_cache = {}

_QMC1_PRIVKEY = (
    0xc3, 0x4a, 0xd6, 0xca, 0x90, 0x67, 0xf7, 0x52,
    0xd8, 0xa1, 0x66, 0x62, 0x9f, 0x5b, 0x09, 0x00,
    0xc3, 0x5e, 0x95, 0x23, 0x9f, 0x13, 0x11, 0x7e,
    0xd8, 0x92, 0x3f, 0xbc, 0x90, 0xbb, 0x74, 0x0e,
    0xc3, 0x47, 0x74, 0x3d, 0x90, 0xaa, 0x3f, 0x51,
    0xd8, 0xf4, 0x11, 0x84, 0x9f, 0xde, 0x95, 0x1d,
    0xc3, 0xc6, 0x09, 0xd5, 0x9f, 0xfa, 0x66, 0xf9,
    0xd8, 0xf0, 0xf7, 0xa0, 0x90, 0xa1, 0xd6, 0xf3,
    0xc3, 0xf3, 0xd6, 0xa1, 0x90, 0xa0, 0xf7, 0xf0,
    0xd8, 0xf9, 0x66, 0xfa, 0x9f, 0xd5, 0x09, 0xc6,
    0xc3, 0x1d, 0x95, 0xde, 0x9f, 0x84, 0x11, 0xf4,
    0xd8, 0x51, 0x3f, 0xaa, 0x90, 0x3d, 0x74, 0x47,
    0xc3, 0x0e, 0x74, 0xbb, 0x90, 0xbc, 0x3f, 0x92,
    0xd8, 0x7e, 0x11, 0x13, 0x9f, 0x23, 0x95, 0x5e,
    0xc3, 0x00, 0x09, 0x5b, 0x9f, 0x62, 0x66, 0xa1,
    0xd8, 0x52, 0xf7, 0x67, 0x90, 0xca, 0xd6, 0x4a,
)


# --- 以下是搬自 lyrics_api.py 的 DES 实现 (行 66-170) ---
# 完整搬移 _bitnum, _bitnum_intr, _bitnum_intl, _sbox_bit,
# _initial_permutation, _inverse_permutation, _f, _des_crypt,
# _des_key_schedule, _tripledes_key_setup, _tripledes_crypt,
# _qrc_cloud_decrypt, _qmc1_decrypt

# （具体代码从 lyrics_api.py:66-190 逐行复制）
```

从 `lyrics_api.py` 第 66-190 行完整复制以下函数到 `src/utils/crypto.py`：
- `_bitnum`, `_bitnum_intr`, `_bitnum_intl`, `_sbox_bit`
- `_initial_permutation`, `_inverse_permutation`, `_f`
- `_des_crypt`, `_des_key_schedule`
- `_tripledes_key_setup`, `_tripledes_crypt`
- `_qrc_cloud_decrypt`（line 163-170）
- `_qmc1_decrypt`（line 184-190）

- [ ] **Step 2: 更新 `lyrics_api.py` 中的加密引用**

删除 `lyrics_api.py:42-210` 的所有加密代码（`_QRC_3DES_KEY` 到 `_qmc1_decrypt`），替换为：

```python
from src.utils.crypto import _qrc_cloud_decrypt, _qmc1_decrypt
```

- [ ] **Step 3: 验证解密正常**

```bash
python -c "
from src.utils.crypto import _qrc_cloud_decrypt
# 简单的完整性检查
print('Crypto module imported OK')
"
```

- [ ] **Step 4: 提交**

```bash
git add src/utils/crypto.py lyrics_api.py
git commit -m "refactor: move crypto to src/utils/crypto.py"
```

---

### Task 4: 搬移歌词解析器

**Files:**
- Create: `src/lyrics/parsers.py`
- Modify: `lyrics_api.py` — 删除解析代码，改为 import

- [ ] **Step 1: 创建 `src/lyrics/parsers.py`**

从 `lyrics_api.py:213-279` 搬移 QRC / LRC 解析：

```python
"""
歌词格式解析器 — QRC 逐字 / LRC 行级
"""

import re
from typing import List, Tuple

from src.utils.crypto import _qrc_cloud_decrypt, _qmc1_decrypt

# ============================================================
# QRC 歌词解析
# ============================================================

_QRC_CONTENT_PATTERN = re.compile(
    r'<Lyric_1 LyricType="1" LyricContent="(?P<content>.*?)"/>',
    re.DOTALL
)
_QRC_LINE_PATTERN = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_QRC_WORD_PATTERN = re.compile(
    r"(?:\[\d+,\d+\])?(?P<content>(?:(?!\(\d+,\d+\)).)*)\((?P<start>\d+),(?P<duration>\d+)\)"
)

LyricLine = Tuple[int, str, str, list]  # (time_ms, text, translation, word_timings)
SimpleLyricLine = Tuple[int, str, list]  # (time_ms, text, word_timings)


def parse_qrc(qrc_text: str) -> List[SimpleLyricLine]:
    """解析 QRC 逐字歌词"""
    match = _QRC_CONTENT_PATTERN.search(qrc_text)
    if not match:
        return parse_lrc(qrc_text)

    result = []
    content = match.group("content")

    for raw_line in content.splitlines():
        line = raw_line.strip()
        line_match = _QRC_LINE_PATTERN.match(line)
        if not line_match:
            continue

        line_start = int(line_match.group(1))
        line_content = line_match.group(3)

        words = []
        text_parts = []
        for wm in _QRC_WORD_PATTERN.finditer(line_content):
            char_text = wm.group("content")
            if char_text and char_text != "\r":
                char_start = int(wm.group("start")) - line_start
                char_duration = int(wm.group("duration"))
                words.append((char_start, char_duration, char_text))
                text_parts.append(char_text)

        if not text_parts:
            continue

        full_text = "".join(text_parts)
        result.append((line_start, full_text, words))

    result.sort(key=lambda x: x[0])
    return result


def parse_lrc(lrc_text: str) -> List[SimpleLyricLine]:
    """解析 LRC 歌词"""
    lines = []
    for line in lrc_text.splitlines():
        line = line.strip()
        if not line:
            continue
        matches = re.findall(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)', line)
        for mm, ss, ms, text in matches:
            time_ms = int(mm) * 60000 + int(ss) * 1000
            if len(ms) == 2:
                time_ms += int(ms) * 10
            else:
                time_ms += int(ms)
            text = text.strip()
            if text:
                lines.append((time_ms, text, []))
    lines.sort(key=lambda x: x[0])
    return lines


def decrypt_and_parse_qrc(encrypted_hex: str) -> List[SimpleLyricLine] | None:
    """解密并解析 QRC 歌词（云端 TripleDES 加密）"""
    try:
        text = _qrc_cloud_decrypt(encrypted_hex)
        return parse_qrc(text), text
    except Exception:
        return None
```

- [ ] **Step 2: 更新 `lyrics_api.py`**

删除 `lyrics_api.py:213-279` 的 `_QRC_*_PATTERN`, `_parse_qrc`, `_parse_lrc_fallback`，替换为：

```python
from src.lyrics.parsers import parse_qrc, parse_lrc
```

- [ ] **Step 3: 提交**

```bash
git add src/lyrics/parsers.py lyrics_api.py
git commit -m "refactor: move lyric parsers to src/lyrics/parsers.py"
```

---

### Task 5: 搬移缓存模块

**Files:**
- Create: `src/lyrics/cache.py`
- Modify: `lyrics_api.py` — 删除缓存代码，改为 import

- [ ] **Step 1: 创建 `src/lyrics/cache.py`**

合并 `lyrics_api.py:286-349`（在线缓存）和 `taskbar_lyrics.py:109-163`（磁盘缓存）：

```python
"""
歌词磁盘缓存 — JSON 格式 + TTL 过期
"""

import json
import os
import time
import hashlib
import threading
from pathlib import Path
from typing import Optional, Any

from src.utils.log import log

_CACHE_DIR = Path.home() / ".taskbar_lyrics_cache"
_CACHE_FILE = _CACHE_DIR / "cache.json"
_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 天

_cache_lock = threading.Lock()
_cache_data: Optional[dict] = None


def _load_cache():
    """加载缓存到内存"""
    global _cache_data
    if _cache_data is not None:
        return
    with _cache_lock:
        if _cache_data is not None:
            return
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            if _CACHE_FILE.exists():
                with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                    _cache_data = json.load(f)
            else:
                _cache_data = {}
        except Exception as e:
            log(f"    [缓存] 加载失败: {e}")
            _cache_data = {}


def _save_cache():
    """保存缓存到磁盘"""
    global _cache_data
    if _cache_data is None:
        return
    with _cache_lock:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = _CACHE_FILE.with_suffix(".tmp")
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(_cache_data, f, ensure_ascii=False, indent=2)
            tmp.replace(_CACHE_FILE)
        except Exception as e:
            log(f"    [缓存] 保存失败: {e}")


def cache_get(key: str) -> Optional[Any]:
    """获取缓存，过期返回 None"""
    _load_cache()
    entry = _cache_data.get(key)
    if not entry:
        return None
    if time.time() - entry.get("ts", 0) > _CACHE_TTL_SECONDS:
        del _cache_data[key]
        _save_cache()
        return None
    return entry.get("data")


def cache_set(key: str, data: Any):
    """写入缓存"""
    _load_cache()
    _cache_data[key] = {"data": data, "ts": time.time()}
    _save_cache()


def cache_clean():
    """清理过期缓存"""
    _load_cache()
    now = time.time()
    expired_keys = [k for k, v in _cache_data.items() if now - v.get("ts", 0) > _CACHE_TTL_SECONDS]
    for k in expired_keys:
        del _cache_data[k]
    if expired_keys:
        _save_cache()
        log(f"    [缓存] 清理 {len(expired_keys)} 条过期记录")


def disk_cache_key(title: str, artist: str, album: str = "") -> str:
    """生成磁盘缓存 key（基于标题信息的 MD5）"""
    raw = f"{artist}|{title}|{album}"
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return h


def load_disk_lyrics(key: str) -> Optional[list]:
    """从磁盘缓存加载歌词"""
    try:
        cache_file = _CACHE_DIR / f"{key}.json"
        if not cache_file.exists():
            return None
        age = time.time() - cache_file.stat().st_mtime
        if age > _CACHE_TTL_SECONDS:
            cache_file.unlink(missing_ok=True)
            return None
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        lyrics = []
        for item in data.get("lyrics", []):
            wt = [tuple(w) for w in item[3]] if item[3] else []
            lyrics.append((item[0], item[1], item[2], wt))
        return lyrics
    except Exception:
        return None


def save_disk_lyrics(key: str, lyrics: list):
    """将歌词写入磁盘缓存"""
    try:
        cache_file = _CACHE_DIR / f"{key}.json"
        data = {
            "key": key,
            "lyrics": [[t, tx, tr, [list(w) for w in wt]] for t, tx, tr, wt in lyrics],
        }
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(cache_file)
    except Exception:
        pass
```

- [ ] **Step 2: 更新 `lyrics_api.py`**

删除 `lyrics_api.py:286-349` 的缓存代码，替换为：

```python
from src.lyrics.cache import cache_get, cache_set, cache_clean
```

- [ ] **Step 3: 更新 `taskbar_lyrics.py`**

删除 `taskbar_lyrics.py:109-163` 的 `_ensure_cache_dir`, `_cache_path`, `_load_cache`, `_save_cache`，替换为：

```python
from src.lyrics.cache import load_disk_lyrics, save_disk_lyrics, disk_cache_key
```

- [ ] **Step 4: 提交**

```bash
git add src/lyrics/cache.py lyrics_api.py taskbar_lyrics.py
git commit -m "refactor: move cache logic to src/lyrics/cache.py"
```

---

### Task 6: 创建 Provider 抽象接口

**Files:**
- Create: `src/lyrics/providers/base.py`

- [ ] **Step 1: 创建 `src/lyrics/providers/base.py`**

```python
"""
歌词数据源抽象基类 — 为后续接入网易云等平台预留接口
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

SongInfo = Dict[str, Any]
# {
#     "id": str,          # 平台歌曲ID/MID
#     "songID": int,      # 平台歌曲数字ID（用于缓存key）
#     "title": str,
#     "artist": str,
#     "album": str,
#     "duration": int,    # 毫秒
# }

LyricLine = tuple  # (time_ms: int, text: str, translation: str, word_timings: list)


class BaseLyricsProvider(ABC):
    """歌词数据源抽象基类"""

    @abstractmethod
    def search(self, title: str, artist: str, album: str = "") -> Optional[SongInfo]:
        """搜索歌曲"""
        ...

    @abstractmethod
    def get_lyrics(self, song_info: SongInfo) -> Optional[List[LyricLine]]:
        """获取歌词
        返回: [(time_ms, text, translation, word_timings), ...]
        word_timings = [(char_offset_ms, char_duration_ms, char), ...]
        """
        ...
```

- [ ] **Step 2: 提交**

```bash
git add src/lyrics/providers/base.py
git commit -m "feat: add BaseLyricsProvider abstract interface"
```

---

### Task 7: 搬移 QQ 音乐 Provider

**Files:**
- Create: `src/lyrics/providers/qq.py`
- Modify: `lyrics_api.py` — 删除 QQ API 代码，改为 import（保留 LyricsProvider 包装类直到 Task 8）

- [ ] **Step 1: 创建 `src/lyrics/providers/qq.py`**

从 `lyrics_api.py:352-808` 搬移 `QQMusicAPI` 类，适配 `BaseLyricsProvider` 接口：

```python
"""
QQ 音乐歌词 Provider — 实现 BaseLyricsProvider 接口
支持: QRC 逐字歌词 + 翻译 (GetPlayLyricInfo) + 旧接口回退
"""

import json
import base64
import time
import requests
from typing import List, Tuple, Optional, Dict

from src.lyrics.providers.base import BaseLyricsProvider, SongInfo, LyricLine
from src.lyrics.cache import cache_get, cache_set
from src.lyrics.parsers import parse_qrc, parse_lrc
from src.utils.crypto import _qrc_cloud_decrypt, _qmc1_decrypt
from src.utils.log import log


class QQMusicProvider(BaseLyricsProvider):
    """QQ音乐歌词数据源"""

    def __init__(self):
        self._session_cache = None
        self._session_time = 0
        self.comm = {
            "ct": 11,
            "cv": "1003006",
            "v": "1003006",
            "os_ver": "15",
            "phonetype": "24122RKC7C",
            "tmeAppID": "qqmusiclight",
            "nettype": "NETWORK_WIFI",
            "udid": "0"
        }

    def _get_session(self) -> Dict:
        """获取 QQ 音乐 session，缓存 30 分钟"""
        now = time.time()
        if self._session_cache and (now - self._session_time) < 1800:
            return self._session_cache
        try:
            url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
            payload = {
                "comm": self.comm,
                "request": {
                    "method": "GetSession",
                    "module": "music.getSession.session",
                    "param": {"caller": 0, "uid": "0", "vkey": 0}
                }
            }
            headers = {
                "User-Agent": "okhttp/3.14.9",
                "content-type": "application/json",
                "cookie": "tmeLoginType=-1;",
                "accept-encoding": "gzip",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") != 0 or data.get("request", {}).get("code") != 0:
                raise Exception(f"code={data.get('code')}, request_code={data.get('request', {}).get('code')}")
            session_data = data["request"]["data"]["session"]
            self._session_cache = {
                "uid": session_data.get("uid", 0),
                "sid": session_data.get("sid", ""),
                "userip": session_data.get("userip", "")
            }
            self.comm["uid"] = self._session_cache["uid"]
            self.comm["sid"] = self._session_cache["sid"]
            self.comm["userip"] = self._session_cache["userip"]
            self._session_time = time.time()
            return self._session_cache
        except Exception as e:
            log(f"    [QQ Session] 获取失败: {e}")
            return {"uid": 0, "sid": "", "userip": ""}

    def search(self, title: str, artist: str = "", album: str = "") -> Optional[SongInfo]:
        """搜索歌曲"""
        query = f"{title} {artist}".strip()
        cache_key = f"qq_search:{query}"
        cached = cache_get(cache_key)
        if cached:
            log(f"    [QQ搜索] 缓存命中: '{query}'")
            return cached
        log(f"    [QQ搜索] query='{query}'")
        try:
            url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
            payload = {
                "req_1": {
                    "module": "music.search.SearchCgiService",
                    "method": "DoSearchForQQMusicDesktop",
                    "param": {
                        "num_per_page": 20,
                        "page_num": 1,
                        "query": query,
                        "search_type": 0
                    }
                }
            }
            params = {"format": "json", "data": json.dumps(payload)}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://y.qq.com/"
            }
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            data = resp.json()
            req_1 = data.get("req_1", {})
            body = req_1.get("data", {})
            songs = body.get("body", {}).get("song", {}).get("list", [])
            if not songs:
                log(f"    [QQ搜索] 无结果")
                return None

            for i, song in enumerate(songs[:3]):
                s_title = song.get("name", "")
                s_artist = song.get("singer", [{}])[0].get("name", "")
                s_album = song.get("album", {}).get("name", "")
                log(f"    [QQ搜索] 结果{i+1}: {s_title} - {s_artist} (专辑: {s_album})")

            title_lower = title.lower().replace(" ", "")
            artist_lower = artist.lower().replace(" ", "") if artist else ""
            best_match = None
            best_score = -1

            for song in songs:
                song_title = song.get("name", "").lower().replace(" ", "")
                song_artist = song.get("singer", [{}])[0].get("name", "").lower().replace(" ", "")
                skip_keywords = ['cover', 'remix', '翻唱', '改编', '版本', 'ver.', 'live']
                song_name = song.get("name", "").lower()
                if any(kw in song_name for kw in skip_keywords):
                    continue
                score = 0
                clean_title = song_title.replace("-", "").replace("_", "").replace("~", "")
                clean_target = title_lower.replace("-", "").replace("_", "").replace("~", "")
                if clean_title == clean_target:
                    score += 100
                elif clean_title.startswith(clean_target) or clean_target.startswith(clean_title):
                    score += 60
                elif title_lower in song_title or song_title in title_lower:
                    score += 30
                else:
                    continue
                if artist_lower and song_artist:
                    clean_artist = song_artist.replace("-", "").replace("_", "")
                    clean_target_artist = artist_lower.replace("-", "").replace("_", "")
                    if clean_artist == clean_target_artist:
                        score += 50
                    elif clean_target_artist in clean_artist or clean_artist in clean_target_artist:
                        score += 30
                    elif album:
                        album_lower = album.lower().replace(" ", "")
                        song_album = song.get("album", {}).get("name", "").lower().replace(" ", "")
                        white_album_keywords = ['white album2', 'whitealbum2', 'white album', 'wa2']
                        same_work = any(kw in album_lower.replace(" ", "") for kw in white_album_keywords) and \
                                    any(kw in song_album for kw in white_album_keywords)
                        if not same_work:
                            continue
                    else:
                        continue
                elif artist_lower and not song_artist:
                    continue
                if album:
                    song_album = song.get("album", {}).get("name", "").lower()
                    clean_album = album.lower().replace(" ", "")
                    clean_song_album = song_album.replace(" ", "")
                    if clean_album == clean_song_album:
                        score += 80
                    elif clean_album in clean_song_album or clean_song_album in clean_album:
                        score += 40
                if score > best_score:
                    best_score = score
                    best_match = song

            if not best_match:
                for song in songs:
                    song_name = song.get("name", "").lower()
                    skip_keywords = ['cover', 'remix', '翻唱', '改编', '版本', 'ver.', 'live']
                    if not any(kw in song_name for kw in skip_keywords):
                        best_match = song
                        break
                if not best_match:
                    best_match = songs[0]

            result = {
                "id": best_match.get("mid"),
                "songID": best_match.get("id", 0),
                "title": best_match.get("name"),
                "artist": best_match.get("singer", [{}])[0].get("name", ""),
                "album": best_match.get("album", {}).get("name", ""),
                "duration": best_match.get("interval", 0) * 1000
            }
            cache_set(cache_key, result)
            return result
        except Exception as e:
            log(f"    [QQ音乐搜索] 失败: {e}")
            return None

    def get_lyrics(self, song_info: SongInfo) -> Optional[List[LyricLine]]:
        """获取歌词（优先旧接口，QRC 需登录）"""
        song_id = song_info.get("songID", 0)
        log(f"    [QQ音乐歌词] 开始获取歌词: songID={song_id}, songMID={song_info.get('id', '')}")

        legacy_result = self._get_lyrics_legacy(song_info)
        if legacy_result:
            has_trans = sum(1 for _, _, tr, _ in legacy_result if tr)
            has_word = sum(1 for _, _, _, wt in legacy_result if wt)
            log(f"    [QQ音乐歌词] 旧接口成功: {len(legacy_result)} 行, 翻译 {has_trans} 行, 逐字 {has_word} 行")
            if has_trans > 0:
                return legacy_result
            log("    [QQ音乐歌词] 旧接口无翻译，尝试 GetPlayLyricInfo 补充...")
        else:
            log(f"    [QQ音乐歌词] 旧接口返回 None")

        log("    [QQ音乐歌词] 尝试 GetPlayLyricInfo...")
        if not song_id:
            log(f"    [QQ音乐歌词] 缺少 songID，无法调用 GetPlayLyricInfo")
            return legacy_result

        session = self._get_session()
        if not session.get("sid"):
            log("    [QQ音乐歌词] 无 session(sid为空)，无法获取 QRC 歌词")
            return legacy_result

        title = song_info.get("title", "")
        album = song_info.get("album", "")
        singer = song_info.get("artist", "")
        duration = song_info.get("duration", 0) // 1000

        try:
            url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
            payload = {
                "comm": self.comm,
                "request": {
                    "method": "GetPlayLyricInfo",
                    "module": "music.musichallSong.PlayLyricInfo",
                    "param": {
                        "songID": song_id,
                        "songName": base64.b64encode(title.encode()).decode() if title else "",
                        "albumName": base64.b64encode(album.encode()).decode() if album else "",
                        "singerName": base64.b64encode(singer.encode()).decode() if singer else "",
                        "interval": duration,
                        "crypt": 1,
                        "qrc": 1,
                        "trans": 1,
                        "roma": 1,
                        "lrc_t": 0,
                        "qrc_t": 0,
                        "trans_t": 0,
                        "roma_t": 0,
                        "type": 0,
                        "ct": 19,
                        "cv": 2111,
                    }
                }
            }
            headers = {
                "User-Agent": "okhttp/3.14.9",
                "content-type": "application/json",
                "cookie": "tmeLoginType=-1;",
                "accept-encoding": "gzip",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            data = resp.json()
            lyric_info = data.get("request", {}).get("data", {})
            lyric_enc = lyric_info.get("lyric", "")
            trans_enc = lyric_info.get("trans", "")
            crypt = lyric_info.get("crypt", 1)

            if not lyric_enc:
                return legacy_result

            try:
                orig_text = _qrc_cloud_decrypt(lyric_enc)
            except Exception:
                try:
                    if all(c in "0123456789ABCDEFabcdef" for c in lyric_enc[:4]):
                        lyric_bytes = bytes.fromhex(lyric_enc)
                    else:
                        lyric_bytes = base64.b64decode(lyric_enc)
                    lyric_ba = bytearray(lyric_bytes)
                    if crypt == 1:
                        _qmc1_decrypt(lyric_ba)
                    orig_text = lyric_ba.decode("utf-8")
                except Exception:
                    return legacy_result

            orig_lines = parse_qrc(orig_text)
            trans_map = {}
            trans_lines_list = []
            trans_decrypted_text = None
            if trans_enc:
                try:
                    trans_text = _qrc_cloud_decrypt(trans_enc)
                    trans_decrypted_text = trans_text
                    if '<Lyric_1' in trans_text[:200]:
                        trans_parsed = parse_qrc(trans_text)
                    else:
                        trans_parsed = parse_lrc(trans_text)
                    for time_ms, text, _ in trans_parsed:
                        trans_map[time_ms] = text
                    trans_lines_list = trans_parsed
                except Exception:
                    try:
                        if all(c in "0123456789ABCDEFabcdef" for c in trans_enc[:4]):
                            trans_bytes = bytes.fromhex(trans_enc)
                        else:
                            trans_bytes = base64.b64decode(trans_enc)
                        trans_ba = bytearray(trans_bytes)
                        if crypt == 1:
                            _qmc1_decrypt(trans_ba)
                        trans_text = trans_ba.decode("utf-8")
                        trans_decrypted_text = trans_text
                        if '<Lyric_1' in trans_text[:200]:
                            trans_parsed = parse_qrc(trans_text)
                        else:
                            trans_parsed = parse_lrc(trans_text)
                        for time_ms, text, _ in trans_parsed:
                            trans_map[time_ms] = text
                        trans_lines_list = trans_parsed
                    except Exception:
                        pass

            is_qrc_trans = (trans_decrypted_text is not None and '<Lyric_1' in trans_decrypted_text[:200])
            result = []
            if trans_lines_list and not is_qrc_trans:
                for i, (time_ms, text, word_timings) in enumerate(orig_lines):
                    translation = trans_lines_list[i][1] if i < len(trans_lines_list) else ""
                    result.append((time_ms, text, translation, word_timings))
            elif trans_map and is_qrc_trans:
                for time_ms, text, word_timings in orig_lines:
                    translation = trans_map.get(time_ms, "")
                    result.append((time_ms, text, translation, word_timings))
            else:
                for time_ms, text, word_timings in orig_lines:
                    result.append((time_ms, text, "", word_timings))

            has_trans = sum(1 for _, _, tr, _ in result if tr)
            has_word = sum(1 for _, _, _, wt in result if wt)
            log(f"    [QQ音乐歌词] GetPlayLyricInfo 成功: {len(result)} 行, 翻译 {has_trans} 行, 逐字 {has_word} 行")
            return result
        except Exception as e:
            log(f"    [QQ音乐歌词] GetPlayLyricInfo 失败: {e}")
            return legacy_result

    def _get_lyrics_legacy(self, song_info: SongInfo) -> Optional[List[LyricLine]]:
        """旧版歌词接口（回退用）"""
        song_mid = song_info.get("id", "")
        try:
            url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
            params = {
                "songmid": song_mid,
                "format": "json",
                "nobase64": 1,
                "songtype": 0,
                "callback": ""
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://y.qq.com/"
            }
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            text = resp.text
            if text.startswith("MusicJsonCallback("):
                text = text[18:-1]
            elif text.startswith("callback("):
                text = text[9:-1]
            data = json.loads(text)
            lyric = data.get("lyric", "")
            trans_raw = data.get("trans", "")
            if not lyric:
                return None
            orig_lines = parse_lrc(lyric)
            trans_map = {}
            if trans_raw:
                for time_ms, t, _ in parse_lrc(trans_raw):
                    trans_map[time_ms] = t
            result = []
            for time_ms, text, word_timings in orig_lines:
                translation = trans_map.get(time_ms, "")
                result.append((time_ms, text, translation, word_timings))
            return result
        except Exception as e:
            log(f"    [QQ音乐歌词(旧)] 失败: {e}")
            return None
```

- [ ] **Step 2: 更新 `lyrics_api.py`**

删除 `lyrics_api.py:352-808` 的 `QQMusicAPI` 类定义，替换为：

```python
from src.lyrics.providers.qq import QQMusicProvider as QQMusicAPI
```

- [ ] **Step 3: 提交**

```bash
git add src/lyrics/providers/qq.py lyrics_api.py
git commit -m "refactor: move QQ Music provider to src/lyrics/providers/qq.py"
```

---

### Task 8: 重构 LyricsManager

**Files:**
- Create: `src/lyrics/manager.py`
- Modify: `taskbar_lyrics.py` — 删除旧 LyricsManager，改为 import

- [ ] **Step 1: 创建 `src/lyrics/manager.py`**

从 `taskbar_lyrics.py:108-295` 重构，使用 provider 接口：

```python
"""
歌词管理器 — 缓存 + 加载 + 当前行匹配
"""

import re
import threading
from pathlib import Path
from typing import Optional, List, Callable

from src.lyrics.cache import cache_get, cache_set, load_disk_lyrics, save_disk_lyrics, disk_cache_key
from src.lyrics.providers.base import BaseLyricsProvider
from src.utils.log import log


class LyricsManager:
    """歌词管理器"""

    def __init__(self, providers: List[BaseLyricsProvider], local_dir=None):
        self.providers = providers
        self.local_dir = Path(local_dir) if local_dir else None
        self._cache = {}
        self._loading_key = ""

    def _cache_key(self, title: str, artist: str, album: str = "") -> str:
        return f"{artist}|{title}|{album}"

    @staticmethod
    def _variants(title: str, artist: str):
        """生成搜索变体"""
        vs = []
        parens = lambda t: re.findall(r'[（(]([^)）]+)[)）]', t)
        strip = lambda t: re.sub(r'\s*[（(][^)）]*[)）]', '', t).strip()
        ct, ca = strip(title), strip(artist)
        vs.append((title, artist))
        if ct:
            vs += [(ct, ca), (ct, "")]
        for a in parens(artist):
            vs.append((ct, a))
        for t in parens(title):
            if any(k in t.lower() for k in ["live", "ver", "remix", "inst", "cover"]):
                continue
            vs.append((t, ca))
        seen = set()
        return [(t, a) for t, a in vs if t.strip() and (t.strip(), a.strip()) not in seen
                and not seen.add((t.strip(), a.strip()))]

    def _try_local(self, title: str, artist: str) -> Optional[list]:
        """尝试从本地目录加载 LRC 文件"""
        if not self.local_dir or not self.local_dir.exists():
            return None
        ct = re.sub(r'\s*[（(][^)）]*[)）]', '', title).strip()
        ca = re.sub(r'\s*[（(][^)）]*[)）]', '', artist).strip()
        for n in [f"{artist} - {title}.lrc", f"{title}.lrc", f"{ca} - {ct}.lrc", f"{ct}.lrc"]:
            p = self.local_dir / n
            if p.exists():
                try:
                    text = p.read_text(encoding="utf-8")
                    from src.lyrics.parsers import parse_lrc
                    return [(t, x, "", []) for t, x in parse_lrc(text)]
                except Exception:
                    pass
        return None

    def _fetch_online(self, title: str, artist: str, album: str = "") -> Optional[list]:
        """使用 provider 列表获取歌词"""
        for provider in self.providers:
            log(f"    [LyricsProvider] {provider.__class__.__name__} 搜索: {artist} - {title}" + (f" (专辑: {album})" if album else ""))
            song_info = provider.search(title, artist, album)
            if not song_info:
                continue
            song_id = song_info.get("songID", 0)
            cache_key = f"lyrics:{song_id}"
            cached = cache_get(cache_key)
            if cached is not None:
                log(f"\n[LyricsProvider] 缓存命中(songID={song_id})")
                if cached == "__NONE__":
                    return None
                return cached
            lyrics = provider.get_lyrics(song_info)
            if lyrics:
                cache_set(cache_key, lyrics)
                has_trans = sum(1 for item in lyrics if len(item) > 2 and item[2])
                has_word = sum(1 for item in lyrics if len(item) > 3 and item[3])
                log(f"  >> 获取成功: {len(lyrics)} 行"
                    + (" [逐字]" if has_word > 0 else "")
                    + (" [翻译]" if has_trans > 0 else ""))
                return lyrics
            cache_set(cache_key, "__NONE__")
        return None

    def load_async(self, title: str, artist: str, cb: Callable, album: str = ""):
        key = self._cache_key(title, artist, album)
        if key in self._cache:
            cb(self._cache[key])
            return
        if self._loading_key == key:
            return

        # 先尝试磁盘缓存
        dk = disk_cache_key(title, artist, album)
        cached = load_disk_lyrics(dk)
        if cached is not None:
            self._cache[key] = cached
            log(f"[Cache] 命中磁盘缓存: {len(cached)} 行")
            cb(cached)
            return

        self._loading_key = key

        def w():
            log(f"\n[Lyrics] {artist} - {title}" + (f" ({album})" if album else ""))
            ly = self._try_local(title, artist) or self._fetch_online(title, artist, album) or []
            if ly:
                save_disk_lyrics(dk, ly)
                log(f"[Cache] 写入磁盘缓存: {len(ly)} 行")
            self._cache[key] = ly
            self._loading_key = ""
            log(f"[Lyrics] {len(ly)} 行")
            cb(ly)

        threading.Thread(target=w, daemon=True).start()

    def get_current_line(self, lyrics: list, position_ms: int) -> tuple:
        """返回 (原文, 翻译, progress 0.0~1.0)"""
        if not lyrics:
            return ("♪ 暂无歌词 ♪", "", 0.0)

        idx = -1
        for i, item in enumerate(lyrics):
            if item[0] <= position_ms:
                idx = i
            else:
                break

        if idx < 0:
            return (lyrics[0][1], lyrics[0][2] if len(lyrics[0]) > 2 else "", 0.0)

        item = lyrics[idx]
        orig = item[1]
        trans = item[2] if len(item) > 2 else ""
        word_timings = item[3] if len(item) > 3 else []

        if word_timings:
            line_start = item[0]
            abs_position = position_ms - line_start
            if abs_position < 0:
                progress = 0.0
            else:
                elapsed_chars = 0
                total_chars = len(word_timings)
                for char_offset, char_dur, _ in word_timings:
                    char_end = char_offset + char_dur
                    if abs_position >= char_end:
                        elapsed_chars += 1
                    elif abs_position > char_offset:
                        elapsed_chars += (abs_position - char_offset) / char_dur
                        break
                    else:
                        break
                progress = elapsed_chars / total_chars if total_chars > 0 else 0.0
            progress = max(0.0, min(1.0, progress))
        else:
            t0 = lyrics[idx][0]
            t1 = lyrics[idx + 1][0] if idx + 1 < len(lyrics) else t0 + 5000
            d = t1 - t0
            progress = max(0.0, min(1.0, (position_ms - t0) / d)) if d > 0 else 1.0

        return (orig, trans, progress)
```

- [ ] **Step 2: 更新 `taskbar_lyrics.py`**

删除 `taskbar_lyrics.py:108-295` 的 `LyricsManager` 类定义（包含 `_cache_key`, `_cache_path`, `_load_cache`, `_save_cache`, `_parse_lrc`, `_try_local`, `_variants`, `_fetch_online`, `load_async`, `get_current_line`），替换为：

```python
from src.lyrics.manager import LyricsManager
```

- [ ] **Step 3: 提交**

```bash
git add src/lyrics/manager.py taskbar_lyrics.py
git commit -m "refactor: move LyricsManager to src/lyrics/manager.py with provider interface"
```

---

### Task 9: 搬移 MediaInfoProvider

**Files:**
- Create: `src/media/provider.py`
- Modify: `taskbar_lyrics.py` — 删除旧 MediaInfoProvider，改为 import

- [ ] **Step 1: 创建 `src/media/provider.py`**

从 `taskbar_lyrics.py:53-102` 搬移：

```python
"""
媒体信息 Provider — Windows GSMTC API 轮询
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

    async def _fetch(self):
        try:
            from winsdk.windows.media.control import \
                GlobalSystemMediaTransportControlsSessionManager as SM
            mgr = await SM.request_async()
            s = mgr.get_current_session()
            if not s:
                return None
            p = await s.try_get_media_properties_async()
            tl = s.get_timeline_properties()
            return {"title": p.title or "", "artist": p.artist or "",
                    "album": getattr(p, 'album_title', '') or "",
                    "position_ms": int(tl.position.total_seconds() * 1000),
                    "duration_ms": int(tl.end_time.total_seconds() * 1000)}
        except Exception:
            return None

    def _poll(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        fails = 0
        while self._running:
            r = loop.run_until_complete(self._fetch())
            if r:
                with self._lock:
                    self._info = r
                    self._update_ts = time.time()
                fails = 0
            else:
                fails += 1
                if fails >= 10:
                    with self._lock:
                        self._info = {"title": "", "artist": "", "position_ms": 0, "duration_ms": 0}
                    fails = 0
            time.sleep(0.5)

    def start(self):
        self._running = True
        threading.Thread(target=self._poll, daemon=True).start()

    def stop(self):
        self._running = False

    def get_info(self):
        with self._lock:
            info = self._info.copy()
            ts = self._update_ts
        if info["title"] and ts > 0:
            info["position_ms"] = int(info["position_ms"] + (time.time() - ts) * 1000)
        return info
```

- [ ] **Step 2: 更新 `taskbar_lyrics.py`**

删除 `taskbar_lyrics.py:53-102` 的 `MediaInfoProvider` 类，替换为：

```python
from src.media.provider import MediaInfoProvider
```

- [ ] **Step 3: 提交**

```bash
git add src/media/provider.py taskbar_lyrics.py
git commit -m "refactor: move MediaInfoProvider to src/media/provider.py"
```

---

### Task 10: 拆分显示层

**Files:**
- Create: `src/display/config.py`
- Create: `src/display/window.py`
- Create: `src/display/karaoke.py`
- Modify: `taskbar_lyrics.py` — 删除旧显示代码，改为 import

- [ ] **Step 1: 创建 `src/display/karaoke.py`**

从 `taskbar_lyrics.py:513-658` 搬移卡拉OK渲染引擎：

```python
"""
像素级卡拉OK渲染引擎 — 3 Canvas text item + 边界渐变
"""

import bisect
import tkinter as tk
from tkinter import font as tkfont


class KaraokeEngine:
    """像素级卡拉OK渲染"""

    def __init__(self, canvas: tk.Canvas, colors: dict, fonts: dict):
        self.canvas = canvas
        self.colors = colors
        self.fonts = fonts

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

    def update_display(self, orig: str, trans: str, progress: float):
        # // 是 QQ 音乐日文歌词的翻译分隔线，视为无效
        if trans in ("", "//"):
            trans = ""
        display = trans if trans else (orig or "♪ 等待播放 ♪")

        if display != self._text:
            self._text = display
            self._last_split = -1
            self._last_mid_color = ""
            self._rebuild(display)

        self._paint(display, progress)

    def _rebuild(self, text: str):
        """文本变化时：重建 Canvas 元素 + 预计算字符宽度"""
        self.canvas.delete("all")
        self._sung_id = self._mid_id = self._unsung_id = None
        if not text:
            return

        ft = self.fonts.get("lyric", ("Microsoft YaHei UI", 14, "bold"))
        if isinstance(ft, list):
            ft = tuple(ft)
        self._font_obj = tkfont.Font(family=ft[0], size=ft[1],
                                     weight=ft[2] if len(ft) > 2 else "normal")

        cum = [0]
        for ch in text:
            cum.append(cum[-1] + self._font_obj.measure(ch))
        self._cum_widths = cum
        self._total_px = cum[-1]

        cy = 21
        col_sung = self.colors.get("sung", "#FFD700")
        col_unsung = self.colors.get("unsung", "#555566")

        self._sung_id = self.canvas.create_text(0, cy, text="",
                                                 fill=col_sung, font=ft, anchor="w")
        self._mid_id = self.canvas.create_text(0, cy, text="",
                                                fill=col_unsung, font=ft, anchor="w")
        self._unsung_id = self.canvas.create_text(0, cy, text=text,
                                                   fill=col_unsung, font=ft, anchor="w")

    def _paint(self, text: str, progress: float):
        """每帧更新：像素级分割 + 边界渐变"""
        if not text or not self._sung_id:
            return

        progress = max(0.0, min(1.0, progress))
        highlight_px = self._total_px * progress
        cw = self._canvas_w or 860
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
            x0 = (cw - self._total_px) / 2
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
    def _lerp_color(c1: str, c2: str, t: float) -> str:
        """线性插值两个 hex 颜色"""
        def norm_color(c):
            if not c or not isinstance(c, str) or not c.startswith('#'):
                return None
            if len(c) == 7:
                return c
            if len(c) == 4:
                return f"#{c[1]*2}{c[2]*2}{c[3]*2}"
            return None

        c1n = norm_color(c1) or "#FFD700"
        c2n = norm_color(c2) or "#555566"
        r1, g1, b1 = int(c1n[1:3], 16), int(c1n[3:5], 16), int(c1n[5:7], 16)
        r2, g2, b2 = int(c2n[1:3], 16), int(c2n[3:5], 16), int(c2n[5:7], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"
```

- [ ] **Step 2: 创建 `src/display/config.py`**

从 `taskbar_lyrics.py:661-736` 搬移配置相关代码：

```python
"""
配置加载/保存 + 配置 UI 弹窗
"""

import json
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path.home() / ".taskbar_lyrics_config.json"


def load_config() -> Dict[str, Any]:
    try:
        if CONFIG_FILE.exists():
            return json.load(open(CONFIG_FILE, "r", encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_config(config: dict):
    try:
        json.dump(config, open(CONFIG_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception:
        pass


def show_offset_config(parent, config, colors, save_fn):
    """歌词偏移设置弹窗"""
    win = tk.Toplevel(parent)
    win.title("歌词偏移")
    win.geometry("360x140")
    win.configure(bg="#2a2a3e")
    win.transient(parent)
    win.grab_set()

    f = tk.Frame(win, bg="#2a2a3e")
    f.pack(fill=tk.X, padx=20, pady=12)
    tk.Label(f, text="偏移(ms)", fg="#FFF", bg="#2a2a3e",
             font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)

    vs = tk.IntVar(value=config.get("lyric_offset_ms", 200))
    tk.Spinbox(f, from_=-2000, to=2000, textvariable=vs, width=6,
               font=("Consolas", 11)).pack(side=tk.LEFT, padx=8)
    tk.Label(f, text="(正数=歌词提前，负数=歌词推后)", fg="#aaa", bg="#2a2a3e",
             font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT, padx=4)

    bf = tk.Frame(win, bg="#2a2a3e")
    bf.pack(fill=tk.X, padx=20, pady=10)

    def apply():
        config["lyric_offset_ms"] = vs.get()
        save_fn()
        win.destroy()

    tk.Button(bf, text="应用", command=apply, bg="#4a4a6e", fg="#FFF",
              width=10).pack(side=tk.LEFT)
    tk.Button(bf, text="关闭", command=win.destroy, bg="#6a4a4e", fg="#FFF",
              width=10).pack(side=tk.RIGHT)


def show_color_config(parent, colors, save_fn):
    """颜色设置弹窗"""
    win = tk.Toplevel(parent)
    win.title("颜色")
    win.geometry("380x280")
    win.configure(bg="#2a2a3e")
    win.transient(parent)
    win.grab_set()

    cv = {}
    for lb, k in [("背景色", "bg"), ("已唱(高亮)", "sung"), ("未唱(暗色)", "unsung")]:
        f = tk.Frame(win, bg="#2a2a3e")
        f.pack(fill=tk.X, padx=20, pady=6)
        tk.Label(f, text=lb, fg="#FFF", bg="#2a2a3e",
                 font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
        v = tk.StringVar(value=colors.get(k, "#666"))
        cv[k] = v
        tk.Entry(f, textvariable=v, width=9, font=("Consolas", 11)).pack(side=tk.LEFT, padx=8)
        pv = tk.Label(f, text="  ", bg=colors.get(k, "#666"), width=3, relief=tk.RIDGE)
        pv.pack(side=tk.LEFT)
        v.trace_add("write", lambda *a, p=pv, vv=v: p.config(bg=vv.get()))

    bf = tk.Frame(win, bg="#2a2a3e")
    bf.pack(fill=tk.X, padx=20, pady=12)

    def apply():
        for k, v in cv.items():
            colors[k] = v.get()
        save_fn()
        win.destroy()

    tk.Button(bf, text="应用", command=apply, bg="#4a4a6e", fg="#FFF",
              width=10).pack(side=tk.LEFT)
    tk.Button(bf, text="关闭", command=win.destroy, bg="#6a4a4e", fg="#FFF",
              width=10).pack(side=tk.RIGHT)


def show_font_config(parent, fonts, save_fn):
    """字体设置弹窗"""
    win = tk.Toplevel(parent)
    win.title("字体")
    win.geometry("420x160")
    win.configure(bg="#2a2a3e")
    win.transient(parent)
    win.grab_set()

    FONTS = ["Microsoft YaHei UI", "微软雅黑", "SimHei", "黑体", "Consolas", "Segoe UI", "Arial"]
    try:
        af = FONTS + [f for f in tkfont.families() if f not in FONTS]
    except Exception:
        af = FONTS

    cur = fonts.get("lyric", ("Microsoft YaHei UI", 14, "bold"))
    if isinstance(cur, list):
        cur = tuple(cur)

    f = tk.Frame(win, bg="#2a2a3e")
    f.pack(fill=tk.X, padx=20, pady=10)
    vf = tk.StringVar(value=cur[0])
    vs = tk.IntVar(value=cur[1])
    vb = tk.BooleanVar(value=len(cur) > 2 and cur[2] == "bold")

    tk.Label(f, text="字体", fg="#FFF", bg="#2a2a3e").pack(side=tk.LEFT)
    om = tk.OptionMenu(f, vf, *af)
    om.config(width=14, bg="#4a4a6e", fg="#FFF")
    om.pack(side=tk.LEFT, padx=5)
    tk.Spinbox(f, from_=8, to=36, textvariable=vs, width=4).pack(side=tk.LEFT, padx=5)
    tk.Checkbutton(f, text="粗", variable=vb, bg="#2a2a3e", fg="#FFF",
                   selectcolor="#4a4a6e").pack(side=tk.LEFT)

    bf = tk.Frame(win, bg="#2a2a3e")
    bf.pack(fill=tk.X, padx=20, pady=10)

    def apply():
        fonts["lyric"] = (vf.get(), vs.get(), "bold" if vb.get() else "normal")
        save_fn()
        win.destroy()

    tk.Button(bf, text="应用", command=apply, bg="#4a4a6e", fg="#FFF",
              width=10).pack(side=tk.LEFT)
    tk.Button(bf, text="关闭", command=win.destroy, bg="#6a4a4e", fg="#FFF",
              width=10).pack(side=tk.RIGHT)
```

- [ ] **Step 3: 创建 `src/display/window.py`**

从 `taskbar_lyrics.py:302-485` 搬移窗口逻辑，使用 KaraokeEngine 和 config 模块：

```python
"""
TaskbarLyricsWindow — Tkinter 窗口生命周期
"""

import ctypes
import tkinter as tk
from pathlib import Path

from src.display.config import load_config, save_config, CONFIG_FILE
from src.display.karaoke import KaraokeEngine
from src.display.config import show_offset_config, show_color_config, show_font_config
from src.utils.log import log


class TaskbarLyricsWindow:
    DEFAULT_COLORS = {"bg": "#1a1a2e", "sung": "#FFD700", "unsung": "#555566"}
    DEFAULT_FONTS = {"lyric": ("Microsoft YaHei UI", 14, "bold")}

    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        self.root = tk.Tk()
        self.root.title("TaskbarLyrics")
        self._config = load_config()
        self._colors = self._config.get("colors", self.DEFAULT_COLORS.copy())
        self._fonts = self._config.get("fonts", self.DEFAULT_FONTS.copy())

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        ww, wh = min(900, sw - 200), 42
        pos = self._config.get("position", {})
        x = max(0, min(pos.get("x", (sw - ww) // 2), sw - ww))
        y = max(0, min(pos.get("y", sh - wh - 50), sh - wh))
        self.root.geometry(f"{ww}x{wh}+{x}+{y}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=self._colors["bg"])
        self.root.after(100, self._setup_style)
        self.root.after(500, self._ensure_topmost)

        # ---- Canvas ----
        self.canvas = tk.Canvas(self.root, bg=self._colors["bg"],
                                height=wh, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=12)

        # Karaoke 引擎
        self.karaoke = KaraokeEngine(self.canvas, self._colors, self._fonts)

        # 拖拽
        self._drag = {"x": 0, "y": 0}
        self.canvas.bind("<Button-1>", lambda e: self._drag.update(x=e.x, y=e.y))
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
        self.root.bind("<Button-3>", self._show_menu)
        self._ct = False
        self._debug_mode = False
        self._debug_label = None
        self._lyric_offset_ms = self._config.get("lyric_offset_ms", 200)

        # 键盘快捷键
        self.root.bind("<Up>", lambda e: self._nudge_offset(50))
        self.root.bind("<Down>", lambda e: self._nudge_offset(-50))
        self.root.bind("<Shift-Up>", lambda e: self._nudge_offset(10))
        self.root.bind("<Shift-Down>", lambda e: self._nudge_offset(-10))
        self.root.bind("<Configure>", self._on_move)
        self.root.bind("<FocusOut>", lambda e: self._restore_topmost())

    # ---- 窗口管理方法（从 taskbar_lyrics.py:378-485 搬移）----
    def _show_menu(self, event):
        import ctypes
        try:
            spi = ctypes.windll.user32.SystemParametersInfoW
            work_area = ctypes.c_int * 4
            wa = work_area()
            spi(0x0030, 0, wa, 0)
            screen_bottom = wa[3]
        except Exception:
            screen_bottom = self.root.winfo_screenheight()
        x, y = event.x_root, event.y_root
        self.menu.post(x, y)
        self.menu.update()
        actual_h = self.menu.winfo_height()
        if y + actual_h > screen_bottom:
            self.menu.unpost()
            self.menu.post(x, screen_bottom - actual_h)

    def _hwnd(self):
        try:
            h = ctypes.windll.user32.FindWindowW(None, "TaskbarLyrics")
            return h or self.root.winfo_id()
        except Exception:
            return None

    def _setup_style(self):
        try:
            h = self._hwnd()
            if not h:
                return
            s = ctypes.windll.user32.GetWindowLongW(h, -20)
            s |= 0x08000000 | 0x00000080
            ctypes.windll.user32.SetWindowLongW(h, -20, s)
            ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
        except Exception:
            pass

    def _restore_topmost(self):
        try:
            h = self._hwnd()
            if h:
                ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0,
                                                  0x0001 | 0x0002 | 0x0010 | 0x0040)
                self.root.attributes("-topmost", True)
        except Exception:
            pass

    def _ensure_topmost(self):
        try:
            h = self._hwnd()
            if h:
                ctypes.windll.user32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
                self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.after(500, self._ensure_topmost)

    def _drag_move(self, e):
        self.root.geometry(f"+{self.root.winfo_x() + e.x - self._drag['x']}+"
                           f"{self.root.winfo_y() + e.y - self._drag['y']}")

    def _on_move(self, e):
        if e.widget == self.root:
            if hasattr(self, '_sid'):
                self.root.after_cancel(self._sid)
            self._sid = self.root.after(500, self._save_pos)

    def _save_pos(self):
        try:
            self._config["position"] = {"x": self.root.winfo_x(), "y": self.root.winfo_y()}
            self._save_config()
        except Exception:
            pass

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
        except Exception:
            pass

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
        log(f"[Offset] {self._lyric_offset_ms}ms ({'+' if delta > 0 else ''}{delta})")

    def _quit(self):
        self.root.quit()
        self.root.destroy()

    def _offset_cfg(self):
        show_offset_config(self.root, self._config, self._colors, self._save_config)

    def _color_cfg(self):
        show_color_config(self.root, self._colors, self._save_config)

    def _font_cfg(self):
        show_font_config(self.root, self._fonts, self._save_config)

    def _save_config(self):
        self._config["colors"] = self._colors
        self._config["fonts"] = self._fonts
        self._config["lyric_offset_ms"] = self._lyric_offset_ms
        save_config(self._config)

    def run(self):
        self.root.mainloop()
```

- [ ] **Step 4: 提交**

```bash
git add src/display/karaoke.py src/display/config.py src/display/window.py
git commit -m "refactor: split display layer into config/window/karaoke modules"
```

---

### Task 11: 瘦身 taskbar_lyrics.py 为纯入口

**Files:**
- Modify: `taskbar_lyrics.py` — 删除所有已搬移的类定义，只保留 TaskbarLyricsApp

- [ ] **Step 1: 重写 `taskbar_lyrics.py`**

将 `taskbar_lyrics.py` 重写为纯入口文件：

```python
"""
Windows 任务栏歌词 — 模块化架构
入口文件，组装各模块
"""

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
        self.window = TaskbarLyricsWindow()
        self._last_song = ""
        self._ly = []
        self._loading = False

    def _on_loaded(self, ly):
        def a():
            self._ly = ly
            self._loading = False
            print(f"[App] {len(ly)} 行")
        self.window.root.after(0, a)

    def _tick(self):
        try:
            info = self.media.get_info()
            title, artist, album = info["title"], info["artist"], info.get("album", "")
            pos_raw = info["position_ms"]
            pos = pos_raw - self.window._lyric_offset_ms
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
                    self.window.update_debug_info(pos_raw, pos, "loading...", 0.0)
                    self.window.karaoke.update_display("♪ 正在加载歌词...", "", 0.0)
                elif self._ly:
                    o, t, p = self.lyrics.get_current_line(self._ly, pos)
                    self.window.update_debug_info(pos_raw, pos, o, p)
                    self.window.karaoke.update_display(o, t, p)
                else:
                    self.window.update_debug_info(pos_raw, pos, "no lyrics", 0.0)
                    self.window.karaoke.update_display("♪ 暂无歌词 ♪", "", 0.0)
            else:
                self.window.karaoke.update_display("♪ 等待播放...", "", 0.0)
        except Exception as e:
            log(f"[Error] {e}")
        self.window.root.after(50, self._tick)

    def run(self):
        _init_log()
        log("=" * 50)
        log("  Windows 任务栏歌词 — 模块化架构")
        log("=" * 50)
        log("  左键拖拽 | 右键菜单 | 上下箭头调偏移 | 右键菜单开调试")
        log("")
        self.media.start()
        self.window.root.after(500, self._tick)
        try:
            self.window.run()
        finally:
            self.media.stop()


if __name__ == "__main__":
    TaskbarLyricsApp(local_dir=None).run()
```

- [ ] **Step 2: 删除旧文件（worktree 中）**

```bash
rm lyrics_api.py
```

- [ ] **Step 3: 完整功能测试**

```bash
python taskbar_lyrics.py
# 验证：能正常启动、获取媒体信息、加载歌词、显示卡拉OK
```

- [ ] **Step 4: 提交**

```bash
git add taskbar_lyrics.py
git rm lyrics_api.py
git commit -m "refactor: slim entry point, remove old lyrics_api.py"
```

---

### Task 12: 全局检查与清理

- [ ] **Step 1: 检查所有 import 无残留**

```bash
grep -rn "from lyrics_api" src/ taskbar_lyrics.py
grep -rn "import lyrics_api" src/ taskbar_lyrics.py
# 应无输出
```

- [ ] **Step 2: 检查无重复代码**

```bash
# 确认以下类只存在于 src/ 中
grep -c "class MediaInfoProvider" taskbar_lyrics.py src/media/provider.py
grep -c "class LyricsManager" taskbar_lyrics.py src/lyrics/manager.py
grep -c "class QQMusicProvider" taskbar_lyrics.py src/lyrics/providers/qq.py
grep -c "class TaskbarLyricsWindow" taskbar_lyrics.py src/display/window.py
# taskbar_lyrics.py 中应全部为 0
```

- [ ] **Step 3: 检查 __init__.py 导出**

确认各模块 `__init__.py` 有便利的重导出（可选，但有助于使用体验）：

```python
# src/__init__.py 无需内容

# src/utils/__init__.py
from src.utils.log import log, _init_log

# src/media/__init__.py
from src.media.provider import MediaInfoProvider

# src/lyrics/__init__.py
from src.lyrics.manager import LyricsManager
from src.lyrics.providers.base import BaseLyricsProvider

# src/lyrics/providers/__init__.py
from src.lyrics.providers.base import BaseLyricsProvider
from src.lyrics.providers.qq import QQMusicProvider

# src/display/__init__.py
from src.display.window import TaskbarLyricsWindow
```

- [ ] **Step 4: 最终功能测试**

```bash
python taskbar_lyrics.py
# 完整测试：播放歌曲 → 歌词加载 → 逐字高亮 → 翻译显示 → 拖拽 → 右键菜单 → 配置
```

- [ ] **Step 5: 提交最终版本**

```bash
git add src/
git commit -m "refactor: global cleanup, add __init__.py re-exports"
```

---

## 验证清单

所有任务完成后，以下功能应与重构前完全一致：

- [ ] `python taskbar_lyrics.py` 能正常启动
- [ ] GSMTC 能获取正在播放的媒体信息
- [ ] 歌曲切换时能自动加载歌词
- [ ] QQ 音乐搜索能正常返回结果
- [ ] QRC 逐字歌词能正常解密和解析
- [ ] 翻译歌词能正常显示
- [ ] 卡拉OK逐字高亮效果正常（像素级精度）
- [ ] 窗口可拖拽移动
- [ ] 右键菜单正常弹出
- [ ] 歌词偏移可调整（上下箭头）
- [ ] 颜色/字体配置可修改并保存
- [ ] 磁盘缓存能命中
- [ ] 内存缓存 TTL 过期正常