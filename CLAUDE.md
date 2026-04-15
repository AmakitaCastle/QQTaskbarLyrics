# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TaskbarLyrics** — Windows taskbar lyrics display tool. Shows real-time lyrics above the taskbar with pixel-perfect karaoke-style highlighting. Supports any media player that registers with Windows GSMTC (QQ Music, NetEase, Spotify, etc.).

## Quick Start

```bash
pip install winsdk pywin32 requests pillow
python taskbar_lyrics.py
```

**Dependencies:**
- `winsdk` — Windows GSMTC API bindings (media playback info)
- `pywin32` — Windows API calls (window style, click-through, always-on-top)
- `requests` — QQ Music API HTTP requests
- `pillow` — System tray icon generation (pystray dependency)
- `pystray` — System tray menu (optional, gracefully degrades if missing)

**Run:**
```bash
python taskbar_lyrics.py
```

**Pack to EXE:**
```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name "TaskbarLyrics" taskbar_lyrics.py
```

## Architecture

Modular package-based structure under `src/`:

```
taskbar_lyrics.py          # Entry: TaskbarLyricsApp assembles modules
└── src/
    ├── media/
    │   └── provider.py    # MediaInfoProvider — polls Windows GSMTC API
    ├── lyrics/
    │   ├── manager.py     # LyricsManager — cache + load + current line matching
    │   ├── parsers.py     # QRC / LRC format parsers
    │   ├── cache.py       # Memory + disk cache (30-day TTL)
    │   └── providers/
    │       ├── base.py    # BaseLyricsProvider abstract base class
    │       └── qq.py      # QQMusicProvider — QRC per-char + translation + legacy fallback
    ├── display/
    │   ├── window.py      # TaskbarLyricsWindow — window management, drag, config dialogs
    │   ├── karaoke.py     # KaraokeEngine — pixel-level tri-color gradient rendering
    │   └── config.py      # Config load/save + color/font/button UI dialogs
    ├── tray/
    │   └── manager.py     # TrayManager — pystray system tray with menu
    └── utils/
        ├── crypto.py      # QRC TripleDES decryption + QMC1 fallback
        └── log.py         # Thread-safe console + file logging
```

### Module Responsibilities

**`media/provider.py` — MediaInfoProvider**
- Background thread polls Windows GSMTC API every 500ms
- Interpolates position between polls using wall-clock delta for smooth tracking
- Provides playback controls: `play_pause()`, `next_track()`, `prev_track()`, `is_playing()`
- Uses `winsdk.windows.media.control` with asyncio in a dedicated thread

**`lyrics/manager.py` — LyricsManager**
- Lyric source priority: local LRC files → QQ Music online
- Generates title/artist variants (stripped parentheses, parenthetical content) for better match rates
- Async loading via background thread with callback to main thread
- Memory cache + disk cache (30-day TTL, stored in `~/.taskbar_lyrics_cache/`)
- `get_current_line()` returns `(original_text, translation, progress)` — progress is 0.0-1.0

**`lyrics/providers/qq.py` — QQMusicProvider (sole lyrics data source)**
- Primary: `GetPlayLyricInfo` — QRC per-character lyrics + translation (requires session)
- Fallback: legacy `c.y.qq.com/lyric/...` endpoint (LRC format)
- Session caching: 30-minute TTL for QQ Music session credentials
- Search scoring: exact match (+100), prefix (+60), substring (+30), artist (+50), album (+80)
- Filters AI translation attributions and instrumental markers
- Only accepts non-Live/Ver tracks by default; falls back to all if none available

**`lyrics/parsers.py` — Format Parsers**
- QRC: XML-embedded per-character timing `(char_offset_ms, char_duration_ms, char)`
- LRC: Standard `[mm:ss.ms]` format with 2/3-digit millisecond handling

**`lyrics/cache.py` — Dual-layer Cache**
- Memory: `cache.json` with 30-day TTL
- Disk: Individual `{md5key}.json` files per song, atomic write (tmp + replace)
- Thread-safe with `threading.Lock`

**`display/window.py` — TaskbarLyricsWindow**
- Tkinter overlay: `WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE` hides from taskbar, `WS_EX_TRANSPARENT` for click-through
- Config dialogs: colors (bg/sung/unsung + transparent mode), fonts (family/size/bold), button size, window size
- Playback control buttons: prev / play-pause / next (Canvas-based circular buttons)
- Position persistence: auto-saves on `<Configure>` with 500ms debounce
- Shortcuts: Esc = quit, Ctrl+T = toggle click-through

**`display/karaoke.py` — KaraokeEngine**
- Pixel-level tri-color rendering: sung (highlight) / boundary (color-interpolated) / unsung (dim)
- 3 Canvas text items, `bisect`-based pixel positioning
- Auto-scrolling for text wider than window (keeps highlight at 40% of viewport)
- Boundary color interpolation via `_lerp_color()` (hex color linear interpolation)
- 20fps (50ms tick from `_tick()`)

**`display/config.py` — Configuration**
- Config file: `~/.taskbar_lyrics_config.json`
- Color/font/button/window-size dialogs with live preview swatches
- `cache_enabled` flag persisted across sessions

**`tray/manager.py` — TrayManager**
- pystray-based system tray with golden-note icon
- Menu: show/hide, click-through toggle, window size, colors, fonts, buttons, cache control, quit
- Cross-thread safety: `root.after(0, fn)` to invoke tkinter from tray thread

**`utils/crypto.py` — Decryption**
- TripleDES implementation from scratch (no external crypto dependency)
- QRC cloud decryption: TripleDES + zlib decompress
- QMC1 fallback: XOR with `_QMC1_PRIVKEY` table
- Key caching for performance

**`utils/log.py` — Logging**
- Thread-safe dual output: console + `taskbar_lyrics.log`
- UTF-8 encoding, timestamped `[HH:MM:SS.mmm]` format

### Data Flow

```
GSMTC API → MediaInfoProvider (500ms poll) → get_info() (wall-clock interpolated)
    → _tick() (50ms, 20fps) → get_current_line() → KaraokeEngine.update_display()
    → Canvas repaint (sung/mid/unsung text items)

Song change → LyricsManager.load_async()
    → 1. Memory cache check
    → 2. Disk cache check
    → 3. Local LRC file search
    → 4. QQ Music search + fetch (GetPlayLyricInfo → legacy fallback)
    → Disk cache write → callback to main thread
```

### Lyrics Data Structure

Each lyric line is a 4-tuple: `(time_ms, text, translation, word_timings)`

- `time_ms`: start time in milliseconds
- `text`: original lyric text
- `translation`: translated text (empty string if none)
- `word_timings`: list of `(char_offset_ms, char_duration_ms, char)` for per-character timing (QRC only)

### Window Flags

- `WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE` — hides from taskbar, doesn't steal focus
- `WS_EX_TRANSPARENT` — click-through (toggled via Ctrl+T)
- Periodic `SetWindowPos` with `HWND_TOPMOST` — keeps always-on-top
- 500ms `_ensure_topmost()` cycle + FocusOut recovery prevents window disappearing

## System Requirements

- **Windows 10 1809+** — GSMTC API requirement
- **Python 3.9+** — for `winsdk` asyncio support
- Media keys test: press play/pause on keyboard; if a system popup controls the player, GSMTC is supported

## Testing

```bash
python test_honesty.py    # Module-level unit tests
```

## Configuration

User preferences are saved to `~/.taskbar_lyrics_config.json`. Local LRC files can be enabled by passing `local_dir` to `TaskbarLyricsApp()` in `taskbar_lyrics.py`.
