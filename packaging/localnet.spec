# Exécutable autonome de LocalNet : pyinstaller packaging/localnet.spec
# Produit dist/LocalNet/ (dossier à zipper) ; Python n'est pas nécessaire sur le PC cible.
from pathlib import Path

racine = Path(SPECPATH).parent

a = Analysis(
    [str(racine / "packaging" / "lanceur.py")],
    pathex=[str(racine)],
    datas=[
        (str(racine / "chat" / "web"), "chat/web"),
        (str(racine / "desktop" / "ressources"), "desktop/ressources"),
    ],
    # Modules Qt inutiles mais lourds (navigateur intégré, QML, PDF).
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtPdf",
        "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LocalNet", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="LocalNet")
