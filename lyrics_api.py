"""
QQ 音乐歌词 API 模块
支持: QRC 逐字歌词 + 翻译 (GetPlayLyricInfo) + 旧接口回退
"""

import re
import json
import zlib
import base64
import time
import os
import requests
from typing import List, Tuple, Optional, Dict
from urllib.parse import quote

# 日志输出到文件
import threading
_log_lock = threading.Lock()
_log_file = None

def _init_lyrics_log():
    global _log_file
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'taskbar_lyrics.log')
    _log_file = open(path, 'a', encoding='utf-8')

def log(msg):
    global _log_file
    if _log_file is None:
        _init_lyrics_log()
    with _log_lock:
        if _log_file:
            try:
                _log_file.write(msg + '\n')
                _log_file.flush()
            except: pass


# ============================================================
# QQ 音乐 QRC 歌词解密 — 对齐 LDDC 项目
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

def _bitnum(a, b, c):
    return ((a[(b // 32) * 4 + 3 - (b % 32) // 8] >> (7 - b % 8)) & 1) << c

def _bitnum_intr(a, b, c):
    return ((a >> (31 - b)) & 1) << c

def _bitnum_intl(a, b, c):
    return ((a << b) & 0x80000000) >> c

def _sbox_bit(a):
    return (a & 32) | ((a & 31) >> 1) | ((a & 1) << 4)

def _initial_permutation(inp):
    return ((
        _bitnum(inp,57,31)|_bitnum(inp,49,30)|_bitnum(inp,41,29)|_bitnum(inp,33,28)|
        _bitnum(inp,25,27)|_bitnum(inp,17,26)|_bitnum(inp,9,25)|_bitnum(inp,1,24)|
        _bitnum(inp,59,23)|_bitnum(inp,51,22)|_bitnum(inp,43,21)|_bitnum(inp,35,20)|
        _bitnum(inp,27,19)|_bitnum(inp,19,18)|_bitnum(inp,11,17)|_bitnum(inp,3,16)|
        _bitnum(inp,61,15)|_bitnum(inp,53,14)|_bitnum(inp,45,13)|_bitnum(inp,37,12)|
        _bitnum(inp,29,11)|_bitnum(inp,21,10)|_bitnum(inp,13,9)|_bitnum(inp,5,8)|
        _bitnum(inp,63,7)|_bitnum(inp,55,6)|_bitnum(inp,47,5)|_bitnum(inp,39,4)|
        _bitnum(inp,31,3)|_bitnum(inp,23,2)|_bitnum(inp,15,1)|_bitnum(inp,7,0)), (
        _bitnum(inp,56,31)|_bitnum(inp,48,30)|_bitnum(inp,40,29)|_bitnum(inp,32,28)|
        _bitnum(inp,24,27)|_bitnum(inp,16,26)|_bitnum(inp,8,25)|_bitnum(inp,0,24)|
        _bitnum(inp,58,23)|_bitnum(inp,50,22)|_bitnum(inp,42,21)|_bitnum(inp,34,20)|
        _bitnum(inp,26,19)|_bitnum(inp,18,18)|_bitnum(inp,10,17)|_bitnum(inp,2,16)|
        _bitnum(inp,60,15)|_bitnum(inp,52,14)|_bitnum(inp,44,13)|_bitnum(inp,36,12)|
        _bitnum(inp,28,11)|_bitnum(inp,20,10)|_bitnum(inp,12,9)|_bitnum(inp,4,8)|
        _bitnum(inp,62,7)|_bitnum(inp,54,6)|_bitnum(inp,46,5)|_bitnum(inp,38,4)|
        _bitnum(inp,30,3)|_bitnum(inp,22,2)|_bitnum(inp,14,1)|_bitnum(inp,6,0)))

def _inverse_permutation(s0, s1):
    data = bytearray(8)
    data[3] = _bitnum_intr(s1,7,7)|_bitnum_intr(s0,7,6)|_bitnum_intr(s1,15,5)|_bitnum_intr(s0,15,4)|_bitnum_intr(s1,23,3)|_bitnum_intr(s0,23,2)|_bitnum_intr(s1,31,1)|_bitnum_intr(s0,31,0)
    data[2] = _bitnum_intr(s1,6,7)|_bitnum_intr(s0,6,6)|_bitnum_intr(s1,14,5)|_bitnum_intr(s0,14,4)|_bitnum_intr(s1,22,3)|_bitnum_intr(s0,22,2)|_bitnum_intr(s1,30,1)|_bitnum_intr(s0,30,0)
    data[1] = _bitnum_intr(s1,5,7)|_bitnum_intr(s0,5,6)|_bitnum_intr(s1,13,5)|_bitnum_intr(s0,13,4)|_bitnum_intr(s1,21,3)|_bitnum_intr(s0,21,2)|_bitnum_intr(s1,29,1)|_bitnum_intr(s0,29,0)
    data[0] = _bitnum_intr(s1,4,7)|_bitnum_intr(s0,4,6)|_bitnum_intr(s1,12,5)|_bitnum_intr(s0,12,4)|_bitnum_intr(s1,20,3)|_bitnum_intr(s0,20,2)|_bitnum_intr(s1,28,1)|_bitnum_intr(s0,28,0)
    data[7] = _bitnum_intr(s1,3,7)|_bitnum_intr(s0,3,6)|_bitnum_intr(s1,11,5)|_bitnum_intr(s0,11,4)|_bitnum_intr(s1,19,3)|_bitnum_intr(s0,19,2)|_bitnum_intr(s1,27,1)|_bitnum_intr(s0,27,0)
    data[6] = _bitnum_intr(s1,2,7)|_bitnum_intr(s0,2,6)|_bitnum_intr(s1,10,5)|_bitnum_intr(s0,10,4)|_bitnum_intr(s1,18,3)|_bitnum_intr(s0,18,2)|_bitnum_intr(s1,26,1)|_bitnum_intr(s0,26,0)
    data[5] = _bitnum_intr(s1,1,7)|_bitnum_intr(s0,1,6)|_bitnum_intr(s1,9,5)|_bitnum_intr(s0,9,4)|_bitnum_intr(s1,17,3)|_bitnum_intr(s0,17,2)|_bitnum_intr(s1,25,1)|_bitnum_intr(s0,25,0)
    data[4] = _bitnum_intr(s1,0,7)|_bitnum_intr(s0,0,6)|_bitnum_intr(s1,8,5)|_bitnum_intr(s0,8,4)|_bitnum_intr(s1,16,3)|_bitnum_intr(s0,16,2)|_bitnum_intr(s1,24,1)|_bitnum_intr(s0,24,0)
    return data

def _f(state, key):
    t1 = _bitnum_intl(state,31,0)|((state&0xf0000000)>>1)|_bitnum_intl(state,4,5)|_bitnum_intl(state,3,6)|((state&0x0f000000)>>3)|_bitnum_intl(state,8,11)|_bitnum_intl(state,7,12)|((state&0x00f00000)>>5)|_bitnum_intl(state,12,17)|_bitnum_intl(state,11,18)|((state&0x000f0000)>>7)|_bitnum_intl(state,16,23)
    t2 = _bitnum_intl(state,15,0)|((state&0x0000f000)<<15)|_bitnum_intl(state,20,5)|_bitnum_intl(state,19,6)|((state&0x00000f00)<<13)|_bitnum_intl(state,24,11)|_bitnum_intl(state,23,12)|((state&0x000000f0)<<11)|_bitnum_intl(state,28,17)|_bitnum_intl(state,27,18)|((state&0x0000000f)<<9)|_bitnum_intl(state,0,23)
    lrg = [((t1>>(24-i*8))&0xff) for i in range(3)] + [((t2>>(24-i*8))&0xff) for i in range(3)]
    lrg = [lrg[i] ^ key[i] for i in range(6)]
    st = (_SBOX[0][_sbox_bit(lrg[0]>>2)]<<28) | (_SBOX[1][_sbox_bit(((lrg[0]&0x03)<<4)|(lrg[1]>>4))]<<24) | (_SBOX[2][_sbox_bit(((lrg[1]&0x0f)<<2)|(lrg[2]>>6))]<<20) | (_SBOX[3][_sbox_bit(lrg[2]&0x3f)]<<16) | (_SBOX[4][_sbox_bit(lrg[3]>>2)]<<12) | (_SBOX[5][_sbox_bit(((lrg[3]&0x03)<<4)|(lrg[4]>>4))]<<8) | (_SBOX[6][_sbox_bit(((lrg[4]&0x0f)<<2)|(lrg[5]>>6))]<<4) | _SBOX[7][_sbox_bit(lrg[5]&0x3f)]
    return (_bitnum_intl(st,15,0)|_bitnum_intl(st,6,1)|_bitnum_intl(st,19,2)|_bitnum_intl(st,20,3)|_bitnum_intl(st,28,4)|_bitnum_intl(st,11,5)|_bitnum_intl(st,27,6)|_bitnum_intl(st,16,7)|_bitnum_intl(st,0,8)|_bitnum_intl(st,14,9)|_bitnum_intl(st,22,10)|_bitnum_intl(st,25,11)|_bitnum_intl(st,4,12)|_bitnum_intl(st,17,13)|_bitnum_intl(st,30,14)|_bitnum_intl(st,9,15)|_bitnum_intl(st,1,16)|_bitnum_intl(st,7,17)|_bitnum_intl(st,23,18)|_bitnum_intl(st,13,19)|_bitnum_intl(st,31,20)|_bitnum_intl(st,26,21)|_bitnum_intl(st,2,22)|_bitnum_intl(st,8,23)|_bitnum_intl(st,18,24)|_bitnum_intl(st,12,25)|_bitnum_intl(st,29,26)|_bitnum_intl(st,5,27)|_bitnum_intl(st,21,28)|_bitnum_intl(st,10,29)|_bitnum_intl(st,3,30)|_bitnum_intl(st,24,31))

def _des_crypt(inp, key):
    s0, s1 = _initial_permutation(inp)
    for idx in range(15):
        prev = s1
        s1 = _f(s1, key[idx]) ^ s0
        s0 = prev
    s0 = _f(s1, key[15]) ^ s0
    return _inverse_permutation(s0, s1)

def _des_key_schedule(key, mode):
    schedule = [[0]*6 for _ in range(16)]
    shift = (1,1,2,2,2,2,2,2,1,2,2,2,2,2,2,1)
    perm_c = (56,48,40,32,24,16,8,0,57,49,41,33,25,17,9,1,58,50,42,34,26,18,10,2,59,51,43,35)
    perm_d = (62,54,46,38,30,22,14,6,61,53,45,37,29,21,13,5,60,52,44,36,28,20,12,4,27,19,11,3)
    comp = (13,16,10,23,0,4,2,27,14,5,20,9,22,18,11,3,25,7,15,6,26,19,12,1,40,51,30,36,46,54,29,39,50,44,32,47,43,48,38,55,33,52,45,41,49,35,28,31)
    c = sum(_bitnum(key, perm_c[i], 31-i) for i in range(28))
    d = sum(_bitnum(key, perm_d[i], 31-i) for i in range(28))
    for i in range(16):
        c = ((c << shift[i]) | (c >> (28 - shift[i]))) & 0xfffffff0
        d = ((d << shift[i]) | (d >> (28 - shift[i]))) & 0xfffffff0
        t = 15 - i if mode == _DECRYPT else i
        for j in range(6):
            schedule[t][j] = 0
        for j in range(24):
            schedule[t][j // 8] |= _bitnum_intr(c, comp[j], 7 - (j % 8))
        for j in range(24, 48):
            schedule[t][j // 8] |= _bitnum_intr(d, comp[j] - 27, 7 - (j % 8))
    return schedule

_des_key_cache = {}

def _tripledes_key_setup(key, mode):
    cache_key = (key, mode)
    if cache_key not in _des_key_cache:
        if mode == _ENCRYPT:
            _des_key_cache[cache_key] = [_des_key_schedule(key[0:], _ENCRYPT), _des_key_schedule(key[8:], _DECRYPT), _des_key_schedule(key[16:], _ENCRYPT)]
        else:
            _des_key_cache[cache_key] = [_des_key_schedule(key[16:], _DECRYPT), _des_key_schedule(key[8:], _ENCRYPT), _des_key_schedule(key[0:], _DECRYPT)]
    return _des_key_cache[cache_key]

def _tripledes_crypt(data, key):
    for i in range(3):
        data = _des_crypt(data, key[i])
    return data


def _qrc_cloud_decrypt(encrypted_hex: str) -> str:
    """解密 QQ 音乐云端歌词（TripleDES + zlib）"""
    data = bytearray.fromhex(encrypted_hex)
    schedule = _tripledes_key_setup(_QRC_3DES_KEY, _DECRYPT)
    decrypted = bytearray()
    for i in range(0, len(data), 8):
        decrypted += _tripledes_crypt(data[i:i+8], schedule)
    return zlib.decompress(decrypted).decode("utf-8")


def _qrc_local_decrypt(data: bytearray) -> str:
    """解密本地 QMC1 加密文件（QMC1 XOR + TripleDES + zlib）"""
    encrypted = data[11:]
    _qmc1_decrypt(encrypted)
    schedule = _tripledes_key_setup(_QRC_3DES_KEY, _DECRYPT)
    decrypted = bytearray()
    for i in range(0, len(encrypted), 8):
        decrypted += _tripledes_crypt(encrypted[i:i+8], schedule)
    return zlib.decompress(decrypted).decode("utf-8")


def _qmc1_decrypt(data: bytearray) -> None:
    """原地解密 QMC1 加密数据（仅用于本地文件）"""
    for i in range(len(data)):
        if i > 0x7FFF:
            data[i] ^= _QMC1_PRIVKEY[(i % 0x7FFF) & 0x7F]
        else:
            data[i] ^= _QMC1_PRIVKEY[i & 0x7F]


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


_QRC_CONTENT_PATTERN = re.compile(
    r'<Lyric_1 LyricType="1" LyricContent="(?P<content>.*?)"/>',
    re.DOTALL
)
_QRC_LINE_PATTERN = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_QRC_WORD_PATTERN = re.compile(
    r"(?:\[\d+,\d+\])?(?P<content>(?:(?!\(\d+,\d+\)).)*)\((?P<start>\d+),(?P<duration>\d+)\)"
)


def _parse_qrc(qrc_text: str) -> List[Tuple[int, str, List]]:
    """解析 QRC 逐字歌词"""
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


# ============================================================
# 本地缓存模块
# ============================================================

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.lyrics_cache')
_CACHE_FILE = os.path.join(_CACHE_DIR, 'cache.json')
_cache_lock = threading.Lock()
_cache_data = None

def _load_cache():
    global _cache_data
    if _cache_data is not None:
        return
    with _cache_lock:
        if _cache_data is not None:
            return
        try:
            if os.path.exists(_CACHE_FILE):
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
            os.makedirs(_CACHE_DIR, exist_ok=True)
            with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(_cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log(f"    [缓存] 保存失败: {e}")

def cache_get(key: str) -> Optional[dict]:
    """获取缓存，过期返回 None"""
    _load_cache()
    entry = _cache_data.get(key)
    if not entry:
        return None
    if time.time() - entry.get("ts", 0) > 86400:
        del _cache_data[key]
        _save_cache()
        return None
    return entry.get("data")

def cache_set(key: str, data):
    """写入缓存"""
    _load_cache()
    _cache_data[key] = {"data": data, "ts": time.time()}
    _save_cache()

def cache_clean():
    """清理过期缓存"""
    _load_cache()
    now = time.time()
    cleaned = 0
    expired_keys = [k for k, v in _cache_data.items() if now - v.get("ts", 0) > 86400]
    for k in expired_keys:
        del _cache_data[k]
        cleaned += 1
    if cleaned > 0:
        _save_cache()
        log(f"    [缓存] 清理 {cleaned} 条过期记录")


class QQMusicAPI:
    """QQ音乐 API - 唯一的歌词数据源"""

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

    def search(self, title: str, artist: str = "", album: str = "") -> Optional[Dict]:
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
                        log(f"    [QQ匹配] 专辑匹配成功: {song.get('name')} - {song_artist}")
                    elif clean_album in clean_song_album or clean_song_album in clean_album:
                        score += 40

                if score > best_score:
                    best_score = score
                    best_match = song
                    log(f"    [QQ匹配] 得分{score}: {song.get('name')} - {song_artist}")

            if not best_match:
                for song in songs:
                    song_name = song.get("name", "").lower()
                    skip_keywords = ['cover', 'remix', '翻唱', '改编', '版本', 'ver.', 'live']
                    if not any(kw in song_name for kw in skip_keywords):
                        best_match = song
                        log(f"    [QQ匹配] 默认选择: {song.get('name')} - {song.get('singer', [{}])[0].get('name', '')}")
                        break
                if not best_match:
                    best_match = songs[0]

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

    def get_lyrics(self, song_info: Dict) -> Optional[List[Tuple[int, str, str, List]]]:
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

            orig_lines = _parse_qrc(orig_text)
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
                        trans_parsed = _parse_qrc(trans_text)
                    else:
                        trans_parsed = _parse_lrc_fallback(trans_text)

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
                            trans_parsed = _parse_qrc(trans_text)
                        else:
                            trans_parsed = _parse_lrc_fallback(trans_text)

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

    def _get_lyrics_legacy(self, song_info: Dict) -> Optional[List[Tuple[int, str, str, List]]]:
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


class LyricsProvider:
    """歌词提供器 - 仅 QQ 音乐"""

    def __init__(self):
        self.qq = QQMusicAPI()

    def get_lyrics(self, title: str, artist: str = "", album: str = "") -> Optional[List[Tuple]]:
        """获取歌词
        返回: [(time_ms, text, translation, word_timings), ...]
        """
        cache_key = f"lyrics:{title}:{artist}:{album}"
        cached = cache_get(cache_key)
        if cached is not None:
            log(f"\n[LyricsProvider] 缓存命中: {artist} - {title}")
            if cached == "__NONE__":
                return None
            return cached

        log(f"\n[LyricsProvider] QQ音乐搜索: {artist} - {title}" + (f" (专辑: {album})" if album else ""))

        song_info = self.qq.search(title, artist, album)
        if not song_info:
            log("  [x] 未找到匹配的歌曲")
            cache_set(cache_key, "__NONE__")
            return None

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
