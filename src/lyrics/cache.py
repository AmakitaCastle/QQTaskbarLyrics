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
    _load_cache()
    _cache_data[key] = {"data": data, "ts": time.time()}
    _save_cache()


def cache_clean():
    _load_cache()
    now = time.time()
    expired_keys = [k for k, v in _cache_data.items() if now - v.get("ts", 0) > _CACHE_TTL_SECONDS]
    for k in expired_keys:
        del _cache_data[k]
    if expired_keys:
        _save_cache()
        log(f"    [缓存] 清理 {len(expired_keys)} 条过期记录")


def disk_cache_key(title: str, artist: str, album: str = "") -> str:
    raw = f"{artist}|{title}|{album}"
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return h


def load_disk_lyrics(key: str) -> Optional[list]:
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
