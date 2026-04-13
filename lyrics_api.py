"""
LDDC 核心 API 模块 - 多平台歌词获取
支持: QQ音乐(QRC)、酷狗音乐(KRC)、网易云音乐(LRC)、Lrclib
"""

import re
import json
import zlib
import base64
import time
import requests
from typing import List, Tuple, Optional, Dict
from urllib.parse import quote


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


class LyricsSource:
    """歌词数据源基类"""
    
    def search(self, title: str, artist: str = "") -> Optional[Dict]:
        """搜索歌曲，返回最佳匹配结果"""
        raise NotImplementedError
    
    def get_lyrics(self, song_id: str) -> Optional[List[Tuple[int, str, List]]]:
        """获取歌词，返回 [(time_ms, text, word_timings), ...]"""
        raise NotImplementedError


class QQMusicAPI(LyricsSource):
    """QQ音乐 API - 支持歌词获取"""

    def __init__(self):
        self._session_cache = None
        self._session_time = 0

    def _get_session(self) -> Dict:
        """获取 QQ 音乐 session (uid, sid, userip)，缓存 30 分钟"""
        now = time.time()
        if self._session_cache and (now - self._session_time) < 1800:
            return self._session_cache

        try:
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
            self._session_time = time.time()
            return self._session_cache
        except Exception as e:
            print(f"    [QQ Session] 获取失败: {e}")
            return {"uid": 0, "sid": "", "userip": ""}

    def search(self, title: str, artist: str = "", album: str = "") -> Optional[Dict]:
        """搜索歌曲，尝试找到最佳匹配"""
        query = f"{title} {artist}".strip()
        print(f"    [QQ搜索] query='{query}'")

        try:
            # 使用 musicu 接口搜索
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
            
            req_1 = data.get("req_1", {})
            body = req_1.get("data", {})
            songs = body.get("body", {}).get("song", {}).get("list", [])

            if not songs:
                print(f"    [QQ搜索] 无结果")
                return None

            # 打印前3个搜索结果
            for i, song in enumerate(songs[:3]):
                s_title = song.get("name", "")
                s_artist = song.get("singer", [{}])[0].get("name", "")
                s_album = song.get("album", {}).get("name", "")
                print(f"    [QQ搜索] 结果{i+1}: {s_title} - {s_artist} (专辑: {s_album})")

            # 尝试找到最佳匹配 — 打分制
            title_lower = title.lower().replace(" ", "")
            artist_lower = artist.lower().replace(" ", "") if artist else ""

            best_match = None
            best_score = -1

            for song in songs:
                song_title = song.get("name", "").lower().replace(" ", "")
                song_artist = song.get("singer", [{}])[0].get("name", "").lower().replace(" ", "")

                # 跳过翻唱、cover、remix等版本
                skip_keywords = ['cover', 'remix', '翻唱', '改编', '版本', 'ver.', 'live']
                song_name = song.get("name", "").lower()
                if any(kw in song_name for kw in skip_keywords):
                    continue

                score = 0
                clean_title = song_title.replace("-", "").replace("_", "").replace("~", "")
                clean_target = title_lower.replace("-", "").replace("_", "").replace("~", "")

                # 标题匹配打分
                if clean_title == clean_target:
                    score += 100  # 完全匹配
                elif clean_title.startswith(clean_target) or clean_target.startswith(clean_title):
                    score += 60   # 前缀匹配
                elif title_lower in song_title or song_title in title_lower:
                    score += 30   # 包含匹配
                else:
                    continue  # 标题都不匹配，跳过

                # 艺术家匹配打分
                if artist_lower and song_artist:
                    clean_artist = song_artist.replace("-", "").replace("_", "")
                    clean_target_artist = artist_lower.replace("-", "").replace("_", "")
                    if clean_artist == clean_target_artist:
                        score += 50  # 艺术家完全匹配
                    elif clean_target_artist in clean_artist or clean_artist in clean_target_artist:
                        score += 30  # 艺术家部分匹配

                # 专辑名匹配加分
                if album:
                    song_album = song.get("album", {}).get("name", "").lower()
                    clean_album = album.lower().replace(" ", "")
                    clean_song_album = song_album.replace(" ", "")
                    if clean_album == clean_song_album:
                        score += 80  # 专辑完全匹配
                        print(f"    [QQ匹配] 专辑匹配成功: {song.get('name')} - {song_artist}")
                    elif clean_album in clean_song_album or clean_song_album in clean_album:
                        score += 40  # 专辑包含

                if score > best_score:
                    best_score = score
                    best_match = song
                    print(f"    [QQ匹配] 得分{score}: {song.get('name')} - {song_artist}")

            if not best_match:
                for song in songs:
                    song_name = song.get("name", "").lower()
                    skip_keywords = ['cover', 'remix', '翻唱', '改编', '版本', 'ver.', 'live']
                    if not any(kw in song_name for kw in skip_keywords):
                        best_match = song
                        print(f"    [QQ匹配] 默认选择: {song.get('name')} - {song.get('singer', [{}])[0].get('name', '')}")
                        break
                if not best_match:
                    best_match = songs[0]

            print(f"    [QQ匹配] 最终选择(score={best_score}): {best_match.get('name')} - {best_match.get('singer', [{}])[0].get('name', '')}")
            
            return {
                "id": best_match.get("mid"),
                "songID": best_match.get("id", 0),
                "title": best_match.get("name"),
                "artist": best_match.get("singer", [{}])[0].get("name", ""),
                "album": best_match.get("album", {}).get("name", ""),
                "duration": best_match.get("interval", 0) * 1000
            }
        except Exception as e:
            print(f"    [QQ音乐搜索] 失败: {e}")
            return None
    
    def get_lyrics(self, song_info: Dict) -> Optional[List[Tuple[int, str, str, List]]]:
        """获取歌词（优先旧接口，QRC 需登录）
        返回: [(time_ms, text, translation, word_timings), ...]
        """
        print(f"    [QQ音乐歌词] 开始获取歌词: songID={song_info.get('songID', 0)}, songMID={song_info.get('id', '')}")
        # 先尝试旧接口（无需登录，稳定）
        result = self._get_lyrics_legacy(song_info)
        if result:
            has_trans = sum(1 for _, _, tr, _ in result if tr)
            print(f"    [QQ音乐歌词] 旧接口成功: {len(result)} 行, 翻译 {has_trans} 行")
            return result
        else:
            print(f"    [QQ音乐歌词] 旧接口返回 None")

        # 旧接口失败，尝试 GetPlayLyricInfo（需要 session）
        print("    [QQ音乐歌词] 旧接口无歌词，尝试 GetPlayLyricInfo...")
        song_id = song_info.get("songID", 0)
        if not song_id:
            print(f"    [QQ音乐歌词] 缺少 songID (当前值: {song_id})，无法调用 GetPlayLyricInfo")
            return None

        session = self._get_session()
        print(f"    [QQ音乐歌词] session: uid={session.get('uid')}, sid={session.get('sid', '')[:8]}***, userip={session.get('userip', '')}")
        if not session.get("sid"):
            print("    [QQ音乐歌词] 无 session(sid为空)，无法获取 QRC 歌词")
            return None

        album = song_info.get("album", "")
        singer = song_info.get("artist", "")
        duration = song_info.get("duration", 0) // 1000

        try:
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
                        "albumName": base64.b64encode(album.encode()).decode() if album else "",
                        "singerName": base64.b64encode(singer.encode()).decode() if singer else "",
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
            lyric_code = lyric_info.get("code", "unknown")
            print(f"    [QQ音乐歌词] GetPlayLyricInfo 响应 code={lyric_code}")

            if lyric_info.get("code") != 0:
                print(f"    [QQ音乐歌词] API 错误: {lyric_info.get('msg', '')}")
                return None

            lyric_enc = lyric_info.get("lyric", "")
            trans_enc = lyric_info.get("trans", "")
            print(f"    [QQ音乐歌词] lyric 长度={len(lyric_enc)}, trans 长度={len(trans_enc)}")

            if not lyric_enc:
                print(f"    [QQ音乐歌词] lyric 字段为空，完整响应: {json.dumps(lyric_info, ensure_ascii=False)[:500]}")
                return None

            # 解密
            lyric_bytes = base64.b64decode(lyric_enc)
            lyric_ba = bytearray(lyric_bytes)
            _qmc1_decrypt(lyric_ba)
            orig_text = lyric_ba.decode("utf-8")
            print(f"    [QQ音乐歌词] QRC 解密成功, 原文前100字: {orig_text[:100]}")

            orig_lines = _parse_qrc(orig_text)
            print(f"    [QQ音乐歌词] QRC 解析 {len(orig_lines)} 行")

            # 解密翻译
            trans_map = {}
            if trans_enc:
                try:
                    trans_bytes = base64.b64decode(trans_enc)
                    trans_ba = bytearray(trans_bytes)
                    _qmc1_decrypt(trans_ba)
                    trans_text = trans_ba.decode("utf-8")
                    print(f"    [QQ音乐歌词] 翻译解密成功, 前100字: {trans_text[:100]}")
                    trans_lines = _parse_qrc(trans_text)
                    for time_ms, text, _ in trans_lines:
                        trans_map[time_ms] = text
                    print(f"    [QQ音乐歌词] 翻译解析 {len(trans_lines)} 行")
                except Exception as e:
                    print(f"    [QQ音乐歌词] 翻译解密失败: {e}")
            else:
                print(f"    [QQ音乐歌词] trans 字段为空，此歌曲无官方翻译")

            # 合并
            result = []
            for time_ms, text, word_timings in orig_lines:
                translation = trans_map.get(time_ms, "")
                result.append((time_ms, text, translation, word_timings))

            has_trans = sum(1 for _, _, tr, _ in result if tr)
            print(f"    [QQ音乐歌词] GetPlayLyricInfo 成功: {len(result)} 行, 翻译 {has_trans} 行")
            return result

        except Exception as e:
            print(f"    [QQ音乐歌词] GetPlayLyricInfo 失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_lyrics_legacy(self, song_info: Dict) -> Optional[List[Tuple[int, str, str, List]]]:
        """旧版歌词接口（回退用）"""
        song_mid = song_info.get("id", "")
        print(f"    [QQ音乐歌词(旧)] 请求 songmid={song_mid}")
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
            print(f"    [QQ音乐歌词(旧)] lyric 长度={len(lyric)}, trans 长度={len(trans_raw)}")
            if not lyric:
                print(f"    [QQ音乐歌词(旧)] lyric 为空，完整响应 keys: {list(data.keys())}")
                return None

            orig_lines = self._parse_lrc(lyric)
            print(f"    [QQ音乐歌词(旧)] 解析 {len(orig_lines)} 行原文")

            trans_map = {}
            if trans_raw:
                for time_ms, t, _ in self._parse_lrc(trans_raw):
                    trans_map[time_ms] = t
                print(f"    [QQ音乐歌词(旧)] 解析 {len(trans_map)} 行翻译")
            else:
                print(f"    [QQ音乐歌词(旧)] trans 字段为空")

            result = []
            for time_ms, text, word_timings in orig_lines:
                translation = trans_map.get(time_ms, "")
                result.append((time_ms, text, translation, word_timings))

            return result

        except Exception as e:
            print(f"    [QQ音乐歌词(旧)] 失败: {e}")
            return None
    
    def _parse_lrc(self, lrc_text: str) -> List[Tuple[int, str, List]]:
        """解析 LRC 歌词"""
        lines = []
        for line in lrc_text.splitlines():
            line = line.strip()
            if not line:
                continue
            
            # 匹配 [mm:ss.xx] 或 [mm:ss.xxx]
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


class KugouAPI(LyricsSource):
    """酷狗音乐 API - 支持 KRC 逐字歌词"""
    
    SEARCH_URL = "https://mobiles.kugou.com/api/v3/search/song"
    
    def search(self, title: str, artist: str = "", album: str = "") -> Optional[Dict]:
        """搜索歌曲"""
        query = f"{title} {artist}".strip()
        params = {
            "keyword": query,
            "page": 1,
            "pagesize": 10,
            "format": "json"
        }
        
        try:
            resp = requests.get(self.SEARCH_URL, params=params, timeout=10)
            data = resp.json()
            
            songs = data.get("data", {}).get("info", [])
            if not songs:
                return None
            
            song = songs[0]
            return {
                "id": song.get("hash"),
                "title": song.get("songname"),
                "artist": song.get("singername", ""),
                "album": song.get("album_name", ""),
                "duration": song.get("duration", 0) * 1000
            }
        except Exception as e:
            print(f"    [酷狗搜索] 失败: {e}")
            return None
    
    def get_lyrics(self, song_hash: str) -> Optional[List[Tuple[int, str, List]]]:
        """获取歌词 - 使用酷狗歌词 API"""
        try:
            # 使用酷狗公开的歌词 API
            url = "http://krcs.kugou.com/search"
            params = {
                "ver": 1,
                "man": "yes",
                "client": "mobi",
                "hash": song_hash
            }
            
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            
            candidate = candidates[0]
            access_key = candidate.get("accesskey")
            lyric_id = candidate.get("id")
            
            if not access_key or not lyric_id:
                return None
            
            # 下载歌词
            download_url = "http://krcs.kugou.com/download"
            params = {
                "ver": 1,
                "id": lyric_id,
                "accesskey": access_key,
                "fmt": "krc"
            }
            
            resp = requests.get(download_url, params=params, timeout=10)
            krc_data = resp.content
            
            # 解密 KRC
            return self._parse_krc(krc_data)
            
        except Exception as e:
            print(f"    [酷狗歌词] 失败: {e}")
            return None
    
    def _parse_krc(self, krc_data: bytes) -> Optional[List[Tuple[int, str, List]]]:
        """解析 KRC 加密歌词"""
        try:
            # 检查文件头
            if len(krc_data) < 4 or krc_data[:4] != b'krc1':
                # 尝试直接作为文本解析
                try:
                    text = krc_data.decode('utf-8')
                    return self._parse_lrc(text)
                except:
                    return None
            
            # 密钥
            key = [0x40, 0x47, 0x61, 0x77, 0x5e, 0x32, 0x76, 0x48]
            
            # 解密
            encrypted = krc_data[4:]
            decrypted = bytearray()
            for i, b in enumerate(encrypted):
                decrypted.append(b ^ key[i % len(key)])
            
            # 解压
            decompressed = zlib.decompress(decrypted)
            json_str = decompressed.decode("utf-8")
            
            data = json.loads(json_str)
            
            # 解析歌词
            lines = []
            for item in data.get("content", []):
                time_ms = int(item.get("time", 0))
                text = item.get("line", "").strip()
                
                if not text:
                    continue
                
                # 解析逐字时间
                word_timings = []
                for word in item.get("words", []):
                    char_start = int(word.get("start", 0))
                    char_duration = int(word.get("duration", 0))
                    char_text = word.get("word", "")
                    if char_text:
                        word_timings.append((char_start, char_duration, char_text))
                
                lines.append((time_ms, text, word_timings))
            
            lines.sort(key=lambda x: x[0])
            return lines
            
        except Exception as e:
            print(f"    [KRC解析] 失败: {e}")
            return None
    
    def _parse_lrc(self, lrc_text: str) -> List[Tuple[int, str, List]]:
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


class NeteaseAPI(LyricsSource):
    """网易云音乐 API - 支持 LRC + 翻译"""
    
    SEARCH_URL = "https://music.163.com/api/search/get/"
    LYRIC_URL = "https://music.163.com/api/song/lyric"
    
    HEADERS = {
        "Referer": "https://music.163.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    def search(self, title: str, artist: str = "", album: str = "") -> Optional[Dict]:
        """搜索歌曲，尝试找到最佳匹配"""
        query = f"{title} {artist}".strip()
        print(f"    [网易搜索] query='{query}'")
        params = {
            "s": query,
            "type": 1,
            "limit": 20,
            "offset": 0
        }
        
        try:
            resp = requests.post(self.SEARCH_URL, data=params, headers=self.HEADERS, timeout=10)
            data = resp.json()
            
            songs = data.get("result", {}).get("songs", [])
            if not songs:
                print(f"    [网易搜索] 无结果")
                return None

            # 打印前3个搜索结果
            for i, song in enumerate(songs[:3]):
                s_title = song.get("name", "")
                s_artist = song.get("artists", [{}])[0].get("name", "") if song.get("artists") else ""
                print(f"    [网易搜索] 结果{i+1}: {s_title} - {s_artist}")

            # 尝试找到最佳匹配 — 打分制
            title_lower = title.lower().replace(" ", "")
            artist_lower = artist.lower().replace(" ", "") if artist else ""

            best_match = None
            best_score = -1

            for song in songs:
                song_title = song.get("name", "").lower().replace(" ", "")
                song_artist = song.get("artists", [{}])[0].get("name", "").lower().replace(" ", "") if song.get("artists") else ""

                # 跳过翻唱、cover、remix等版本
                skip_keywords = ['cover', 'remix', '翻唱', '改编', '版本', 'ver.', 'live']
                song_name = song.get("name", "").lower()
                if any(kw in song_name for kw in skip_keywords):
                    continue

                score = 0
                clean_title = song_title.replace("-", "").replace("_", "").replace("~", "")
                clean_target = title_lower.replace("-", "").replace("_", "").replace("~", "")

                # 标题匹配打分
                if clean_title == clean_target:
                    score += 100  # 完全匹配
                elif clean_title.startswith(clean_target) or clean_target.startswith(clean_title):
                    score += 60   # 前缀匹配
                elif title_lower in song_title or song_title in title_lower:
                    score += 30   # 包含匹配
                else:
                    continue  # 标题都不匹配，跳过

                # 艺术家匹配打分
                if artist_lower and song_artist:
                    clean_artist = song_artist.replace("-", "").replace("_", "")
                    clean_target_artist = artist_lower.replace("-", "").replace("_", "")
                    if clean_artist == clean_target_artist:
                        score += 50  # 艺术家完全匹配
                    elif clean_target_artist in clean_artist or clean_artist in clean_target_artist:
                        score += 30  # 艺术家部分匹配
                    # 艺术家不匹配：不加分，但标题分数仍然有效
                elif not artist_lower:
                    score += 25  # 没有艺术家信息，给基础分

                # 专辑名匹配加分
                if album:
                    song_album = song.get("album", {}).get("name", "").lower()
                    clean_album = album.lower().replace(" ", "")
                    clean_song_album = song_album.replace(" ", "")
                    if clean_album == clean_song_album:
                        score += 80  # 专辑完全匹配
                        print(f"    [网易匹配] 专辑匹配成功: {song.get('name')} - {song_artist}")
                    elif clean_album in clean_song_album or clean_song_album in clean_album:
                        score += 40  # 专辑包含

                if score > best_score:
                    best_score = score
                    best_match = song
                    print(f"    [网易匹配] 得分{score}: {song.get('name')} - {song_artist}")

            if not best_match:
                # 无匹配，使用第一个非翻唱歌曲
                for song in songs:
                    song_name = song.get("name", "").lower()
                    skip_keywords = ['cover', 'remix', '翻唱', '改编', '版本', 'ver.', 'live']
                    if not any(kw in song_name for kw in skip_keywords):
                        best_match = song
                        print(f"    [网易匹配] 默认选择: {song.get('name')} - {song.get('artists', [{}])[0].get('name', '')}")
                        break
                if not best_match:
                    best_match = songs[0]

            print(f"    [网易匹配] 最终选择(score={best_score}): {best_match.get('name')} - {best_match.get('artists', [{}])[0].get('name', '')}")
            
            return {
                "id": str(best_match.get("id")),
                "title": best_match.get("name"),
                "artist": best_match.get("artists", [{}])[0].get("name", ""),
                "album": best_match.get("album", {}).get("name", ""),
                "duration": best_match.get("duration", 0)
            }
        except Exception as e:
            print(f"    [网易云搜索] 失败: {e}")
            return None
    
    def get_lyrics(self, song_info) -> Optional[List[Tuple[int, str, str, List]]]:
        """获取歌词，返回 [(time_ms, text, translation, word_timings), ...]"""
        song_id = song_info.get("id", "") if isinstance(song_info, dict) else song_info
        try:
            params = {
                "id": song_id,
                "lv": 1,
                "kv": 1,
                "tv": -1
            }
            
            resp = requests.get(self.LYRIC_URL, params=params, headers=self.HEADERS, timeout=10)
            data = resp.json()
            
            # 解析原文
            lrc_text = data.get("lrc", {}).get("lyric", "")
            if not lrc_text:
                return None
            
            orig_lines = self._parse_lrc(lrc_text)
            
            # 解析翻译
            trans_map = {}
            tlyric = data.get("tlyric", {}).get("lyric", "")
            if tlyric:
                for time_ms, text, _ in self._parse_lrc(tlyric):
                    trans_map[time_ms] = text
            
            # 合并
            result = []
            for time_ms, text, _ in orig_lines:
                trans = trans_map.get(time_ms, "")
                result.append((time_ms, text, trans, []))
            
            return result
            
        except Exception as e:
            print(f"    [网易云歌词] 失败: {e}")
            return None
    
    def _parse_lrc(self, lrc_text: str) -> List[Tuple[int, str, List]]:
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


class LrclibAPI(LyricsSource):
    """Lrclib 开源歌词库 API"""
    
    BASE_URL = "https://lrclib.net/api"
    
    def __init__(self):
        self._lyrics_cache = {}  # 缓存歌词数据

    def search(self, title: str, artist: str = "", album: str = "") -> Optional[Dict]:
        """搜索歌曲"""
        params = {
            "track_name": title
        }
        if artist:
            params["artist_name"] = artist
        
        try:
            resp = requests.get(f"{self.BASE_URL}/search", params=params, timeout=10)
            if resp.status_code != 200:
                return None
            
            results = resp.json()
            if not results:
                return None
            
            song = results[0]
            song_id = song.get("id")
            
            # 缓存歌词数据
            self._lyrics_cache[str(song_id)] = {
                "syncedLyrics": song.get("syncedLyrics", ""),
                "plainLyrics": song.get("plainLyrics", "")
            }
            
            return {
                "id": song_id,
                "title": song.get("trackName"),
                "artist": song.get("artistName", ""),
                "album": song.get("albumName", ""),
                "duration": song.get("duration", 0) * 1000
            }
        except Exception as e:
            print(f"    [Lrclib搜索] 失败: {e}")
            return None
    
    def get_lyrics(self, song_info) -> Optional[List[Tuple[int, str, str, List]]]:
        """获取歌词"""
        song_id = song_info.get("id", "") if isinstance(song_info, dict) else song_info
        try:
            # 优先从缓存获取
            cached = self._lyrics_cache.get(str(song_id))
            if cached:
                synced = cached.get("syncedLyrics", "")
                if synced:
                    return self._parse_lrc(synced)
                plain = cached.get("plainLyrics", "")
                if plain:
                    return [(0, line, "", []) for line in plain.splitlines() if line.strip()]
            
            # 缓存未命中，尝试API获取
            resp = requests.get(f"{self.BASE_URL}/songs/{song_id}", timeout=10)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            
            # 优先使用逐字同步歌词
            synced = data.get("syncedLyrics", "")
            if synced:
                return self._parse_lrc(synced)
            
            # 回退到纯文本
            plain = data.get("plainLyrics", "")
            if plain:
                return [(0, line, "", []) for line in plain.splitlines() if line.strip()]
            
            return None
            
        except Exception as e:
            print(f"    [Lrclib歌词] 失败: {e}")
            return None
    
    def _parse_lrc(self, lrc_text: str) -> List[Tuple[int, str, str, List]]:
        """解析 LRC 歌词，返回 [(time_ms, text, translation, word_timings), ...]"""
        lines = []
        for line in lrc_text.splitlines():
            line = line.strip()
            if not line:
                continue
            
            # 解析时间标签 [mm:ss.xx]
            matches = re.findall(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)', line)
            for mm, ss, ms, text in matches:
                time_ms = int(mm) * 60000 + int(ss) * 1000
                if len(ms) == 2:
                    time_ms += int(ms) * 10
                else:
                    time_ms += int(ms)
                
                text = text.strip()
                if text:
                    lines.append((time_ms, text, "", []))
        
        lines.sort(key=lambda x: x[0])
        return lines


class LyricsProvider:
    """歌词提供器 - 整合多个数据源"""
    
    def __init__(self):
        self.sources = {
            "qq": QQMusicAPI(),
            "kugou": KugouAPI(),
            "netease": NeteaseAPI(),
            "lrclib": LrclibAPI()
        }
        self.source_priority = ["netease", "qq", "lrclib", "kugou"]
    
    def get_lyrics(self, title: str, artist: str = "", album: str = "") -> Optional[List[Tuple]]:
        """
        获取歌词，按优先级尝试多个数据源
        返回: [(time_ms, text, translation, word_timings), ...]
        或    [(time_ms, text, word_timings), ...] (纯逐字歌词)
        """
        print(f"\n[LyricsProvider] 搜索: {artist} - {title}" + (f" (专辑: {album})" if album else ""))

        for source_name in self.source_priority:
            source = self.sources[source_name]
            print(f"  >> 尝试 {source_name}...")

            try:
                # 搜索歌曲
                song_info = source.search(title, artist, album)
                if not song_info:
                    continue
                
                print(f"     找到: {song_info.get('title')} - {song_info.get('artist')}")
                
                # 获取歌词
                if source_name == "kugou":
                    lyrics = source.get_lyrics(song_info["id"])
                else:
                    lyrics = source.get_lyrics(song_info)
                if lyrics and len(lyrics) > 0:
                    print(f"     成功获取 {len(lyrics)} 行歌词")
                    return lyrics
                
            except Exception as e:
                print(f"     失败: {e}")
                continue
        
        print("  [x] 所有数据源都未找到歌词")
        return None
    
    def get_lyrics_with_word_timing(self, title: str, artist: str = "") -> Optional[List[Tuple[int, str, List]]]:
        """
        获取带逐字时间戳的歌词
        优先返回 QRC/KRC 格式的逐字歌词
        返回: [(time_ms, text, [(char_start, char_duration, char), ...]), ...]
        """
        lyrics = self.get_lyrics(title, artist)
        if not lyrics:
            return None
        
        # 检查是否有逐字时间戳
        result = []
        for item in lyrics:
            if len(item) >= 4:
                # 格式: (time_ms, text, translation, word_timings)
                time_ms, text, trans, word_timings = item
                result.append((time_ms, text, word_timings))
            elif len(item) == 3:
                # 格式: (time_ms, text, word_timings)
                result.append(item)
            else:
                # 格式: (time_ms, text)
                result.append((item[0], item[1], []))
        
        return result


# 便捷函数
def get_lyrics(title: str, artist: str = "") -> Optional[List[Tuple]]:
    """获取歌词的便捷函数"""
    provider = LyricsProvider()
    return provider.get_lyrics(title, artist)


def get_lyrics_with_word_timing(title: str, artist: str = "") -> Optional[List[Tuple[int, str, List]]]:
    """获取逐字歌词的便捷函数"""
    provider = LyricsProvider()
    return provider.get_lyrics_with_word_timing(title, artist)


if __name__ == "__main__":
    # 测试
    test_cases = [
        ("晴天", "周杰伦"),
        ("告白气球", "周杰伦"),
        ("BLUE", "Billie Eilish"),
    ]
    
    provider = LyricsProvider()
    
    for title, artist in test_cases:
        print("\n" + "="*50)
        lyrics = provider.get_lyrics(title, artist)
        if lyrics:
            print(f"前3行预览:")
            for item in lyrics[:3]:
                print(f"  {item}")
