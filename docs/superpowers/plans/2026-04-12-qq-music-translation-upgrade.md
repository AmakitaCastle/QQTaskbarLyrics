# QQ 音乐翻译歌词升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 QQMusicAPI 使用 LDDC 的 musicu.fcg 接口获取 QRC 逐字歌词 + 官方翻译

**Architecture:** 在现有 `lyrics_api.py` 中替换 QQMusicAPI.get_lyrics() 为 musicu.fcg 调用，新增 QMC1 解密和 QRC 解析函数，保持对外返回格式不变

**Tech Stack:** Python 3, requests, re, base64, zlib

---

### Task 1: 升级 QQMusicAPI.search() 返回 songID

**Files:**
- Modify: `lyrics_api.py:30-131` (QQMusicAPI.search)

当前 `search()` 只返回 `mid`（字符串 ID），但 `GetPlayLyricInfo` 需要 `songID`（整数 ID）。从搜索结果中提取 `id` 字段。

- [ ] **Step 1: 修改 search() 返回值**

在 `lyrics_api.py` 中，修改 `QQMusicAPI.search()` 的 return 语句，增加 `"songID"` 字段。搜索结果中 `song.get("id")` 就是整数 songID。

修改前 (约第 125-131 行):
```python
            return {
                "id": best_match.get("mid"),
                "title": best_match.get("name"),
                "artist": best_match.get("singer", [{}])[0].get("name", ""),
                "album": best_match.get("album", {}).get("name", ""),
                "duration": best_match.get("interval", 0) * 1000
            }
```

修改后:
```python
            return {
                "id": best_match.get("mid"),
                "songID": best_match.get("id", 0),
                "title": best_match.get("name"),
                "artist": best_match.get("singer", [{}])[0].get("name", ""),
                "album": best_match.get("album", {}).get("name", ""),
                "duration": best_match.get("interval", 0) * 1000
            }
```

- [ ] **Step 2: 验证改动**

运行 `python lyrics_api.py` 确认搜索仍然正常工作，打印结果中应包含 `songID` 字段。

- [ ] **Step 3: 提交**

```bash
git add lyrics_api.py
git commit -m "feat: add songID to QQMusicAPI search results for GetPlayLyricInfo"
```

---

### Task 2: 实现 QMC1 解密函数

**Files:**
- Modify: `lyrics_api.py` (在文件顶部 imports 之后，class 定义之前添加)

QMC1 是 QQ 音乐 QRC 歌词的加密方式。128 字节固定密钥，逐字节 XOR。

- [ ] **Step 1: 添加 QMC1 解密函数**

在 `lyrics_api.py` 第 13 行（`from urllib.parse import quote` 之后）添加：

```python


# ============================================================
# QMC1 解密 — QQ 音乐 QRC 歌词解密
# ============================================================

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


def _qmc1_decrypt(data: bytearray) -> None:
    """原地解密 QMC1 加密数据"""
    for i in range(len(data)):
        if i > 0x7FFF:
            data[i] ^= _QMC1_PRIVKEY[(i % 0x7FFF) & 0x7F]
        else:
            data[i] ^= _QMC1_PRIVKEY[i & 0x7F]
```

- [ ] **Step 2: 添加 QRC 解析函数**

紧接在 `_qmc1_decrypt` 之后添加：

```python
_QRC_CONTENT_PATTERN = re.compile(
    r'<Lyric_1 LyricType="1" LyricContent="(?P<content>.*?)"/>',
    re.DOTALL
)
_QRC_LINE_PATTERN = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_QRC_WORD_PATTERN = re.compile(
    r"(?:\[\d+,\d+\])?(?P<content>(?:(?!\(\d+,\d+\)).)*)\((?P<start>\d+),(?P<duration>\d+)\)"
)


def _parse_qrc(qrc_text: str) -> List[Tuple[int, str, List]]:
    """解析 QRC 逐字歌词
    返回: [(time_ms, text, word_timings), ...]
    word_timings: [(char_start_ms, char_duration_ms, char), ...]
    """
    match = _QRC_CONTENT_PATTERN.search(qrc_text)
    if not match:
        # 回退到 LRC 解析
        return _parse_lrc_fallback(qrc_text)

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
                char_start = int(wm.group("start"))
                char_duration = int(wm.group("duration"))
                words.append((char_start, char_duration, char_text))
                text_parts.append(char_text)

        if not text_parts:
            continue

        full_text = "".join(text_parts)
        result.append((line_start, full_text, words))

    result.sort(key=lambda x: x[0])
    return result


def _parse_lrc_fallback(lrc_text: str) -> List[Tuple[int, str, List]]:
    """LRC 格式解析（QRC 解析失败时的回退）"""
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
```

