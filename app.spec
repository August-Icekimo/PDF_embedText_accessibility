# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for PDF/UA Accessible PDF Generator GUI.

Usage:
    pyinstaller app.spec

Produces a single-file executable that includes tkinterdnd2 data files.
"""
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect tkinterdnd2 platform-specific libraries
tkdnd_datas = []
try:
    tkdnd_datas = collect_data_files('tkinterdnd2')
except Exception:
    pass

# Collect ttkbootstrap themes
ttkb_datas = []
try:
    ttkb_datas = collect_data_files('ttkbootstrap')
except Exception:
    pass

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=tkdnd_datas + ttkb_datas + [('fonts', 'fonts')],
    hiddenimports=[
        'tkinterdnd2',
        'ttkbootstrap',
        'weasyprint',
        'PIL',
        'fitz',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AccessiblePdfGenerator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # GUI 模式，不顯示終端視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # 可自訂 icon: 'icon.ico' (Win) / 'icon.icns' (Mac)
)
