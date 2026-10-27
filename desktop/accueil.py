"""Écran d'accueil : votre IP, rejoindre un salon par IP ou par découverte, ou en créer un."""

from __future__ import annotations

import getpass
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from chat.decouverte import decouvrir, ip_locale, normaliser
from chat.protocole import pseudo_valide

from . import theme
from .widgets import Verre, bouton, bouton_icone, label


class _Signaux(QObject):
    salons = Signal(list)


class Accueil(QWidget):
    rejoindre = Signal(str, str, str)  # url, pseudo, nom du salon
    creer = Signal(str)                # pseudo

    def __init__(self):
        super().__init__()
        self.ip = ip_locale()
        self.signaux = _Signaux()
        self.signaux.salons.connect(self._salons_trouves)
        self._construire()
        self.rechercher()

    def _construire(self) -> None:
        externe = QGridLayout(self)
        externe.setContentsMargins(32, 32, 32, 32)
        carte = Verre(marges=40, espacement=40, horizontal=True)
        carte.setMaximumSize(1040, 640)
        externe.addWidget(carte, 0, 0, Qt.AlignCenter)

        # Colonne gauche : identité + votre IP + créer
        gauche = QVBoxLayout()
        gauche.setSpacing(16)
        logo = label()
        logo.setPixmap(theme.logo(76))
        gauche.addWidget(logo)
        gauche.addWidget(label("LocalNet", "titre"))
        accroche = label("Discutez et partagez photos et vidéos avec les appareils de votre réseau. "
                         "Rien ne sort de chez vous.", "doux")
        accroche.setWordWrap(True)
        gauche.addWidget(accroche)
        gauche.addSpacing(8)

        bloc_ip = Verre(marges=18, espacement=4, fin=True)
        bloc_ip.lay.addWidget(label("VOTRE ADRESSE IP", "section"))
        ligne_ip = QHBoxLayout()
        ligne_ip.addWidget(label(self.ip, "ip"))
        ligne_ip.addStretch()
        self.copier = bouton_icone("copy", "Copier l'adresse", 36)
        self.copier.clicked.connect(self._copier_ip)
        ligne_ip.addWidget(self.copier)
        bloc_ip.lay.addLayout(ligne_ip)
        self.aide_ip = label("Les autres vous rejoignent avec cette IP une fois le salon créé.", "petit")
        self.aide_ip.setWordWrap(True)
        bloc_ip.lay.addWidget(self.aide_ip)
        gauche.addWidget(bloc_ip)
        gauche.addStretch()

        self.bouton_creer = bouton("Créer un salon sur ce PC", icone="plus")
        self.bouton_creer.clicked.connect(self._creer)
        gauche.addWidget(self.bouton_creer)

        # Colonne droite : pseudo + rejoindre
        droite = QVBoxLayout()
        droite.setSpacing(10)
        droite.addWidget(label("VOTRE PSEUDO", "section"))
        self.pseudo = QLineEdit(getpass.getuser() if pseudo_valide(getpass.getuser()) else "")
        self.pseudo.setPlaceholderText("ex. alice")
        self.pseudo.setMaxLength(20)
        droite.addWidget(self.pseudo)
        droite.addSpacing(14)

        droite.addWidget(label("REJOINDRE PAR IP", "section"))
        ligne = QHBoxLayout()
        ligne.setSpacing(10)
        self.adresse = QLineEdit()
        self.adresse.setPlaceholderText("192.168.1.42")
        self.adresse.returnPressed.connect(self._rejoindre_ip)
        ligne.addWidget(self.adresse, 1)
        aller = bouton("Rejoindre", icone="arrow-right")
        aller.clicked.connect(self._rejoindre_ip)
        ligne.addWidget(aller)
        droite.addLayout(ligne)
        droite.addSpacing(14)

        entete = QHBoxLayout()
        entete.addWidget(label("SALONS DÉTECTÉS", "section"))
        entete.addStretch()
        self.actualiser = bouton_icone("refresh-cw", "Chercher à nouveau", 30)
        self.actualiser.clicked.connect(self.rechercher)
        entete.addWidget(self.actualiser)
        droite.addLayout(entete)
        self.liste = QVBoxLayout()
        self.liste.setSpacing(8)
        droite.addLayout(self.liste)
        droite.addStretch()

        self.message = label("", "erreur")
        self.message.setWordWrap(True)
        droite.addWidget(self.message)

        carte.lay.addLayout(gauche, 5)
        carte.lay.addLayout(droite, 6)

    # --- Actions ------------------------------------------------------------

    def _pseudo(self) -> str | None:
        pseudo = self.pseudo.text().strip()
        if pseudo_valide(pseudo):
            return pseudo
        self.erreur("Pseudo : 1 à 20 caractères (lettres, chiffres, « . », « _ », « - »).")
        self.pseudo.setFocus()
        return None

    def _rejoindre_ip(self) -> None:
        adresse = self.adresse.text().strip()
        if not adresse:
            self.adresse.setFocus()
            return
        if pseudo := self._pseudo():
            self.rejoindre.emit(normaliser(adresse), pseudo, adresse)

    def _creer(self) -> None:
        if pseudo := self._pseudo():
            self.bouton_creer.setEnabled(False)
            self.bouton_creer.setText("Ouverture du salon…")
            self.creer.emit(pseudo)

    def creation_finie(self) -> None:
        self.bouton_creer.setEnabled(True)
        self.bouton_creer.setText("Créer un salon sur ce PC")

    def _copier_ip(self) -> None:
        QApplication.clipboard().setText(self.ip)
        self.copier.setIcon(theme.icone("copy", theme.SAUGE, 20))
        QTimer.singleShot(1200, lambda: self.copier.setIcon(theme.icone("copy", theme.TEXTE, 20)))

    def erreur(self, texte: str) -> None:
        self.message.setText(texte)

    # --- Découverte mDNS ----------------------------------------------------

    def rechercher(self) -> None:
        self._vider()
        self.liste.addWidget(label("Recherche sur le réseau…", "petit"))
        self.actualiser.setEnabled(False)
        threading.Thread(target=lambda: self.signaux.salons.emit(decouvrir()), daemon=True).start()

    def _vider(self) -> None:
        while self.liste.count():
            if w := self.liste.takeAt(0).widget():
                w.deleteLater()

    def _salons_trouves(self, salons: list) -> None:
        self._vider()
        self.actualiser.setEnabled(True)
        if not salons:
            self.liste.addWidget(label("Aucun salon annoncé. Entrez une IP ou créez-en un.", "petit"))
            return
        for nom, url in salons:
            b = bouton(f"{nom}    ·    {url.removeprefix('ws://')}", "salon", icone="wifi")
            b.clicked.connect(lambda _=False, u=url, n=nom: (p := self._pseudo()) and self.rejoindre.emit(u, p, n))
            self.liste.addWidget(b)