- [ ] **Step 3: 验证解密和解析**

在文件末尾的 `if __name__ == "__main__":` 测试块中，添加一个解密测试（可选，手动验证）。

- [ ] **Step 4: 提交**

```bash
git add lyrics_api.py
git commit -m "feat: add QMC1 decryption and QRC parsing for QQ Music verbatim lyrics"
```

---

### Task 3: 实现 get_session() 方法

**Files:**
- Modify: `lyrics_api.py` (在 QQMusicAPI 类中添加 get_session 方法)

QQ 音乐新版 API 需要 session 凭证（uid/sid/userip），通过 `music.getSession.session` 模块获取。

- [ ] **Step 1: 添加 session 缓存和 get_session 方法**

在 `QQMusicAPI` 类的 `__init__` 方法（如果没有的话需要添加）和 `search` 方法之间，添加：

```python
    def __init__(self):
        self._session_cache = None
        self._session_time = 0

    def _get_session(self) -> Dict:
        """获取 QQ 音乐 session (uid, sid, userip)，缓存 30 分钟"""
        now = time.time()
        if self._session_cache and (now - self._session_time) < 1800:
            return self._session_cache

        try:
            import time as _time
            url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
            payload = {
                "req_0": {
                    "module": "music.getSession",
                    "method": "session",
                    "param": {}
                }
            }
            params = {
                "format": "json",
                "data": json.dumps(payload)
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://y.qq.com/"
            }
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            data = resp.json()

            req = data.get("req_0", {})
            session_data = req.get("data", {})
            self._session_cache = {
                "uid": session_data.get("uid", 0),
                "sid": session_data.get("sid", ""),
                "userip": session_data.get("userip", "")
            }
            self._session_time = _time.time()
            return self._session_cache
        except Exception as e:
            print(f"    [QQ Session] 获取失败: {e}")
            return {"uid": 0, "sid": "", "userip": ""}
```

- [ ] **Step 2: 添加 time import**

在文件顶部 imports 中添加 `import time`（如果尚未存在）。

- [ ] **Step 3: 提交**

```bash
git add lyrics_api.py
git commit -m "feat: add QQ Music session management with 30min cache"
```

---

### Task 4: 重写 get_lyrics() 使用 GetPlayLyricInfo

**Files:**
- Modify: `lyrics_api.py:136-191` (QQMusicAPI.get_lyrics 整个方法)

- [ ] **Step 1: 替换 get_lyrics() 方法**

将原有的 `get_lyrics()` 方法（第 136-191 行）替换为：

```python
    def get_lyrics(self, song_info: Dict) -> Optional[List[Tuple[int, str, str, List]]]:
        """获取歌词（QRC 逐字 + 翻译）
        返回: [(time_ms, text, translation, word_timings), ...]
        """
        song_id = song_info.get("songID", 0)
        if not song_id:
            print("    [QQ音乐歌词] 缺少 songID，回退到旧接口")
            return self._get_lyrics_legacy(song_info)

        session = self._get_session()
        album = song_info.get("album", "")
        singer = song_info.get("artist", "")
        duration = song_info.get("duration", 0) // 1000  # ms -> s

        try:
            import base64 as _b64
            url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
            payload = {
                "comm": {
                    "uin": session["uid"],
                    "sid": session["sid"],
                    "userip": session["userip"]
                },
                "GetPlayLyricInfo": {
                    "module": "music.musichallSong.PlayLyricInfo",
                    "method": "GetPlayLyricInfo",
                    "param": {
                        "songID": song_id,
                        "albumName": _b64.b64encode(album.encode()).decode() if album else "",
                        "singerName": _b64.b64encode(singer.encode()).decode() if singer else "",
                        "interval": duration,
                        "qrc": 1,
                        "trans": 1,
                        "roma": 0
                    }
                }
            }
            params = {"format": "json"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://y.qq.com/"
            }
            resp = requests.post(url, json=payload, params=params, headers=headers, timeout=15)
            data = resp.json()

            lyric_info = data.get("GetPlayLyricInfo", {})
            if lyric_info.get("code") != 0:
                print(f"    [QQ音乐歌词] API 错误: {lyric_info.get('msg', '')}")
                return self._get_lyrics_legacy(song_info)

            # 解密原文
            lyric_enc = lyric_info.get("lyric", "")
            trans_enc = lyric_info.get("trans", "")

            if not lyric_enc:
                return self._get_lyrics_legacy(song_info)

            # 解密
            lyric_bytes = base64.b64decode(lyric_enc)
            lyric_ba = bytearray(lyric_bytes)
            _qmc1_decrypt(lyric_ba)
            orig_text = lyric_ba.decode("utf-8")

            orig_lines = _parse_qrc(orig_text)

            # 解密翻译
            trans_map = {}
            if trans_enc:
                try:
                    trans_bytes = base64.b64decode(trans_enc)
                    trans_ba = bytearray(trans_bytes)
                    _qmc1_decrypt(trans_ba)
                    trans_text = trans_ba.decode("utf-8")
                    trans_lines = _parse_qrc(trans_text)
                    for time_ms, text, _ in trans_lines:
                        trans_map[time_ms] = text
                except Exception:
                    pass

            # 合并原文和翻译，保持逐字时间戳
            result = []
            for time_ms, text, word_timings in orig_lines:
                translation = trans_map.get(time_ms, "")
                result.append((time_ms, text, translation, word_timings))

            if not result:
                return self._get_lyrics_legacy(song_info)

            return result

        except Exception as e:
            print(f"    [QQ音乐歌词] 失败: {e}，回退到旧接口")
            return self._get_lyrics_legacy(song_info)
```

