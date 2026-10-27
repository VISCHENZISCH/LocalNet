"""Fenêtre « Paramètres » : photo de profil et thème clair / sombre."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QDialog, QFileDialog, QHBoxLayout, QVBoxLayout

from . import reglages, theme
from .client import Photos
from .widgets import Avatar, Carte, bouton, label


class Parametres(QDialog):
    photo_changee = Signal()  # la photo de ce PC a été choisie ou retirée

    def __init__(self, parent, photos: Photos, pseudo: str):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self.setMinimumWidth(460)
        self.photos, self.pseudo = photos, pseudo or "?"

        racine = QVBoxLayout(self)
        racine.setContentsMargins(20, 20, 20, 20)
        carte = Carte(marges=28, espacement=14, ombre=False)
        racine.addWidget(carte)
        carte.lay.addWidget(label("Paramètres", "sous-titre"))
        carte.lay.addSpacing(6)

        carte.lay.addWidget(label("PHOTO DE PROFIL", "section"))
        ligne = QHBoxLayout()
        ligne.setSpacing(20)
        ligne.addWidget(Avatar(self.pseudo, 96, photos))
        actions = QVBoxLayout()
        actions.setSpacing(8)
        choisir = bouton("Choisir une photo", icone="camera")
        choisir.clicked.connect(self._choisir)
        self.retirer = bouton("Retirer", "secondaire", icone="trash-2")
        self.retirer.clicked.connect(self._retirer)
        self.retirer.setEnabled(reglages.octets_photo() is not None)
        actions.addWidget(choisir)
        actions.addWidget(self.retirer)
        aide = label("Visible par les membres des salons que vous rejoignez.", "petit")
        aide.setWordWrap(True)
        actions.addWidget(aide)
        ligne.addLayout(actions, 1)
        carte.lay.addLayout(ligne)
        carte.lay.addSpacing(10)

        carte.lay.addWidget(label("APPARENCE", "section"))
        onglets = QHBoxLayout()
        onglets.setSpacing(6)
        groupe = QButtonGroup(self)
        for mode, texte, icone in (("clair", "Clair", "sun"), ("sombre", "Sombre", "moon")):
            b = bouton(texte, "onglet", icone=icone)
            b.setCheckable(True)
            b.setChecked(theme.mode == mode)
            b.clicked.connect(lambda _=False, m=mode: self._theme(m))
            groupe.addButton(b)
            onglets.addWidget(b)
        onglets.addStretch()
        carte.lay.addLayout(onglets)
        carte.lay.addSpacing(10)

        fermer = bouton("Terminé")
        fermer.clicked.connect(self.accept)
        carte.lay.addWidget(fermer)

    def _choisir(self) -> None:
        chemin, _ = QFileDialog.getOpenFileName(self, "Photo de profil", str(Path.home()),
                                                "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if not chemin:
            return
        if reglages.enregistrer_photo(Path(chemin)):
            self.photos.definir_locale(self.pseudo, reglages.photo())
            self.retirer.setEnabled(True)
            self.photo_changee.emit()

    def _retirer(self) -> None:
        reglages.supprimer_photo()
        self.photos.definir_locale(self.pseudo, None)
        self.retirer.setEnabled(False)
        self.photo_changee.emit()

    def _theme(self, mode: str) -> None:
        theme.appliquer(mode)
        reglages.ecrire("theme", mode)
