"""
媒体信息 Provider — Windows GSMTC API 轮询 + 播放控制
"""

import asyncio
import threading
import time


class MediaInfoProvider:
    def __init__(self):
        self._info = {"title": "", "artist": "", "position_ms": 0, "duration_ms": 0}
        self._lock = threading.Lock()
        self._running = False
        self._update_ts = 0.0
        self._state = {"playing": True}

    async def _fetch(self):
        try:
            from winsdk.windows.media.control import \
                GlobalSystemMediaTransportControlsSessionManager as SM
            mgr = await SM.request_async()
            s = mgr.get_current_session()
            if not s:
                return None
            p = await s.try_get_media_properties_async()
            tl = s.get_timeline_properties()
            return {"title": p.title or "", "artist": p.artist or "",
                    "album": getattr(p, 'album_title', '') or "",
                    "position_ms": int(tl.position.total_seconds() * 1000),
                    "duration_ms": int(tl.end_time.total_seconds() * 1000)}
        except Exception:
            return None

    def _poll(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        fails = 0
        while self._running:
            r = loop.run_until_complete(self._fetch())
            if r:
                with self._lock:
                    self._info = r
                    self._update_ts = time.time()
                fails = 0
            else:
                fails += 1
                if fails >= 10:
                    with self._lock:
                        self._info = {"title": "", "artist": "", "position_ms": 0, "duration_ms": 0}
                    fails = 0
            time.sleep(0.5)

    def start(self):
        self._running = True
        threading.Thread(target=self._poll, daemon=True).start()

    def stop(self):
        self._running = False

    def get_info(self):
        with self._lock:
            info = self._info.copy()
            ts = self._update_ts
        if info["title"] and ts > 0:
            info["position_ms"] = int(info["position_ms"] + (time.time() - ts) * 1000)
        return info

    # ---- 播放控制 ----

    def _run_control(self, action: str):
        """在临时 event loop 中执行 GSMTC 控制命令"""
        async def _do():
            try:
                from winsdk.windows.media.control import \
                    GlobalSystemMediaTransportControlsSessionManager as SM
                mgr = await SM.request_async()
                s = mgr.get_current_session()
                if not s:
                    return
                if action == "play_pause":
                    await s.try_toggle_play_pause_async()
                elif action == "next":
                    await s.try_skip_next_async()
                elif action == "prev":
                    await s.try_skip_previous_async()
                elif action == "stop":
                    await s.try_stop_async()
            except Exception:
                pass
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_do())
            loop.close()
        except Exception:
            pass

    def play_pause(self):
        self._run_control("play_pause")
        with self._lock:
            self._state["playing"] = not self._state["playing"]

    def next_track(self):
        self._run_control("next")

    def prev_track(self):
        self._run_control("prev")

    def is_playing(self):
        with self._lock:
            return self._state.get("playing", True)
