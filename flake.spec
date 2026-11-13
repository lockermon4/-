# PyInstaller: сборка Flake.app (python -m PyInstaller --noconfirm flake.spec)
from flakemac import __version__

a = Analysis(
    ["run_flake.py"],
    datas=[("flakemac/assets", "flakemac/assets")],
    hiddenimports=["AppKit", "Foundation", "Quartz", "objc"],
    excludes=[
        "tkinter", "unittest", "pydoc_data",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtNetwork",
        "PySide6.QtOpenGL", "PySide6.QtDBus", "PySide6.QtSql",
        "PySide6.QtTest", "PySide6.QtPrintSupport", "PySide6.QtSvg",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Flake",
    console=False,
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Flake")
app = BUNDLE(
    coll,
    name="Flake.app",
    icon="flake.icns",
    bundle_identifier="io.github.flakemac",
    version=__version__,
    info_plist={
        "CFBundleName": "Flake",
        "CFBundleDisplayName": "Flake",
        "CFBundleShortVersionString": __version__,
        "LSUIElement": True,                 # без значка в Dock
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    },
)
