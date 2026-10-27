"""Thèmes clair et sombre, accent bleu ; feuille de style, icônes, logo, police.

Attention : Qt ignore border-radius s'il dépasse la moitié de la hauteur du
widget ; boutons et champs font au moins 40 px de haut pour leurs 20 px.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QPushButton

RESSOURCES = Path(__file__).resolve().parent / "ressources"

BLEU = "#1877F2"
BLEU_SURVOL = "#166FE5"
VERT = "#42B72A"
ROUGE = "#E41E3F"
RAYON = 20  # boutons et champs
POLICE = "Plus Jakarta Sans"  # ressources/polices, licence OFL

PALETTES = {
    "clair": {
        "fond": "#F0F2F5", "carte": "#FFFFFF", "texte": "#050505", "doux": "#65676B",
        "lisere": "#E4E6EB", "champ": "#F0F2F5", "survol": "#E4E6EB", "bulle": "#E4E6EB",
        "bleu_pale": "#E7F3FF", "ombre": "#1A000000",
    },
    "sombre": {
        "fond": "#18191A", "carte": "#242526", "texte": "#E4E6EB", "doux": "#B0B3B8",
        "lisere": "#3E4042", "champ": "#3A3B3C", "survol": "#4E4F50", "bulle": "#3A3B3C",
        "bleu_pale": "#263951", "ombre": "#66000000",
    },
}
mode = "clair"

# Pastilles des profils sans photo : lettre blanche sur couleur vive.
TEINTES = ["#1877F2", "#42B72A", "#E9710F", "#F3425F", "#9360F7", "#0F9D8F", "#D6308A", "#5C6BC0"]


def c(nom: str) -> str:
    """Couleur `nom` du thème courant."""
    return PALETTES[mode][nom]


def qss() -> str:
    p = PALETTES[mode]
    return f"""
* {{ font-family: "{POLICE}"; color: {p["texte"]}; font-size: 13px; }}
QMainWindow, QDialog {{ background: {p["fond"]}; }}
QToolTip {{ background: {p["carte"]}; color: {p["texte"]}; border: 1px solid {p["lisere"]}; padding: 6px 8px; }}

#carte {{ background: {p["carte"]}; border-radius: 16px; }}
#carte-fine {{ background: {p["champ"]}; border-radius: 14px; }}
#saisie {{ background: {p["champ"]}; border-radius: {RAYON}px; }}
#bulle-moi {{ background: {BLEU}; border-radius: 18px; border-bottom-right-radius: 6px; }}
#bulle-autre {{ background: {p["bulle"]}; border-radius: 18px; border-bottom-left-radius: 6px; }}
#separation {{ background: {p["lisere"]}; }}
#apercu {{ background: {p["champ"]}; border-radius: 14px; }}
#vignette {{ background: {p["bleu_pale"]}; border-radius: 14px; }}

