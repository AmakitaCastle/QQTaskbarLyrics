"""
QQ 音乐歌词提供者 — QRC 逐字歌词 + 翻译 (GetPlayLyricInfo) + 旧接口回退
"""

import json
import base64
import time
import requests
from typing import Optional, List, Dict, Tuple

from src.lyrics.providers.base import BaseLyricsProvider, SongInfo, LyricLine
from src.lyrics.cache import cache_get, cache_set
from src.lyrics.parsers import parse_qrc, parse_lrc
from src.utils.crypto import _qrc_cloud_decrypt, _qmc1_decrypt
from src.utils.log import log


class QQMusicProvider(BaseLyricsProvider):
    """QQ 音乐歌词提供者 — 唯一的歌词数据源"""

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
        """获取 QQ 音乐 session (uid, sid, userip)，缓存 30 分钟"""
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

    @staticmethod
    def _is_instrumental(text: str) -> bool:
        """检测歌词是否为纯音乐提示"""
        if not text:
            return False
        keywords = [
            "纯音乐",
            "没有填词",
            "暂无歌词",
            "instrumental",
            "伴奏",
            "BGM",
            "background music",
            "此歌曲为",
        ]
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def search(self, title: str, artist: str = "", album: str = "") -> Optional[SongInfo]:
        """搜索歌曲，尝试找到最佳匹配"""
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

            skip_keywords = ['cover', 'remix', '翻唱', '改编', '版本']

            # 先收集所有歌曲及其是否含 Live/Ver 标记
            all_songs = []
            for song in songs:
                song_name = song.get("name", "").lower()
                is_live_ver = any(kw in song_name for kw in ['live', 'ver.'])
                all_songs.append((song, is_live_ver))

            # 优先非 Live/Ver 的歌曲；如果全是 Live/Ver 版本，也接受
            candidates = [(s, v) for s, v in all_songs if not v]
            if not candidates:
                candidates = all_songs

            for song, _ in candidates:
                song_title = song.get("name", "").lower().replace(" ", "")
                song_artist = song.get("singer", [{}])[0].get("name", "").lower().replace(" ", "")

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
                        log(f"    [QQ匹配] 专辑匹配成功: {song.get('name')} - {song_artist}")
                    elif clean_album in clean_song_album or clean_song_album in clean_album:
                        score += 40

                if score > best_score:
                    best_score = score
                    best_match = song
                    log(f"    [QQ匹配] 得分{score}: {song.get('name')} - {song_artist}")

            if not best_match:
                for song, is_live_ver in candidates:
                    song_name = song.get("name", "").lower()
                    if not is_live_ver and not any(kw in song_name for kw in skip_keywords):
                        best_match = song
                        log(f"    [QQ匹配] 默认选择: {song.get('name')} - {song.get('singer', [{}])[0].get('name', '')}")
                        break
                if not best_match:
                    song = candidates[0][0]
                    best_match = song

            log(f"    [QQ匹配] 最终选择(score={best_score}): {best_match.get('name')} - {best_match.get('singer', [{}])[0].get('name', '')}")

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
        """获取歌词（优先旧接口，QRC 需登录）
        返回: [(time_ms, text, translation, word_timings), ...]
        """
        log(f"    [QQ音乐歌词] 开始获取歌词: songID={song_info.get('songID', 0)}, songMID={song_info.get('id', '')}")

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
        song_id = song_info.get("songID", 0)
        if not song_id:
            log(f"    [QQ音乐歌词] 缺少 songID (当前值: {song_id})，无法调用 GetPlayLyricInfo")
            return legacy_result

        session = self._get_session()
        log(f"    [QQ音乐歌词] session: uid={session.get('uid')}, sid={session.get('sid', '')[:8]}***, userip={session.get('userip', '')}")
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

            log(f"    [QQ音乐歌词] GetPlayLyricInfo 响应: lyric={len(lyric_enc)}字, trans={len(trans_enc)}字, crypt={crypt}")
            log(f"    [QQ音乐歌词] 完整响应 keys: {list(lyric_info.keys())}")

            if not lyric_enc:
                log(f"    [QQ音乐歌词] lyric 字段为空，此歌曲无 QRC 歌词")
                return legacy_result

            log(f"    [QQ音乐歌词] lyric 长度={len(lyric_enc)}, trans 长度={len(trans_enc)}, crypt={crypt}")

            try:
                log(f"    [QQ音乐歌词] 使用 TripleDES 解密 (crypt={crypt})")
                orig_text = _qrc_cloud_decrypt(lyric_enc)
                log(f"    [QQ音乐歌词] QRC 解密成功, 原文前100字: {orig_text[:100]}")
                if self._is_instrumental(orig_text):
                    log("    [QQ音乐歌词] 检测到纯音乐标记，此歌曲无歌词")
                    return None
            except Exception as e:
                log(f"    [QQ音乐歌词] TripleDES 解密失败: {e}")
                log(f"    [QQ音乐歌词] 尝试 QMC1 回退解密...")
                try:
                    if all(c in "0123456789ABCDEFabcdef" for c in lyric_enc[:4]):
                        lyric_bytes = bytes.fromhex(lyric_enc)
                    else:
                        lyric_bytes = base64.b64decode(lyric_enc)
                    lyric_ba = bytearray(lyric_bytes)
                    if crypt == 1:
                        _qmc1_decrypt(lyric_ba)
                    orig_text = lyric_ba.decode("utf-8")
                    log(f"    [QQ音乐歌词] QMC1 回退成功, 原文前100字: {orig_text[:100]}")
                except Exception as e2:
                    log(f"    [QQ音乐歌词] 所有解密方式均失败: {e2}")
                    return legacy_result

            orig_lines = parse_qrc(orig_text)
            log(f"    [QQ音乐歌词] QRC 解析 {len(orig_lines)} 行")

            trans_map = {}
            trans_lines_list = []
            trans_decrypted_text = None
            if trans_enc:
                try:
                    trans_text = _qrc_cloud_decrypt(trans_enc)
                    log(f"    [QQ音乐歌词] 翻译解密成功, 前100字: {trans_text[:100]}")
                    trans_decrypted_text = trans_text

                    if '<Lyric_1' in trans_text[:200]:
                        trans_parsed = parse_qrc(trans_text)
                    else:
                        trans_parsed = parse_lrc(trans_text)

                    for time_ms, text, _ in trans_parsed:
                        trans_map[time_ms] = text
                    trans_lines_list = trans_parsed
                    log(f"    [QQ音乐歌词] 翻译解析 {len(trans_lines_list)} 行")
                except Exception as e:
                    log(f"    [QQ音乐歌词] 翻译 TripleDES 解密失败, 尝试 QMC1 回退...")
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
                        log(f"    [QQ音乐歌词] 翻译 QMC1 回退成功 {len(trans_lines_list)} 行")
                    except Exception as e2:
                        log(f"    [QQ音乐歌词] 翻译解密完全失败: {e2}")
            else:
                log(f"    [QQ音乐歌词] trans 字段为空，此歌曲无官方翻译")

            is_qrc_trans = (trans_decrypted_text is not None and '<Lyric_1' in trans_decrypted_text[:200])

            result = []
            if trans_lines_list and not is_qrc_trans:
                for i, (time_ms, text, word_timings) in enumerate(orig_lines):
                    translation = trans_lines_list[i][1] if i < len(trans_lines_list) else ""
                    result.append((time_ms, text, translation, word_timings))
                log(f"    [QQ音乐歌词] 翻译合并: LRC 按行对齐 ({len(trans_lines_list)} 行翻译)")
            elif trans_map and is_qrc_trans:
                for time_ms, text, word_timings in orig_lines:
                    translation = trans_map.get(time_ms, "")
                    result.append((time_ms, text, translation, word_timings))
                log(f"    [QQ音乐歌词] 翻译合并: QRC 精确匹配")
            else:
                for time_ms, text, word_timings in orig_lines:
                    result.append((time_ms, text, "", word_timings))

            has_trans = sum(1 for _, _, tr, _ in result if tr)
            has_word = sum(1 for _, _, _, wt in result if wt)
            log(f"    [QQ音乐歌词] GetPlayLyricInfo 成功: {len(result)} 行, 翻译 {has_trans} 行, 逐字 {has_word} 行")
            return result

        except Exception as e:
            log(f"    [QQ音乐歌词] GetPlayLyricInfo 失败: {e}")
            import traceback
            traceback.print_exc()
            return legacy_result

    def _get_lyrics_legacy(self, song_info: SongInfo) -> Optional[List[LyricLine]]:
        """旧版歌词接口（回退用）"""
        song_mid = song_info.get("id", "")
        log(f"    [QQ音乐歌词(旧)] 请求 songmid={song_mid}")
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
            log(f"    [QQ音乐歌词(旧)] lyric 长度={len(lyric)}, trans 长度={len(trans_raw)}")
            if not lyric:
                log(f"    [QQ音乐歌词(旧)] lyric 为空，完整响应 keys: {list(data.keys())}")
                return None

            if self._is_instrumental(lyric):
                log(f"    [QQ音乐歌词(旧)] 检测到纯音乐标记，此歌曲无歌词")
                return None

            orig_lines = self._parse_lrc(lyric)
            log(f"    [QQ音乐歌词(旧)] 解析 {len(orig_lines)} 行原文")

            trans_map = {}
            if trans_raw:
                for time_ms, t, _ in self._parse_lrc(trans_raw):
                    trans_map[time_ms] = t
                log(f"    [QQ音乐歌词(旧)] 解析 {len(trans_map)} 行翻译")
            else:
                log(f"    [QQ音乐歌词(旧)] trans 字段为空")

            result = []
            for time_ms, text, word_timings in orig_lines:
                translation = trans_map.get(time_ms, "")
                result.append((time_ms, text, translation, word_timings))

            return result

        except Exception as e:
            log(f"    [QQ音乐歌词(旧)] 失败: {e}")
            return None

    def _parse_lrc(self, lrc_text: str) -> List[Tuple[int, str, List]]:
        """解析 LRC 歌词 — 委托给模块级 parse_lrc"""
        return parse_lrc(lrc_text)
