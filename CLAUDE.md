# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two main components:

1. **Windows Taskbar Lyrics Display Tool** (Python) - Displays real-time lyrics from music players (QQ Music, NetEase Cloud Music, Spotify) on the Windows taskbar
2. **QQ Music API** (Node.js/TypeScript) - REST API service for QQ Music data

## Quick Start

### Python Lyrics Tool

**Install dependencies:**
```bash
pip install winsdk pywin32 requests numpy
```

**Run:**
```bash
python taskbar_lyrics.py          # Main lyrics display (pixel-perfect karaoke style)
python taskbar_lyrics_karaoke.py  # Alternative karaoke version with dual-line display
python audio_visualizer.py        # Audio visualization module (FFT analysis)
```

**Features:**
- GSMTC API integration for media playback info
- Multi-source lyrics: QQ Music (QRC), Kugou (KRC), NetEase, Lrclib
- Local LRC file support
- Karaoke-style word-by-word highlighting
- Configurable colors and fonts via UI

### QQ Music API

**Location:** `qq-music-api-main/qq-music-api-main/`

**Install & Run:**
```bash
cd qq-music-api-main/qq-music-api-main
npm install
npm run dev    # Development mode (port 3200)
npm run build  # Production build
npm run start  # Production server
npm run test   # Run tests
```

**Requirements:** Node.js 20+

## Architecture

### Python Lyrics Tool Structure

```
audio_visualizer.py    # Audio FFT analysis, beat detection, color transitions
lyrics_api.py          # Multi-platform lyrics provider (QQ/Kugou/NetEase/Lrclib)
taskbar_lyrics.py      # Main app: pixel-level karaoke rendering
taskbar_lyrics_karaoke.py  # Alternative: dual-line (original + translation) display
```

**Three-layer architecture** (both taskbar_lyrics variants):

| Layer | Class | Role |
|---|---|---|
| Media Info | `MediaInfoProvider` | Background thread polls Windows GSMTC API every 500ms for title/artist/position |
| Lyrics | `LyricsManager` | Loads lyrics from local LRC files or online APIs, caches results |
| Display | `TaskbarLyricsWindow` / `KaraokeLyricsWindow` | Tkinter transparent overlay with click-through, drag, config UI |

**Data flow:** GSMTC API → `MediaInfoProvider` (polls) → `get_info()` → `_tick()` (50ms/100ms interval) → `get_current_line()` → Canvas repaint

**Key Components:**

- `MediaInfoProvider`: Polls Windows GSMTC API; interpolates position between polls using wall-clock delta for smooth tracking
- `LyricsProvider` (in `lyrics_api.py`): Standalone orchestrator for 4 data sources — `NeteaseAPI`, `QQMusicAPI`, `LrclibAPI`, `KugouAPI`
- `LyricsManager`: Wraps `LyricsProvider`, adds local LRC loading and caching
- `TaskbarLyricsWindow`: Tkinter overlay with drag support, click-through, always-on-top

**Lyrics Source Priority:** NetEase → Lrclib → QQ Music → Kugou

**Rendering modes:**
- `taskbar_lyrics.py`: Pixel-level karaoke with 3 Canvas text items (sung/mid/unsung), bisect-based pixel positioning, boundary color interpolation (`_lerp_color`), 20fps (50ms tick)
- `taskbar_lyrics_karaoke.py`: Dual-line display (original + translation), supports KRC (per-character clip rectangles) and LRC (single clip rectangle), 10fps (100ms tick)

**Window flags:** `WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE` hides from taskbar; `WS_EX_TRANSPARENT` enables click-through; periodic `SetWindowPos` keeps always-on-top

### Audio Visualizer

`AudioVisualizer` captures system audio via Windows Core Audio API (loopback mode, `pycaw`), falls back to simulated audio:
- FFT analysis split into bass (20-250Hz), mid (250-4000Hz), treble (4000-20000Hz)
- Beat detection via energy threshold
- Maps frequency bands to HSL color (bass=red/orange, mid=green/yellow, treble=blue/purple)
- 6 preset palettes: rainbow, ocean, fire, neon, pastel, gold
- `VisualizerUI` provides Tkinter config window with live preview

### QQ Music API Structure

```
qq-music-api-main/qq-music-api-main/
├── src/               # TypeScript source code
├── routes/            # API route definitions
├── utils/             # Helper utilities
├── docs/              # VitePress documentation
├── tests/             # Jest test suite
├── config/            # Service configuration
│   ├── service-config.ts  # Fallback mode, global cookie settings
│   └── user-info.ts       # QQ cookie, uin credentials
└── vercel.json        # Vercel deployment config
```

**Entry point:** `app.ts` → imports `koaApp.ts` → starts Koa server on port 3200

**Middleware pipeline** (in order): koa-bodyparser → fallbackMiddleware → cookieMiddleware → koa-static → request logging → CORS → response time → router

**Main API Categories:**
- **Music**: Playback URLs, lyrics, MV info, album images
- **Singer**: Profile, hot songs, similar artists, albums
- **Playlist**: Categories, list, details
- **User**: Login (QR code), avatar, user playlists
- **Rank**: Chart lists and details
- **Other**: Comments, digital albums, downloads

**Key Files:**
- `app.js` / `app.ts`: Entry point, Koa server setup
- `tsconfig.json`: TypeScript configuration
- `vercel.json`: Deployment config

## Commands Reference

| Task | Command |
|------|---------|
| Run lyrics tool | `python taskbar_lyrics.py` |
| Run audio visualizer | `python audio_visualizer.py` |
| Install Python deps | `pip install winsdk pywin32 requests numpy` |
| Start QQ Music API dev | `cd qq-music-api-main/qq-music-api-main && npm run dev` |
| Build QQ Music API | `npm run build` |
| Test QQ Music API | `npm run test` |
| Run docs | `npm run docs:dev` |

## Component Relationship

The Python lyrics tool and the QQ Music API are **independent** projects. `lyrics_api.py` calls QQ Music's **direct web endpoints** (e.g., `c.y.qq.com/lyric/...`) rather than the local QQ Music API server. The QQ Music API exists as a separate standalone service.

## Technical Notes

### GSMTC API
- Requires Windows 10 1809+ for Global System Media Transport Controls
- Supported players: QQ Music, NetEase, Spotify, etc. that register with Windows media session
- Keyboard media keys (play/pause) test: if they control the player, GSMTC is supported

### Lyrics Formats
- **QRC** (QQ Music): Encrypted逐字 lyrics with character-level timing
- **KRC** (Kugou): XOR encryption + zlib decompression, word-level timestamps
- **LRC**: Standard format with line-level timing + optional translation

### Windows Window Style
- Taskbar lyrics uses `WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE` for taskbar hiding
- Click-through mode: `WS_EX_TRANSPARENT` flag via SetWindowLong

### Configuration Files
- Python tool saves user preferences to `~/.taskbar_lyrics_config.json` or `~/.taskbar_lyrics_karaoke_config.json`
- QQ Music API credentials in `qq-music-api-main/qq-music-api-main/config/user-info.ts`

### Rendering Performance
- `taskbar_lyrics.py`: 20fps (50ms tick interval)
- `taskbar_lyrics_karaoke.py`: 10fps (100ms tick interval)
- Audio visualizer: requires `pycaw` for real audio capture, falls back to simulated mode
