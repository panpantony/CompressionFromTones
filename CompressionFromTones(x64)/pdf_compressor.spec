# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['pdf_compressor.py'],
    pathex=[],
    binaries=[('gs10.04.0/bin/gswin64c.exe', '.')],
    datas=[],
    hiddenimports=['customtkinter', 'pystray', 'pystray._win32', 'PIL', 'rumps'],
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
    name='pdf_compressor',
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
    icon=['icon.ico'],
)
