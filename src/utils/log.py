"""
统一日志模块 — 终端 + 文件双输出，线程安全
"""

import sys
import io
import os
import threading
import datetime

# 设置 stdout 编码为 utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

_log_lock = threading.Lock()
_log_file = None
_initialized = False


def _init_log():
    """初始化日志（调用一次）"""
    global _log_file, _initialized
    if _initialized:
        return
    _initialized = True
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'taskbar_lyrics.log')
    path = os.path.normpath(path)
    _log_file = open(path, 'a', encoding='utf-8')


def log(msg):
    """输出日志到终端和文件"""
    if not _initialized:
        _init_log()
    ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except:
        pass
    with _log_lock:
        if _log_file:
            try:
                _log_file.write(line + '\n')
                _log_file.flush()
            except:
                pass
