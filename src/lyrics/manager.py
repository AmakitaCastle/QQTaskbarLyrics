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
                    # parse_lrc returns (time_ms, text, []) — normalize to (time_ms, text, translation, word_timings)
                    return [(t, x, "", wt) for t, x, wt in parse_lrc(text)]
                except Exception:
                    pass
        return None

    def _fetch_online(self, title: str, artist: str, album: str = "") -> Optional[list]:
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
