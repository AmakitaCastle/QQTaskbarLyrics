# Taskbar Lyrics Playback Control Bar Design

**Date:** 2026-04-14  
**Topic:** Replace vertical button layout with horizontal pill-style control bar

## Context

The current implementation (from previous task) places 3 playback control buttons (prev/play-pause/next) in a **vertical stack** inside a left-side `btn_frame` (75px wide), with the lyrics Canvas taking the rest of the window. The reference image shows a sleek horizontal bar where buttons are inline with the lyrics text, separated by a vertical divider line.

Additionally, the user has removed the right-click context menu from the codebase — settings are now accessed via the system tray.

## Architecture

Single horizontal container replaces the two-frame layout:

```
┌──────────────────────────────────────────────────────┐
│ [⏮] [] [⏭] │ 只有你是天蓝色                     │
└──────────────────────────────────────────────────────┘
 按钮组(86px)  分隔线  歌词Canvas(flex:1)
```

No more `btn_frame` + `canvas` split. One `tk.Frame` with `pack(side=tk.LEFT)` for all children.

## Window Dimensions

- Height: **32px** (down from current 42px)
- Width: 900px default (unchanged)
- Minimum height: 20px (unchanged)

## Components

### 1. Container Frame (`self.container`)

A single `tk.Frame` replacing both `btn_frame` and `canvas` packing:

```python
self.container = tk.Frame(self.root, bg=_actual_bg, height=32)
self.container.pack(fill=tk.X, expand=False)
```

### 2. Button Group Frame (`self.ctrl_group`)

Fixed width ~86px, 3 buttons horizontally:

- 3 × `tk.Canvas` (26×26px circles) + 0px gap between them
- Each button: `create_oval(0,0,26,26)` for background, `create_text(13,13)` for icon
- Icons: `⏮` (prev), `⏸`/`▶` (play/pause toggle), `⏭` (next)
- Colors: transparent bg, text `#ccccdd`; hover draws `rgba(255,255,255,0.1)` circle
- Play button in active state: text color `#FFD700` (matches `sung` lyric color)

```python
self.ctrl_group = tk.Frame(self.container, bg=_actual_bg, width=86)
self.ctrl_group.pack(side=tk.LEFT, fill=tk.Y)
```

### 3. Divider

1px wide, 16px tall vertical line between buttons and lyrics:

```python
self.divider = tk.Frame(self.container, bg="#2a2a38", width=1, height=16)
self.divider.pack(side=tk.LEFT, padx=8)
```

### 4. Lyrics Canvas (`self.canvas`)

Takes remaining space, identical to current but with updated `offset_x`:

```python
self.canvas = tk.Canvas(self.container, bg=_actual_bg,
                        height=32, highlightthickness=0, bd=0)
self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
```

### KaraokeEngine offset

- `offset_x` = 86 (button group) + 1 (divider) + 16 (divider padding) = **103px**
- Lyrics render starts after the button area

## Interaction

### Drag
- Bound to `self.container` instead of `self.canvas`
- Entire bar (buttons + divider + lyrics) is draggable

### Right-click
- **Removed** (user has already deleted menu code; settings via tray)

### Keyboard shortcuts
- `Esc` — quit
- `Ctrl+T` — toggle click-through

### Click-through
- When enabled (`WS_EX_TRANSPARENT`), entire window including buttons is non-interactive

## Color Configuration

### Changes
- **Remove** from `DEFAULT_COLORS`: `btn`, `btn_hover`, `btn_text` (no longer needed — buttons are transparent)
- **Add**: `divider` (default: `#2a2a38`, a subtle dark tone approximating `rgba(255,255,255,0.15)` on the `#1a1a2e` background)
- Keep: `bg`, `sung`, `unsung`

### Play state color
- Play button text switches between `#ccccdd` (default) and `#FFD700` (playing)
- Controlled by `self._callbacks` from `MediaInfoProvider`

## Files Modified

| File | Change |
|------|--------|
| `src/display/window.py` | Replace btn_frame+canvas with single container frame; horizontal circular buttons; divider; new dimensions; update DEFAULT_COLORS (remove btn keys, add divider) |
| `src/display/karaoke.py` | Update `offset_x` default to 103 |
| `taskbar_lyrics.py` | No changes needed (callbacks already wired) |
| `src/media/provider.py` | No changes needed (control methods already added) |

## Error Handling

- If GSMTC session unavailable: buttons still render but clicks silently fail (existing behavior)
- Play state toggle in `_on_play_pause` is optimistic — UI updates immediately, actual state synced via `_tick`/`is_playing()`
- `offset_x` clamped: lyrics never render under buttons
