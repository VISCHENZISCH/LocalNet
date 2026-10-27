"""Écran d'accueil : présentation et IP à gauche, connexion au salon à droite."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget,
)

from chat.decouverte import decouvrir, ip_locale, normaliser
from chat.protocole import PORT_DEFAUT, mot_de_passe_valide, pseudo_valide

from . import reglages, theme
from .widgets import Carte, bouton, bouton_icone, label


class _Signaux(QObject):
    salons = Signal(list)


class Accueil(QWidget):
    rejoindre = Signal(str, str, str, bool, str)  # url, utilisateur, mot de passe, nouveau compte, nom
    heberger = Signal(str, str, bool)             # utilisateur, mot de passe, nouveau compte
    parametres = Signal()

    def __init__(self):
        super().__init__()
        self.ip = ip_locale()
        self.signaux = _Signaux()
        self.signaux.salons.connect(self._salons_trouves)
        self._construire()
        self.rechercher()

    def _construire(self) -> None:
        externe = QVBoxLayout(self)
        externe.setContentsMargins(24, 16, 24, 24)
        haut = QHBoxLayout()
        haut.addStretch()
        reglages_btn = bouton_icone("settings", "Paramètres (photo de profil, thème)", 40)
        reglages_btn.clicked.connect(self.parametres)
        haut.addWidget(reglages_btn)
        externe.addLayout(haut)

        centre = QGridLayout()
        externe.addLayout(centre, 1)
        contenu = QWidget()
        contenu.setMaximumWidth(1000)
        centre.addWidget(contenu, 0, 0, Qt.AlignCenter)
        colonnes = QHBoxLayout(contenu)
        colonnes.setSpacing(64)

        # Gauche : identité + votre IP
        gauche = QVBoxLayout()
        gauche.setSpacing(14)
        gauche.addStretch()
        marque = QHBoxLayout()
        marque.setSpacing(14)
        logo = label()
        logo.setPixmap(theme.logo(64))
        marque.addWidget(logo)
        marque.addWidget(label("LocalNet", "logo-titre"))
        marque.addStretch()
        gauche.addLayout(marque)
        accroche = label("Discutez et partagez photos et vidéos avec les appareils de votre réseau.",
                         "accroche")
        accroche.setWordWrap(True)
        gauche.addWidget(accroche)
        gauche.addSpacing(10)

        bloc_ip = Carte(marges=18, espacement=4)
        bloc_ip.lay.addWidget(label("VOTRE ADRESSE IP", "section"))
        ligne_ip = QHBoxLayout()
        ligne_ip.addWidget(label(self.ip, "ip"))
        ligne_ip.addStretch()
        self.copier = bouton_icone("copy", "Copier l'adresse", 36)
        self.copier.clicked.connect(self._copier_ip)
        ligne_ip.addWidget(self.copier)
        bloc_ip.lay.addLayout(ligne_ip)
        aide = label("Hébergez un salon : les autres le rejoignent avec cette IP.", "petit")
        aide.setWordWrap(True)
        bloc_ip.lay.addWidget(aide)
        gauche.addWidget(bloc_ip)
        gauche.addStretch()
        colonnes.addLayout(gauche, 1)

        # Droite : carte de connexion
        carte = Carte(marges=24, espacement=10)
        carte.setFixedWidth(420)
        onglets = QHBoxLayout()
        onglets.setSpacing(6)
        self.groupe = QButtonGroup(self)
        self.onglet_connexion = bouton("Se connecter", "onglet", icone="log-in")
        self.onglet_creation = bouton("Créer un compte", "onglet", icone="user-plus")
        for b in (self.onglet_connexion, self.onglet_creation):
            b.setCheckable(True)
            b.clicked.connect(self._mode)
            self.groupe.addButton(b)
            onglets.addWidget(b, 1)
        carte.lay.addLayout(onglets)
        carte.lay.addSpacing(6)

        self.utilisateur = QLineEdit(reglages.lire("utilisateur"))
        self.utilisateur.setPlaceholderText("Nom d'utilisateur")
        self.utilisateur.setMaxLength(20)
        self.mot_de_passe = QLineEdit()
        self.mot_de_passe.setPlaceholderText("Mot de passe")
        self.mot_de_passe.setEchoMode(QLineEdit.Password)
        self.mot_de_passe.setMaxLength(64)
        self.adresse = QLineEdit()
        self.adresse.setPlaceholderText("IP du salon, ex. 192.168.1.42")
        for champ in (self.utilisateur, self.mot_de_passe, self.adresse):
            champ.returnPressed.connect(self._rejoindre)
            carte.lay.addWidget(champ)

        self.valider = bouton("Se connecter")
        self.valider.clicked.connect(self._rejoindre)
        carte.lay.addWidget(self.valider)
        self.message = label("", "erreur")
        self.message.setWordWrap(True)
        self.message.hide()
        carte.lay.addWidget(self.message)

        carte.lay.addWidget(self._separation())
        entete = QHBoxLayout()
        entete.addWidget(label("SALONS DÉTECTÉS", "section"))
        entete.addStretch()
        self.actualiser = bouton_icone("refresh-cw", "Chercher à nouveau", 32)
        self.actualiser.clicked.connect(self.rechercher)
        entete.addWidget(self.actualiser)
        carte.lay.addLayout(entete)
        self.liste = QVBoxLayout()
        self.liste.setSpacing(6)
        carte.lay.addLayout(self.liste)

        carte.lay.addWidget(self._separation())
        self.bouton_heberger = bouton("Héberger un salon sur ce PC", "vert", icone="plus")
        self.bouton_heberger.clicked.connect(self._heberger)
        carte.lay.addWidget(self.bouton_heberger)
        colonnes.addWidget(carte, 0, Qt.AlignVCenter)

        (self.onglet_connexion if self.utilisateur.text() else self.onglet_creation).setChecked(True)
        self._mode()

    @staticmethod
    def _separation() -> QFrame:
        trait = QFrame()
        trait.setObjectName("separation")
        trait.setFixedHeight(1)
        return trait

    def _mode(self) -> None:
        nouveau = self.onglet_creation.isChecked()
        self.valider.setText("Créer le compte et rejoindre" if nouveau else "Se connecter")
        self.mot_de_passe.setPlaceholderText("Mot de passe (4 caractères min.)" if nouveau else "Mot de passe")
        self.erreur("")

    # --- Actions ------------------------------------------------------------

    def _identifiants(self) -> tuple[str, str, bool] | None:
        pseudo, mdp = self.utilisateur.text().strip(), self.mot_de_passe.text()
        if not pseudo_valide(pseudo):
            self.erreur("Nom d'utilisateur : 1 à 20 caractères (lettres, chiffres, « . », « _ », « - »).")
            self.utilisateur.setFocus()
            return None
        if not mot_de_passe_valide(mdp):
            self.erreur("Le mot de passe doit faire de 4 à 64 caractères.")
            self.mot_de_passe.setFocus()
            return None
        reglages.ecrire("utilisateur", pseudo)
        return pseudo, mdp, self.onglet_creation.isChecked()

    def _rejoindre(self) -> None:
        if not (ids := self._identifiants()):
            return
        adresse = self.adresse.text().strip()
        if not adresse:
            self.erreur("Entrez l'IP du salon, choisissez un salon détecté ou hébergez-en un.")
            self.adresse.setFocus()
            return
        self.rejoindre.emit(normaliser(adresse), *ids, adresse)

    def _heberger(self) -> None:
        if ids := self._identifiants():
            self.bouton_heberger.setEnabled(False)
            self.bouton_heberger.setText("Ouverture du salon…")
            self.heberger.emit(*ids)

    def hebergement_fini(self) -> None:
        self.bouton_heberger.setEnabled(True)
        self.bouton_heberger.setText("Héberger un salon sur ce PC")

    def _copier_ip(self) -> None:
        QApplication.clipboard().setText(self.ip)
        self.copier.setIcon(theme.icone("copy", theme.VERT, 20))
        QTimer.singleShot(1200, lambda: self.copier.setIcon(theme.icone("copy", theme.c("doux"), 20)))

    def erreur(self, texte: str) -> None:
        self.message.setText(texte)
        self.message.setVisible(bool(texte))

    def vider_mot_de_passe(self) -> None:
        self.mot_de_passe.clear()

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
            self.liste.addWidget(label("Aucun salon annoncé pour l'instant.", "petit"))
            return
        for nom, url in salons:
            ip = url.removeprefix("ws://").removesuffix(f":{PORT_DEFAUT}")
            b = bouton(f"{nom}  ·  {ip}", "salon", icone="wifi")
            b.setToolTip("Utiliser ce salon")
            b.clicked.connect(lambda _=False, a=ip: self.adresse.setText(a))
            self.liste.addWidget(b)
