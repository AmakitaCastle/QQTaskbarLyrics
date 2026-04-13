"""
QQ 音乐歌词 API 模块
支持: QRC 逐字歌词 + 翻译 (GetPlayLyricInfo) + 旧接口回退
"""

import re
import json
import base64
import time
import os
import requests
from typing import List, Tuple, Optional, Dict
from urllib.parse import quote

from src.utils.log import log
from src.lyrics.cache import cache_get, cache_set, cache_clean
from src.lyrics.providers.qq import QQMusicProvider as QQMusicAPI


class LyricsProvider:
    """歌词提供器 - 仅 QQ 音乐"""

    def __init__(self):
        self.qq = QQMusicAPI()

    def get_lyrics(self, title: str, artist: str = "", album: str = "") -> Optional[List[Tuple]]:
        """获取歌词
        返回: [(time_ms, text, translation, word_timings), ...]
        缓存 key 基于 QQ songID，不受 GSMTC 标题格式影响
        """
        log(f"\n[LyricsProvider] QQ音乐搜索: {artist} - {title}" + (f" (专辑: {album})" if album else ""))

        song_info = self.qq.search(title, artist, album)
        if not song_info:
            log("  [x] 未找到匹配的歌曲")
            return None

        song_id = song_info.get("songID", 0)
        cache_key = f"lyrics:{song_id}"
        cached = cache_get(cache_key)
        if cached is not None:
            log(f"\n[LyricsProvider] 缓存命中(songID={song_id}): {artist} - {title}")
            if cached == "__NONE__":
                return None
            return cached

        log(f"     找到: {song_info.get('title')} - {song_info.get('artist')}")
        lyrics = self.qq.get_lyrics(song_info)

        if not lyrics:
            log("  [x] 未获取到歌词")
            cache_set(cache_key, "__NONE__")
            return None

        has_trans = sum(1 for item in lyrics if len(item) > 2 and item[2])
        has_word = sum(1 for item in lyrics if len(item) > 3 and item[3])
        log(f"  >> 获取成功: {len(lyrics)} 行"
            + (" [逐字]" if has_word > 0 else "")
            + (" [翻译]" if has_trans > 0 else ""))
        cache_set(cache_key, lyrics)
        return lyrics

    def get_lyrics_with_word_timing(self, title: str, artist: str = "") -> Optional[List[Tuple[int, str, List]]]:
        """获取带逐字时间戳的歌词"""
        lyrics = self.get_lyrics(title, artist)
        if not lyrics:
            return None
        result = []
        for item in lyrics:
            if len(item) >= 4:
                time_ms, text, trans, word_timings = item
                result.append((time_ms, text, word_timings))
            elif len(item) == 3:
                result.append(item)
            else:
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
    test_cases = [
        ("晴天", "周杰伦"),
        ("告白气球", "周杰伦"),
        ("BLUE", "Billie Eilish"),
    ]

    provider = LyricsProvider()

    for title, artist in test_cases:
        log("\n" + "="*50)
        lyrics = provider.get_lyrics(title, artist)
        if lyrics:
            log(f"前3行预览:")
            for item in lyrics[:3]:
                log(f"  {item}")
