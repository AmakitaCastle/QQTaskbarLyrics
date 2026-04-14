"""
配置加载/保存 + 配置 UI 弹窗
"""

import json
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path.home() / ".taskbar_lyrics_config.json"


def load_config() -> Dict[str, Any]:
    try:
        if CONFIG_FILE.exists():
            return json.load(open(CONFIG_FILE, "r", encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_config(config: dict):
    try:
        json.dump(config, open(CONFIG_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_cache_enabled() -> bool:
    """获取缓存启用状态，默认 True"""
    cfg = load_config()
    return cfg.get("cache_enabled", True)


def set_cache_enabled(enabled: bool):
    """保存缓存启用状态"""
    cfg = load_config()
    cfg["cache_enabled"] = enabled
    save_config(cfg)


def show_color_config(parent, colors, save_fn, root, canvas):
    win = tk.Toplevel(parent)
    win.title("颜色")
    win.geometry("420x320")
    win.configure(bg="#2a2a3e")
    win.transient(parent)
    win.grab_set()

    cv = {}
    is_transparent = tk.BooleanVar(value=colors.get("bg") == "transparent")
    bg_entry_var = None

    # --- 背景色行 ---
    f_bg = tk.Frame(win, bg="#2a2a3e")
    f_bg.pack(fill=tk.X, padx=20, pady=(12, 6))
    tk.Label(f_bg, text="背景色", fg="#FFF", bg="#2a2a3e",
             font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
    bg_val = colors.get("bg", "#1a1a2e")
    if bg_val == "transparent":
        bg_val = "#1a1a2e"  # show a default in the entry
    bg_entry_var = tk.StringVar(value=bg_val)
    cv["bg"] = bg_entry_var
    tk.Entry(f_bg, textvariable=bg_entry_var, width=9, font=("Consolas", 11)).pack(side=tk.LEFT, padx=8)
    bg_pv = tk.Label(f_bg, text="  ", bg=bg_val, width=3, relief=tk.RIDGE)
    bg_pv.pack(side=tk.LEFT)
    bg_entry_var.trace_add("write", lambda *a, p=bg_pv, vv=bg_entry_var: p.config(bg=vv.get()))

    tk.Checkbutton(f_bg, text="透明", variable=is_transparent, bg="#2a2a3e", fg="#FFF",
                   selectcolor="#4a4a6e", font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT, padx=12)

    # --- 已唱/未唱 ---
    for lb, k in [("已唱(高亮)", "sung"), ("未唱(暗色)", "unsung")]:
        f = tk.Frame(win, bg="#2a2a3e")
        f.pack(fill=tk.X, padx=20, pady=6)
        tk.Label(f, text=lb, fg="#FFF", bg="#2a2a3e",
                 font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
        v = tk.StringVar(value=colors.get(k, "#666"))
        cv[k] = v
        tk.Entry(f, textvariable=v, width=9, font=("Consolas", 11)).pack(side=tk.LEFT, padx=8)
        pv = tk.Label(f, text="  ", bg=colors.get(k, "#666"), width=3, relief=tk.RIDGE)
        pv.pack(side=tk.LEFT)
        v.trace_add("write", lambda *a, p=pv, vv=v: p.config(bg=vv.get()))

    # 提示
    tk.Label(win, text="* 透明模式下背景不可见，仅显示歌词文字",
             fg="#888", bg="#2a2a3e", font=("Microsoft YaHei UI", 9)).pack(anchor=tk.W, padx=20, pady=(4, 0))

    bf = tk.Frame(win, bg="#2a2a3e")
    bf.pack(fill=tk.X, padx=20, pady=12)

    def apply():
        if is_transparent.get():
            colors["bg"] = "transparent"
        else:
            colors["bg"] = bg_entry_var.get()
        save_fn()
        # 刷新窗口背景
        win.destroy()

    tk.Button(bf, text="应用", command=apply, bg="#4a4a6e", fg="#FFF",
              width=10).pack(side=tk.LEFT)
    tk.Button(bf, text="关闭", command=win.destroy, bg="#6a4a4e", fg="#FFF",
              width=10).pack(side=tk.RIGHT)


def show_button_config(parent, colors, save_fn, window, apply_fn):
    """按钮设置弹窗"""
    win = tk.Toplevel(parent)
    win.title("按钮设置")
    win.geometry("380x140")
    win.configure(bg="#2a2a3e")
    win.transient(parent)
    win.grab_set()

    # --- 按钮图标颜色 ---
    f1 = tk.Frame(win, bg="#2a2a3e")
    f1.pack(fill=tk.X, padx=20, pady=(12, 6))
    tk.Label(f1, text="图标颜色", fg="#FFF", bg="#2a2a3e",
             font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
    btn_val = colors.get("btn_fg", "#ffffff")
    btn_var = tk.StringVar(value=btn_val)
    tk.Entry(f1, textvariable=btn_var, width=9, font=("Consolas", 11)).pack(side=tk.LEFT, padx=8)
    pv = tk.Label(f1, text="  ", bg=btn_val, width=3, relief=tk.RIDGE)
    pv.pack(side=tk.LEFT)
    btn_var.trace_add("write", lambda *a: pv.config(bg=btn_var.get()))

    # --- 按钮大小 ---
    f2 = tk.Frame(win, bg="#2a2a3e")
    f2.pack(fill=tk.X, padx=20, pady=6)
    tk.Label(f2, text="按钮大小", fg="#FFF", bg="#2a2a3e",
             font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
    btn_size = tk.IntVar(value=28)
    tk.Spinbox(f2, from_=20, to=40, textvariable=btn_size, width=4,
               font=("Consolas", 11)).pack(side=tk.LEFT, padx=8)

    bf = tk.Frame(win, bg="#2a2a3e")
    bf.pack(fill=tk.X, padx=20, pady=12)

    def apply():
        colors["btn_fg"] = btn_var.get()
        apply_fn(btn_size.get())
        save_fn()
        win.destroy()

    tk.Button(bf, text="应用", command=apply, bg="#4a4a6e", fg="#FFF",
              width=10).pack(side=tk.LEFT)
    tk.Button(bf, text="关闭", command=win.destroy, bg="#6a4a4e", fg="#FFF",
              width=10).pack(side=tk.RIGHT)


def show_font_config(parent, fonts, save_fn, karaoke_engine):
    win = tk.Toplevel(parent)
    win.title("字体")
    win.geometry("420x160")
    win.configure(bg="#2a2a3e")
    win.transient(parent)
    win.grab_set()

    FONTS = ["Microsoft YaHei UI", "微软雅黑", "SimHei", "黑体", "Consolas", "Segoe UI", "Arial"]
    try:
        af = FONTS + [f for f in tkfont.families() if f not in FONTS]
    except Exception:
        af = FONTS

    cur = fonts.get("lyric", ("Microsoft YaHei UI", 14, "bold"))
    if isinstance(cur, list):
        cur = tuple(cur)

    f = tk.Frame(win, bg="#2a2a3e")
    f.pack(fill=tk.X, padx=20, pady=10)
    vf = tk.StringVar(value=cur[0])
    vs = tk.IntVar(value=cur[1])
    vb = tk.BooleanVar(value=len(cur) > 2 and cur[2] == "bold")

    tk.Label(f, text="字体", fg="#FFF", bg="#2a2a3e").pack(side=tk.LEFT)
    om = tk.OptionMenu(f, vf, *af)
    om.config(width=14, bg="#4a4a6e", fg="#FFF")
    om.pack(side=tk.LEFT, padx=5)
    tk.Spinbox(f, from_=8, to=36, textvariable=vs, width=4).pack(side=tk.LEFT, padx=5)
    tk.Checkbutton(f, text="粗", variable=vb, bg="#2a2a3e", fg="#FFF",
                   selectcolor="#4a4a6e").pack(side=tk.LEFT)

    bf = tk.Frame(win, bg="#2a2a3e")
    bf.pack(fill=tk.X, padx=20, pady=10)

    def apply():
        fonts["lyric"] = (vf.get(), vs.get(), "bold" if vb.get() else "normal")
        karaoke_engine._text = ""  # force rebuild on next frame
        save_fn()
        win.destroy()

    tk.Button(bf, text="应用", command=apply, bg="#4a4a6e", fg="#FFF",
              width=10).pack(side=tk.LEFT)
    tk.Button(bf, text="关闭", command=win.destroy, bg="#6a4a4e", fg="#FFF",
              width=10).pack(side=tk.RIGHT)
