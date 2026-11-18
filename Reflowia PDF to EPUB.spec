# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

datas = [('templates', 'templates'), ('app_icon_256.png', '.')]
datas += collect_data_files('webview')
datas += collect_data_files('pymupdf')

binaries = []
binaries += collect_dynamic_libs('pymupdf')

hiddenimports = [
    'webview',
    'webview.platforms.winforms',
    'clr_loader',
    'pythonnet',
    'pymupdf',
    'fitz',
]
hiddenimports += collect_submodules('pymupdf')


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'tkinter', '_tkinter',
        'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL',
        'IPython', 'notebook', 'nbformat', 'nbconvert',
        'zmq', 'tornado', 'black', 'pygments', 'chardet',
        'sqlite3', 'test', 'unittest'
    ],
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
    name='Reflowia PDF to EPUB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon=['app.ico'],
)

