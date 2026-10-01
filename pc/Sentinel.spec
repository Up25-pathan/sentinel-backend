# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SENTINEL.

One executable. The intelligence panels and the offensive tooling used to be
built as two separate executables from two analyses; they are now a single
window, so they ship together and share the shell, the audit log and the
stylesheet.
"""

import os

PC_ROOT = os.path.abspath(os.getcwd())

HIDDEN = [
    'ui.login_dialog',
    'matplotlib.backends.backend_qtagg',
    # Job scripts are launched as subprocesses via sys.executable, so
    # PyInstaller cannot see the import edge.
    'redlab.utils.workers',
    'redlab.utils.net_scanner',
]

a = Analysis(
    [os.path.join(PC_ROOT, 'sentinel_ui.py')],
    pathex=[PC_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PC_ROOT, 'ui', 'style.qss'), 'ui'),
        # Job scripts run as subprocesses, so they must ship as data files
        # rather than be bundled as importable modules.
        (os.path.join(PC_ROOT, 'redlab', 'bin'), 'redlab/bin'),
    ],
    hiddenimports=HIDDEN,
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
    [],
    exclude_binaries=True,
    name='Sentinel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Sentinel',
)