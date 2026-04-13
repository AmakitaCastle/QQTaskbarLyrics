"""
TripleDES / QMC1 歌词解密 — 纯函数，无外部依赖
从 QQ 音乐 QRC 加密歌词解密
"""

import zlib

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
