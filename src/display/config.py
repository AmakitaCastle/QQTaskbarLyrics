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


def show_color_config(parent, colors, save_fn, root, canvas):
    win = tk.Toplevel(parent)
    win.title("颜色")
    win.geometry("380x280")
    win.configure(bg="#2a2a3e")
    win.transient(parent)
    win.grab_set()

    cv = {}
    for lb, k in [("背景色", "bg"), ("已唱(高亮)", "sung"), ("未唱(暗色)", "unsung")]:
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

    bf = tk.Frame(win, bg="#2a2a3e")
    bf.pack(fill=tk.X, padx=20, pady=12)

    def apply():
        for k, v in cv.items():
            colors[k] = v.get()
        root.configure(bg=colors["bg"])
        canvas.configure(bg=colors["bg"])
        save_fn()
        win.destroy()

    tk.Button(bf, text="应用", command=apply, bg="#4a4a6e", fg="#FFF",
              width=10).pack(side=tk.LEFT)
    tk.Button(bf, text="关闭", command=win.destroy, bg="#6a4a4e", fg="#FFF",
              width=10).pack(side=tk.RIGHT)


def show_font_config(parent, fonts, save_fn, karaoke_engine):
    win = tk.Toplevel(parent)
    win.title("颜色")
    win.geometry("380x280")
    win.configure(bg="#2a2a3e")
    win.transient(parent)
    win.grab_set()

    cv = {}
    for lb, k in [("背景色", "bg"), ("已唱(高亮)", "sung"), ("未唱(暗色)", "unsung")]:
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

    bf = tk.Frame(win, bg="#2a2a3e")
    bf.pack(fill=tk.X, padx=20, pady=12)

    def apply():
        for k, v in cv.items():
            colors[k] = v.get()
        root.configure(bg=colors["bg"])
        canvas.configure(bg=colors["bg"])
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
