# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['taskbar_lyrics.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['src', 'src.media', 'src.media.provider', 'src.lyrics', 'src.lyrics.manager', 'src.lyrics.parsers', 'src.lyrics.cache', 'src.lyrics.providers', 'src.lyrics.providers.base', 'src.lyrics.providers.qq', 'src.display', 'src.display.window', 'src.display.karaoke', 'src.display.config', 'src.tray', 'src.tray.manager', 'src.utils', 'src.utils.crypto', 'src.utils.log'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TaskbarLyrics',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
