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
