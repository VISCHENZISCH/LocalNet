"""Briques d'interface : fond, cartes, boutons, avatars ronds."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from . import theme


class Fond(QWidget):
    """Fond uni de la fenêtre, selon le thème."""

    def paintEvent(self, _event) -> None:
        QPainter(self).fillRect(self.rect(), QColor(theme.c("fond")))


class Carte(QFrame):
    """Panneau du thème (blanc en clair) avec ombre douce ; `self.lay` est sa mise en page."""

    def __init__(self, marges: int = 24, espacement: int = 14, fine: bool = False,
                 horizontal: bool = False, ombre: bool = True):
        super().__init__()
        self.setObjectName("carte-fine" if fine else "carte")
        self.lay = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        self.lay.setContentsMargins(marges, marges, marges, marges)
        self.lay.setSpacing(espacement)
        if ombre and not fine:
            effet = QGraphicsDropShadowEffect(self)
            effet.setBlurRadius(24)
            effet.setOffset(0, 2)
            effet.setColor(QColor(theme.c("ombre")))
            self.setGraphicsEffect(effet)


def label(texte: str = "", role: str | None = None) -> QLabel:
    l = QLabel(texte)
    if role:
        l.setProperty("role", role)
    return l


def _iconifier(b: QPushButton, icone: str, couleur: str | None, taille: int) -> None:
    # Propriétés relues par theme.appliquer() pour recolorer au changement de thème.
    b.setProperty("icone", icone)
    b.setProperty("couleur-icone", couleur)
    b.setIcon(theme.icone(icone, couleur or theme.c("doux"), taille))
    b.setIconSize(QSize(taille, taille))


def bouton(texte: str, role: str = "principal", icone: str | None = None) -> QPushButton:
    b = QPushButton(texte)
    b.setProperty("role", role)
    b.setCursor(Qt.PointingHandCursor)
    if icone:
        blanc = role in ("principal", "vert")
        _iconifier(b, icone, "#FFFFFF" if blanc else None, 18)
    return b


def bouton_icone(icone: str, aide: str, taille: int = 40, couleur: str | None = None) -> QPushButton:
    b = QPushButton()
    b.setProperty("role", "icone")
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedSize(taille, taille)
    b.setStyleSheet(f"border-radius: {min(theme.RAYON, taille // 2)}px;")
    _iconifier(b, icone, couleur, 20)
    b.setToolTip(aide)
    return b


def arrondir(pix: QPixmap, rayon: float) -> QPixmap:
    sortie = QPixmap(pix.size())
    sortie.fill(Qt.transparent)
    p = QPainter(sortie)
    p.setRenderHint(QPainter.Antialiasing)
    chemin = QPainterPath()
    chemin.addRoundedRect(QRectF(sortie.rect()), rayon, rayon)
    p.setClipPath(chemin)
    p.drawPixmap(0, 0, pix)
    p.end()
    return sortie


def carre(pix: QPixmap, cote: int) -> QPixmap:
    """Recadre au centre et met à l'échelle en carré."""
    pix = pix.scaled(cote, cote, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    return pix.copy((pix.width() - cote) // 2, (pix.height() - cote) // 2, cote, cote)


class Avatar(QWidget):
    """Photo de profil ronde, ou initiale sur pastille colorée.

    `photos` (desktop.client.Photos) fournit les images et prévient quand elles
    changent : l'avatar se redessine seul.
    """

    def __init__(self, pseudo: str, taille: int = 36, photos=None):
        super().__init__()
        self.pseudo, self.taille, self.photos = pseudo, taille, photos
        self.setFixedSize(taille, taille)
        self.setToolTip(pseudo)
        if photos is not None:
            photos.modifie.connect(self._modifie)

    def _modifie(self, pseudo: str) -> None:
        if pseudo.lower() == self.pseudo.lower():
            self.update()

    def changer(self, pseudo: str) -> None:
        self.pseudo = pseudo
        self.setToolTip(pseudo)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        cercle = QPainterPath()
        cercle.addEllipse(QRectF(self.rect()))
        pix = self.photos.pour(self.pseudo) if self.photos else None
        if pix is not None and not pix.isNull():
            p.setClipPath(cercle)
            p.drawPixmap(self.rect(), pix)
            return
        p.fillPath(cercle, QColor(theme.teinte(self.pseudo or "?")))
        police = QFont(theme.POLICE)
        police.setPixelSize(int(self.taille * 0.42))
        police.setWeight(QFont.Bold)
        p.setFont(police)
        p.setPen(QColor("white"))
        p.drawText(self.rect(), Qt.AlignCenter, (self.pseudo or "?")[:1].upper())