- [ ] **Step 2: 保留旧接口作为回退**

将原 `get_lyrics()` 方法重命名为 `_get_lyrics_legacy()`，并修改签名接受 `song_info` 字典：

```python
    def _get_lyrics_legacy(self, song_info: Dict) -> Optional[List[Tuple[int, str, str, List]]]:
        """旧版歌词接口（回退用）"""
        song_mid = song_info.get("id", "")
        # ... 保留原有 get_lyrics 的完整实现代码 ...
```

完整代码：

```python
    def _get_lyrics_legacy(self, song_info: Dict) -> Optional[List[Tuple[int, str, str, List]]]:
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
            if not lyric:
                return None

            trans = data.get("trans", "")
            orig_lines = self._parse_lrc(lyric)

            trans_map = {}
            if trans:
                for time_ms, t, _ in self._parse_lrc(trans):
                    trans_map[time_ms] = t

            result = []
            for time_ms, text, word_timings in orig_lines:
                translation = trans_map.get(time_ms, "")
                result.append((time_ms, text, translation, word_timings))

            return result

        except Exception as e:
            print(f"    [QQ音乐歌词(旧)] 失败: {e}")
            return None
```

- [ ] **Step 3: 修改 LyricsProvider 调用方式**

在 `LyricsProvider.get_lyrics()` 方法（约第 652-683 行）中，原来调用 `source.get_lyrics(song_info["id"])`，需要改为传递整个 `song_info` 字典：

修改前：
```python
                lyrics = source.get_lyrics(song_info["id"])
```

修改后：
```python
                lyrics = source.get_lyrics(song_info)
```

- [ ] **Step 4: 为其他 API 类添加兼容性包装**

`NeteaseAPI.get_lyrics()` 和 `LrclibAPI.get_lyrics()` 原来接受 `song_id: str`，需要改为接受 `song_info: Dict`（只使用 `song_info["id"]`）。

在 `NeteaseAPI.get_lyrics()` 方法签名处（约第 471 行），修改：

```python
    def get_lyrics(self, song_info: Dict) -> Optional[List[Tuple[int, str, str, List]]]:
        """获取歌词，返回 [(time_ms, text, translation, word_timings), ...]"""
        song_id = song_info.get("id", "") if isinstance(song_info, dict) else song_info
```

在 `LrclibAPI.get_lyrics()` 方法签名处（约第 579 行），修改：

```python
    def get_lyrics(self, song_info) -> Optional[List[Tuple[int, str, str, List]]]:
        """获取歌词"""
        song_id = song_info.get("id", "") if isinstance(song_info, dict) else song_info
```

- [ ] **Step 5: 提交**

```bash
git add lyrics_api.py
git commit -m "feat: upgrade QQ Music lyrics to QRC verbatim format with translation via GetPlayLyricInfo"
```

---

### Task 5: 端到端测试验证

**Files:**
- No file changes, just run tests

- [ ] **Step 1: 运行 lyrics_api.py 测试**

```bash
python lyrics_api.py
```

验证输出中包含翻译歌词（不再只有原文）。

- [ ] **Step 2: 运行 taskbar_lyrics.py 验证**

```bash
python taskbar_lyrics.py
```

播放一首 QQ 音乐的歌曲，确认：
1. 歌词能正常显示
2. 翻译歌词（如果有）能正确显示
3. 逐字高亮效果正常

- [ ] **Step 3: 测试回退机制**

验证当 session 获取失败或 API 返回错误时，能回退到旧接口而不崩溃。