QLabel {{ background: transparent; }}
QLabel[role="logo-titre"] {{ color: {BLEU}; font-size: 40px; font-weight: 800; letter-spacing: -1px; }}
QLabel[role="accroche"] {{ font-size: 19px; font-weight: 500; }}
QLabel[role="sous-titre"] {{ font-size: 16px; font-weight: 700; }}
QLabel[role="doux"] {{ color: {p["doux"]}; }}
QLabel[role="petit"] {{ color: {p["doux"]}; font-size: 11px; }}
QLabel[role="meta-moi"] {{ color: rgba(255, 255, 255, 0.75); font-size: 11px; }}
QLabel[role="section"] {{ color: {p["doux"]}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel[role="ip"] {{ font-size: 24px; font-weight: 700; letter-spacing: 1px; }}
QLabel[role="note"] {{ color: {p["doux"]}; font-size: 11px; padding: 4px 12px;
                       background: {p["champ"]}; border-radius: 10px; }}
QLabel[role="en-ligne"] {{ color: {VERT}; font-size: 11px; font-weight: 600; }}
QLabel[role="erreur"] {{ color: {ROUGE}; }}
QLabel#bulle-texte {{ font-size: 14px; }}
#bulle-moi QLabel#bulle-texte {{ color: white; }}

QPushButton {{ border: none; border-radius: {RAYON}px; padding: 11px 22px; font-weight: 700; min-height: 18px; }}
QPushButton[role="principal"] {{ background: {BLEU}; color: white; font-size: 14px; }}
QPushButton[role="principal"]:hover {{ background: {BLEU_SURVOL}; }}
QPushButton[role="principal"]:disabled {{ background: {p["bleu_pale"]}; color: {p["doux"]}; }}
QPushButton[role="vert"] {{ background: {VERT}; color: white; font-size: 14px; }}
QPushButton[role="vert"]:hover {{ background: #36A420; }}
QPushButton[role="vert"]:disabled {{ background: {p["champ"]}; color: {p["doux"]}; }}
QPushButton[role="secondaire"] {{ background: {p["champ"]}; }}
QPushButton[role="secondaire"]:hover {{ background: {p["survol"]}; }}
QPushButton[role="onglet"] {{ background: transparent; color: {p["doux"]}; padding: 11px 16px; }}
QPushButton[role="onglet"]:checked {{ background: {p["bleu_pale"]}; color: {BLEU}; }}
QPushButton[role="icone"] {{ background: transparent; padding: 0; min-height: 0; }}
QPushButton[role="icone"]:hover {{ background: {p["champ"]}; }}
QPushButton[role="salon"] {{ background: {p["champ"]}; text-align: left; padding: 12px 18px; font-weight: 600; }}
QPushButton[role="salon"]:hover {{ background: {p["bleu_pale"]}; color: {BLEU}; }}

QLineEdit {{
    background: {p["champ"]}; border: 1px solid {p["lisere"]}; border-radius: {RAYON}px;
    padding: 11px 18px; min-height: 18px; font-size: 14px; selection-background-color: {BLEU};
    selection-color: white;
}}
QLineEdit:focus {{ border-color: {BLEU}; background: {p["carte"]}; }}
QLineEdit#champ-message, QLineEdit#champ-message:focus {{ background: transparent; border: none; padding: 8px 4px; }}

QProgressBar {{ background: {p["champ"]}; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {BLEU}; border-radius: 3px; }}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ width: 8px; background: transparent; margin: 6px 2px; }}
QScrollBar::handle:vertical {{ background: {p["lisere"]}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    height: 0; background: none;
}}
"""


def appliquer(nouveau_mode: str) -> None:
    """Change de thème à chaud : feuille de style et icônes déjà affichées."""
    global mode
    mode = nouveau_mode if nouveau_mode in PALETTES else "clair"
    app = QApplication.instance()
    app.setStyleSheet(qss())
    for w in app.allWidgets():
        if isinstance(w, QPushButton) and w.property("icone"):
            couleur = w.property("couleur-icone") or c("doux")
            w.setIcon(icone(w.property("icone"), couleur, w.iconSize().width()))
        if isinstance(effet := w.graphicsEffect(), QGraphicsDropShadowEffect):
            effet.setColor(QColor(c("ombre")))
        w.update()


def charger_police() -> None:
    # Fichiers statiques, un par graisse : Qt n'applique pas font-weight aux polices variables.
    for fichier in (RESSOURCES / "polices").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fichier))


def teinte(pseudo: str) -> str:
    return TEINTES[sum(pseudo.lower().encode()) % len(TEINTES)]


def _rendu(svg: bytes, taille: int) -> QPixmap:
    pix = QPixmap(QSize(taille, taille) * 2)  # rendu net sur écrans haute densité
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    QSvgRenderer(QByteArray(svg)).render(p)
    p.end()
    pix.setDevicePixelRatio(2)
    return pix


@cache
def icone(nom: str, couleur: str, taille: int = 20) -> QIcon:
    """Icône Lucide (ressources/icones) recolorée."""
    svg = (RESSOURCES / "icones" / f"{nom}.svg").read_bytes()
    return QIcon(_rendu(svg.replace(b"currentColor", couleur.encode()), taille))


@cache
def logo(taille: int = 64) -> QPixmap:
    return _rendu((RESSOURCES / "logo.svg").read_bytes(), taille)
