# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all # 💡 이 부분을 상단에 추가하세요

# 💡 collect_all을 사용하여 의존성을 명시적으로 수집
torch_data = collect_all('torch')
pandas_data = collect_all('pandas')
scipy_data = collect_all('scipy')

a = Analysis(
    ['maria_main.py'],
    pathex=[],
    binaries=torch_data[1] + pandas_data[1] + scipy_data[1], # 💡 바이너리 추가
    datas=torch_data[2] + pandas_data[2] + scipy_data[2],    # 💡 데이터 추가
    hiddenimports=torch_data[0] + pandas_data[0] + scipy_data[0], # 💡 숨겨진 임포트 추가
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PySide6'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None) # a.zipped_data 추가

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False, # 빌드 오류 파악을 위해 필요시 True로 변경 가능
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
    name='main',
)