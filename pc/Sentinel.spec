# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for both SENTINEL applications.

Two executables are produced from one analysis: SENTINEL CIC (reporting) and
SENTINEL REDLAB (offensive operations). They share the shell, the audit log and
the stylesheet, so those are bundled into both.
"""

import os

PC_ROOT = os.path.abspath(os.getcwd())

COMMON_HIDDEN = [
    'ui.login_dialog',
    'matplotlib.backends.backend_qtagg',
    # REDLAB shells out to its own job scripts as subprocesses, so PyInstaller
    # cannot see the import edge.
    'redlab.utils.workers',
    'redlab.utils.net_scanner',
]

a_cic = Analysis(
    [os.path.join(PC_ROOT, 'redlab_ui.py')],
    pathex=[PC_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PC_ROOT, 'ui', 'style.qss'), 'ui'),
    ],
    hiddenimports=COMMON_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['redlab'],
    noarchive=False,
    optimize=0,
)
pyz_cic = PYZ(a_cic.pure)

exe_cic = EXE(
    pyz_cic,
    a_cic.scripts,
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
coll_cic = COLLECT(
    exe_cic,
    a_cic.binaries,
    a_cic.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Sentinel',
)

b_redlab = Analysis(
    [os.path.join(PC_ROOT, 'redlab', '__main__.py')],
    pathex=[PC_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PC_ROOT, 'ui', 'style.qss'), 'ui'),
        # Job scripts run as subprocesses via sys.executable, so they must be
        # shipped as data files rather than bundled as modules.
        (os.path.join(PC_ROOT, 'redlab', 'bin'), 'redlab/bin'),
    ],
    hiddenimports=COMMON_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['ui.panels'],
    noarchive=False,
    optimize=0,
)
pyz_redlab = PYZ(b_redlab.pure)

exe_redlab = EXE(
    pyz_redlab,
    b_redlab.scripts,
    [],
    exclude_binaries=True,
    name='SentinelRedLab',
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
coll_redlab = COLLECT(
    exe_redlab,
    b_redlab.binaries,
    b_redlab.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SentinelRedLab',
)