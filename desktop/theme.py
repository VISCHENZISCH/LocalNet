"""Thème sombre « verre dépoli » : fond uni très sombre, panneaux translucides, accents verts.

Attention : Qt ignore border-radius s'il dépasse la moitié de la hauteur du
widget ; boutons et champs font au moins 40 px de haut pour leurs 20 px.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

RESSOURCES = Path(__file__).resolve().parent / "ressources"

NUIT = "#080A08"
TEXTE = "#EEF3EE"
TEXTE_DOUX = "rgba(222, 232, 223, 0.55)"
VERRE = "rgba(255, 255, 255, 0.05)"
VERRE_FORT = "rgba(255, 255, 255, 0.09)"
LISERE = "rgba(255, 255, 255, 0.10)"
VERT = "#58855C"
SAUGE = "#9EB8A0"
FORET = "#0D3311"
ROUGE = "#E58A7F"
RAYON = 20  # boutons et champs

POLICE = "Plus Jakarta Sans"  # ressources/polices, licence OFL

# Couleur stable par pseudo, lisible sur fond sombre et accordée aux verts.
TEINTES = ["#9EB8A0", "#D8C08A", "#D99A7A", "#B9A3C9", "#A9C46C", "#E0B3A0", "#8FBFAE", "#C9C9A0"]

QSS = f"""
* {{ font-family: "{POLICE}"; color: {TEXTE}; font-size: 13px; }}
QMainWindow {{ background: {NUIT}; }}
QToolTip {{ background: {FORET}; color: {TEXTE}; border: 1px solid {VERT}; padding: 6px 8px; }}

#verre {{ background: {VERRE}; border: 1px solid {LISERE}; border-radius: 24px; }}
#verre-fin {{ background: {VERRE}; border: 1px solid {LISERE}; border-radius: 16px; }}
#saisie {{ background: {VERRE}; border: 1px solid {LISERE}; border-radius: {RAYON}px; }}
#bulle-moi {{ background: {VERT}; border-radius: 18px; border-bottom-right-radius: 6px; }}
#bulle-autre {{ background: {VERRE_FORT}; border: 1px solid {LISERE};
               border-radius: 18px; border-bottom-left-radius: 6px; }}

QLabel {{ background: transparent; }}
QLabel[role="titre"] {{ font-size: 30px; font-weight: 800; letter-spacing: -0.5px; }}
QLabel[role="sous-titre"] {{ font-size: 16px; font-weight: 700; }}
QLabel[role="doux"] {{ color: {TEXTE_DOUX}; }}
QLabel[role="petit"] {{ color: {TEXTE_DOUX}; font-size: 11px; }}
QLabel[role="section"] {{ color: {SAUGE}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel[role="ip"] {{ font-size: 24px; font-weight: 700; letter-spacing: 1px; }}
QLabel[role="note"] {{ color: {TEXTE_DOUX}; font-size: 11px; padding: 4px 12px;
                       background: {VERRE}; border-radius: 10px; }}
QLabel[role="erreur"] {{ color: {ROUGE}; }}

QPushButton {{ border: none; border-radius: {RAYON}px; padding: 11px 22px; font-weight: 600; min-height: 18px; }}
QPushButton[role="principal"] {{ background: {VERT}; color: white; }}
QPushButton[role="principal"]:hover {{ background: {SAUGE}; color: {FORET}; }}
QPushButton[role="principal"]:disabled {{ background: {FORET}; color: {TEXTE_DOUX}; }}
QPushButton[role="verre"] {{ background: {VERRE}; border: 1px solid {LISERE}; }}
QPushButton[role="verre"]:hover {{ background: {FORET}; border-color: {VERT}; }}
QPushButton[role="icone"] {{ background: transparent; padding: 0; min-height: 0; }}
QPushButton[role="icone"]:hover {{ background: {VERRE_FORT}; }}
QPushButton[role="salon"] {{ background: {VERRE}; border: 1px solid {LISERE}; text-align: left;
                             padding: 12px 18px; font-weight: 500; }}
QPushButton[role="salon"]:hover {{ background: {FORET}; border-color: {VERT}; }}

QLineEdit {{
    background: rgba(0, 0, 0, 0.35); border: 1px solid {LISERE}; border-radius: {RAYON}px;
    padding: 11px 18px; min-height: 18px; selection-background-color: {VERT};
}}
QLineEdit:focus {{ border-color: {SAUGE}; }}

QProgressBar {{ background: {VERRE}; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {VERT}; border-radius: 3px; }}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ width: 8px; background: transparent; margin: 6px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 0.15); border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    height: 0; background: none;
}}
"""


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
def icone(nom: str, couleur: str = TEXTE, taille: int = 20) -> QIcon:
    """Icône Lucide (ressources/icones) recolorée."""
    svg = (RESSOURCES / "icones" / f"{nom}.svg").read_bytes()
    return QIcon(_rendu(svg.replace(b"currentColor", couleur.encode()), taille))


def charger_police() -> None:
    # Fichiers statiques, un par graisse : Qt n'applique pas font-weight aux polices variables.
    for fichier in (RESSOURCES / "polices").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fichier))


@cache
def logo(taille: int = 64) -> QPixmap:
    return _rendu((RESSOURCES / "logo.svg").read_bytes(), taille)
