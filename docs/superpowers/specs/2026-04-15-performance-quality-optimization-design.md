# 性能与代码质量优化设计

**日期**: 2026-04-15
**范围**: 性能优化 (5 项) + 代码质量 (4 项)
**验证策略**: 每组完成后单独验证

---

## 组 1：低风险 — 代码质量修复

### 1.1 裸 `except:` → `except Exception:`

**影响文件**：
- `src/display/window.py` — 约 8 处
- `src/media/provider.py` — 约 4 处
- `src/display/config.py` — 1 处
- `src/lyrics/cache.py` — 约 2 处
- `src/lyrics/manager.py` — 约 1 处

**改动**：全局替换裸 `except:` 为 `except Exception:`。不改变任何 catch 后的行为。

### 1.2 `_variants` 去重逻辑修复

**文件**：`src/lyrics/manager.py:29-44`

**问题**：`not seen.add(...)` 始终为 True（`set.add()` 返回 None），导致 `seen` 永远为空，去重无效。

**修复**：改为标准的先检查后添加模式。

### 1.3 清理 `_search_artist` 死代码

**文件**：`src/lyrics/providers/qq.py:234-240`

**问题**：`self._search_artist` 从未在 `LyricsManager` 或 `QQMusicProvider` 中设置，是死代码。

**修复**：移除该分支。

---

## 组 2：中风险 — 性能与架构

### 2.1 `MediaInfoProvider` event loop 复用

**文件**：`src/media/provider.py`

**现状**：`_run_control` 每次创建新 event loop → `run_until_complete` → `close`。

**设计**：
- `_poll` 启动时保存 `self._loop` 引用
- `_run_control` 改为 `asyncio.run_coroutine_threadsafe(self._do(), self._loop)`
- 新增 `_loop_ready` threading.Event 确保 loop 就绪后再提交
- 控制命令无需等待完成，fire-and-forget

### 2.2 配置保存优化

**文件**：`src/display/window.py:231-243`

**现状**：拖动时每 500ms 触发 JSON 写入。

**设计**：
- `_on_move` 维持 500ms debounce，但仅在 `_pending_save` 为 False 时设置定时器
- 取消 `after_cancel` 后重置 `_pending_save = False`
- `_quit` 时调用 `_save_pos` 确保最终位置被保存

### 2.3 缓存延迟写入

**文件**：`src/lyrics/cache.py`

**现状**：`cache_set` 每次同步读写整个 `cache.json`。

**设计**：
- `cache_set` 仅更新 `_cache_data` 内存，不写磁盘
- 启动后台线程，每 30 秒调用 `_save_cache`
- `atexit.register(_save_cache)` 确保进程退出时 flush
- `_CACHE_DIR` 创建时机不变（首次 load 时）
- 磁盘歌词缓存（`save_disk_lyrics`）保持即时写入（数据量大，需及时落盘）

---

## 组 3：需运行验证 — 动态行为优化

### 3.1 GSMTC 自适应轮询

**文件**：`src/media/provider.py:41-59`

**设计**：
- 播放中：`sleep(0.5)`
- 暂停中：`sleep(2.0)`
- 无媒体/无标题：`sleep(5.0)`
- 通过 `self._playing` 和 `info["title"]` 判断状态

### 3.2 `_tick` 动态频率

**文件**：`taskbar_lyrics.py:75`

**设计**：
- 有歌词 + 播放中：`after(50, self._tick)` — 20fps 平滑渲染
- 加载中：`after(200, self._tick)` — 5fps 刷新提示
- 无歌词/等待/无媒体：`after(500, self._tick)` — 2fps 保持显示

### 3.3 `_ensure_topmost` 按需触发

**文件**：`src/display/window.py:67, 137-148`

**现状**：启动时 `after(500, self._ensure_topmost)`，然后每 500ms 递归调用自己。

**设计**：
- 移除 `_setup_style` 中的周期性调用
- 移除 `_ensure_topmost` 末尾的 `self.root.after(500, self._ensure_topmost)`
- 保留 `_restore_topmost`（FocusOut 时调用）
- 保留 `_setup_style` 中的初始 SetWindowPos 调用（一次性设置窗口样式）

---

## 验证计划

| 组 | 验证方式 | 成功标准 |
|---|---|---|
| 组 1 | `python test_honesty.py` + 正常运行 | 测试通过，无异常 |
| 组 2 | 运行程序，测试播放控制按钮响应 | 按钮无延迟，缓存不丢失 |
| 组 3 | 运行程序，观察 CPU/日志输出 | 暂停时轮询降低，tick 频率正确 |
