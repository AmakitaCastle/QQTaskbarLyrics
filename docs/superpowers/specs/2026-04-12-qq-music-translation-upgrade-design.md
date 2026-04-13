# QQ 音乐翻译歌词升级设计

## 问题

当前 `lyrics_api.py` 中的 `QQMusicAPI` 使用旧端点 `c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg`，返回的是标准 LRC 格式，`trans` 翻译字段经常为空。

## 解决方案

切换到 LDDC 使用的 `musicu.fcg` 接口，通过 `GetPlayLyricInfo` 模块获取 QRC 逐字歌词 + 官方翻译。

## 架构

### 新增组件

| 函数 | 职责 |
|------|------|
| `get_session()` | 获取 QQ 音乐 session（uid/sid/userip），调用 `music.getSession.session` |
| `qrc_decrypt(data: str) -> str` | QMC1 XOR 解密，128 字节固定密钥 |
| `parse_qrc(qrc_text: str) -> list` | 解析 QRC XML-like 格式，返回 `[(time_ms, text, word_timings)]` |

### 修改组件

| 函数 | 改动 |
|------|------|
| `QQMusicAPI.get_lyrics()` | 改用 `musicu.fcg` + `GetPlayLyricInfo`，分别获取原文和翻译，解密后合并 |

### 保持不变

- `QQMusicAPI.search()` — 已经使用 `musicu.fcg`，无需改动
- `LyricsProvider` 编排逻辑 — 不变
- `taskbar_lyrics.py` 消费端 — 不变，返回格式兼容

## 数据流

```
title + artist
  → search() → song_mid, duration
  → get_lyrics()
    → get_session() → uid, sid, userip
    → musicu.fcg (GetPlayLyricInfo, qrc=1, trans=1)
    → qrc_decrypt(lyric) + qrc_decrypt(trans)
    → parse_qrc(原文) + parse_qrc(翻译)
    → 合并: [(time_ms, text, translation, word_timings)]
```

## QRC 解密

QMC1 算法：简单的逐字节 XOR，密钥 128 字节。来源：QMC 解密项目（公开知识）。

## QRC 格式

```xml
<Lyric_1 LyricType="1" LyricSort="1" LyricContent="">
[0,0,0,0,0]<0,0,0>一<0,0,0>起<0,0,0>听<0,0,0>雨
</Lyric_1>
```

其中 `<time,duration,?>字` 格式，翻译格式相同但 LyricSort=2。

## 错误处理

- session 获取失败 → 回退到旧端点
- 解密失败 → 回退到旧端点
- 无翻译 → 原文正常返回，翻译为空字符串
