"""Briques d'interface : fond uni, panneaux de verre, boutons, avatars."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import theme

class Fond(QWidget):
    """Fond uni très sombre, sans dégradé."""

    def paintEvent(self, _event) -> None:
        QPainter(self).fillRect(self.rect(), QColor(theme.NUIT))


class Verre(QFrame):
    """Panneau translucide ; `self.lay` est sa mise en page."""

    def __init__(self, marges: int = 24, espacement: int = 14, fin: bool = False, horizontal: bool = False):
        super().__init__()
        self.setObjectName("verre-fin" if fin else "verre")
        self.lay = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        self.lay.setContentsMargins(marges, marges, marges, marges)
        self.lay.setSpacing(espacement)


def label(texte: str = "", role: str | None = None) -> QLabel:
    l = QLabel(texte)
    if role:
        l.setProperty("role", role)
    return l


def bouton(texte: str, role: str = "principal", icone: str | None = None) -> QPushButton:
    b = QPushButton(texte)
    b.setProperty("role", role)
    b.setCursor(Qt.PointingHandCursor)
    if icone:
        b.setIcon(theme.icone(icone, "#FFFFFF" if role == "principal" else theme.TEXTE, 18))
        b.setIconSize(QSize(18, 18))
    return b


def bouton_icone(icone: str, aide: str, taille: int = 40, couleur: str = theme.TEXTE) -> QPushButton:
    b = QPushButton()
    b.setProperty("role", "icone")
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedSize(taille, taille)
    b.setStyleSheet(f"border-radius: {min(theme.RAYON, taille // 2)}px;")
    b.setIcon(theme.icone(icone, couleur, 20))
    b.setIconSize(QSize(20, 20))
    b.setToolTip(aide)
    return b


def avatar(pseudo: str, taille: int = 34) -> QLabel:
    a = QLabel(pseudo[:1].upper())
    a.setFixedSize(taille, taille)
    a.setAlignment(Qt.AlignCenter)
    couleur = QColor(theme.teinte(pseudo))
    rgb = f"{couleur.red()}, {couleur.green()}, {couleur.blue()}"  # Qt lit #AARRGGBB, pas #RRGGBBAA
    a.setStyleSheet(f"background: rgba({rgb}, 0.2); color: {couleur.name()}; border: 1px solid rgba({rgb}, 0.4);"
                    f"border-radius: {taille // 2}px; font-weight: 700; font-size: {taille * 2 // 5}px;")
    return a
