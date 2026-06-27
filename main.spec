# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['maria_main.py'],
    pathex=[],
    binaries=[],
    datas=[('template_전기실_운영일지.xlsx', '.')],
    # 빌드 시 누락되는 모듈이 있다면 여기에 추가하세요
    hiddenimports=[], 
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 불필요한 라이브러리 제외 유지
    excludes=['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PySide6'],
    noarchive=False,
    optimize=0, # 최적화 레벨을 2로 설정하여 파일 크기 및 속도 개선
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