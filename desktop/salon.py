"""Écran du salon : membres à gauche, fil de discussion et saisie à droite."""

from __future__ import annotations

import shutil
from pathlib import Path
from collections.abc import Callable

from PySide6.QtCore import QSize, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QScrollArea,
    QVBoxLayout, QWidget,
)

from chat.protocole import EXTENSIONS, taille_lisible

from . import theme
from .client import ClientSalon
from .widgets import Avatar, Carte, arrondir, bouton_icone, label

LARGEUR_BULLE = 460
IMAGE_MAX = QSize(420, 320)
TAILLE_AVATAR_FIL = 30


class Cliquable(QLabel):
    def __init__(self, action: Callable[[], None]):
        super().__init__()
        self.action = action
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.action()


def enregistrer(chemin: Path, nom: str) -> Path:
    """Copie le fichier dans ~/Téléchargements/LocalNet et renvoie la destination."""
    dossier = Path(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)) / "LocalNet"
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / nom
    n = 1
    while cible.exists():
        cible = dossier / f"{Path(nom).stem} ({n}){Path(nom).suffix}"
        n += 1
    shutil.copy2(chemin, cible)
    return cible


class Salon(QWidget):
    quitter = Signal()
    parametres = Signal()

    def __init__(self, client: ClientSalon):
        super().__init__()
        self.client = client
        self.photos = client.photos
        self.dernier_auteur: str | None = None
        self.setAcceptDrops(True)
        self._construire()

        client.bienvenue.connect(self._bienvenue)
        client.recu.connect(self._recu)
        client.membres.connect(self._membres)
        client.note.connect(self._note)
        client.etat.connect(self._etat)
        client.envoi.connect(self._progression)

    # --- Construction -------------------------------------------------------

    def _construire(self) -> None:
        racine = QHBoxLayout(self)
        racine.setContentsMargins(16, 16, 16, 16)
        racine.setSpacing(16)

        # Barre latérale
        cote = Carte(marges=20, espacement=12)
        cote.setFixedWidth(280)
        marque = QHBoxLayout()
        marque.setSpacing(10)
        logo = label()
        logo.setPixmap(theme.logo(36))
        marque.addWidget(logo)
        marque.addWidget(label("LocalNet", "sous-titre"))
        marque.addStretch()
        cote.lay.addLayout(marque)
        cote.lay.addSpacing(10)

        cote.lay.addWidget(label("SALON", "section"))
        bloc = Carte(marges=14, espacement=2, fine=True)
        self.nom_salon = label("", "sous-titre")
        bloc.lay.addWidget(self.nom_salon)
        ligne = QHBoxLayout()
        self.adresse = label("", "doux")
        self.adresse.setTextInteractionFlags(Qt.TextSelectableByMouse)
        ligne.addWidget(self.adresse)
        ligne.addStretch()
        copier = bouton_icone("copy", "Copier l'adresse du salon", 30)
        copier.clicked.connect(lambda: QApplication.clipboard().setText(self.adresse.text()))
        ligne.addWidget(copier)
        bloc.lay.addLayout(ligne)
        cote.lay.addWidget(bloc)
        cote.lay.addSpacing(8)

        self.titre_membres = label("EN LIGNE", "section")
        cote.lay.addWidget(self.titre_membres)
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        zone.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        contenu = QWidget()
        self.liste_membres = QVBoxLayout(contenu)
        self.liste_membres.setContentsMargins(0, 0, 0, 0)
        self.liste_membres.setSpacing(10)
        zone.setWidget(contenu)
        cote.lay.addWidget(zone, 1)

        # Votre profil, en bas
        trait = QFrame()
        trait.setObjectName("separation")
        trait.setFixedHeight(1)
        cote.lay.addWidget(trait)
        profil = QHBoxLayout()
        profil.setSpacing(10)
        self.mon_avatar = Avatar("", 40, self.photos)
        profil.addWidget(self.mon_avatar)
        infos = QVBoxLayout()
        infos.setSpacing(0)
        self.mon_nom = label("", "sous-titre")
        infos.addWidget(self.mon_nom)
        self.etat = label("", "petit")
        infos.addWidget(self.etat)
        profil.addLayout(infos, 1)
        reglages_btn = bouton_icone("settings", "Paramètres (photo de profil, thème)", 36)
        reglages_btn.clicked.connect(self.parametres)
        profil.addWidget(reglages_btn)
        sortir = bouton_icone("log-out", "Quitter le salon", 36)
        sortir.clicked.connect(self.quitter)
        profil.addWidget(sortir)
        cote.lay.addLayout(profil)
        racine.addWidget(cote)

        # Zone principale
        principal = Carte(marges=0, espacement=0)
        entete = QHBoxLayout()
        entete.setContentsMargins(24, 18, 24, 16)
        self.titre = label("", "sous-titre")
        entete.addWidget(self.titre)
        entete.addStretch()
        entete.addWidget(label("Glissez des photos ou vidéos ici pour les envoyer", "petit"))
        principal.lay.addLayout(entete)
        separation = QFrame()
        separation.setObjectName("separation")
        separation.setFixedHeight(1)
        principal.lay.addWidget(separation)

        self.zone = QScrollArea()
        self.zone.setWidgetResizable(True)
        self.zone.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        fil = QWidget()
        self.fil = QVBoxLayout(fil)
        self.fil.setContentsMargins(20, 16, 18, 16)
        self.fil.setSpacing(8)
        self.fil.addStretch()
        self.zone.setWidget(fil)
        principal.lay.addWidget(self.zone, 1)

        bas = QVBoxLayout()
        bas.setContentsMargins(16, 6, 16, 16)
        bas.setSpacing(8)
        self.ligne_envoi = QWidget()
        h = QHBoxLayout(self.ligne_envoi)
        h.setContentsMargins(8, 0, 8, 0)
        self.texte_envoi = label("", "petit")
        h.addWidget(self.texte_envoi)
        self.barre = QProgressBar()
        self.barre.setTextVisible(False)
        h.addWidget(self.barre, 1)
        self.ligne_envoi.hide()
        bas.addWidget(self.ligne_envoi)

        saisie = Carte(marges=6, espacement=6, fine=True, horizontal=True)
        saisie.setObjectName("saisie")
        joindre = bouton_icone("image", "Envoyer une photo ou une vidéo", 40, couleur=theme.BLEU)
        joindre.clicked.connect(self._choisir_fichiers)
        saisie.lay.addWidget(joindre)
        self.champ = QLineEdit()
        self.champ.setObjectName("champ-message")
        self.champ.setPlaceholderText("Écrire un message…")
        self.champ.returnPressed.connect(self._envoyer)
        saisie.lay.addWidget(self.champ, 1)
        envoyer = bouton_icone("send-horizontal", "Envoyer", 40, couleur=theme.BLEU)
        envoyer.clicked.connect(self._envoyer)
        saisie.lay.addWidget(envoyer)
        bas.addWidget(saisie)
        principal.lay.addLayout(bas)
        racine.addWidget(principal, 1)

    def ouvrir(self, nom: str, url: str, pseudo: str) -> None:
        self._vider_fil()
        self.dernier_auteur = None
        self.nom_salon.setText(nom)
        self.adresse.setText(url.removeprefix("wss://"))
        self.titre.setText(f"Salon · {nom}")
        self.mon_nom.setText(pseudo)
        self.mon_avatar.changer(pseudo)
        self.champ.setFocus()

    def _vider_fil(self) -> None:
        while self.fil.count() > 1:
            if w := self.fil.takeAt(0).widget():
                w.deleteLater()

    # --- Événements du client -----------------------------------------------

    def _bienvenue(self, pseudo: str, historique: list) -> None:
        self.mon_nom.setText(pseudo)
        self.mon_avatar.changer(pseudo)
        for m in historique:
            self._recu(m)

    def _recu(self, m: dict) -> None:
        if m.get("type") == "message":
            self._bulle_texte(m["de"], m["texte"], m.get("heure", ""))
        elif m.get("type") == "fichier":
            self._bulle_fichier(m)

    def _etat(self, texte: str) -> None:
        self.etat.setText(("● " if texte == "en ligne" else "") + texte)
        self.etat.setProperty("role", "en-ligne" if texte == "en ligne" else "petit")
        self.etat.style().unpolish(self.etat)
        self.etat.style().polish(self.etat)

    def _membres(self, membres: list) -> None:
        while self.liste_membres.count():
            if w := self.liste_membres.takeAt(0).widget():
                w.deleteLater()
        self.titre_membres.setText(f"EN LIGNE · {len(membres)}")
        for pseudo in membres:
            rangee = QWidget()
            h = QHBoxLayout(rangee)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(10)
            h.addWidget(Avatar(pseudo, 36, self.photos))
            nom = label(pseudo + ("  (vous)" if pseudo == self.client.pseudo else ""))
            nom.setStyleSheet("font-weight: 600;")
            h.addWidget(nom)
            h.addStretch()
            self.liste_membres.addWidget(rangee)
        self.liste_membres.addStretch()

    def _progression(self, nom: str, envoye: int, total: int) -> None:
        if total == 0:
            self.ligne_envoi.hide()
            return
        self.ligne_envoi.show()
        self.texte_envoi.setText(f"Envoi de {nom} · {taille_lisible(envoye)} / {taille_lisible(total)}")
        self.barre.setValue(int(envoye * 100 / total))

    # --- Envoi --------------------------------------------------------------

    def _envoyer(self) -> None:
        texte = self.champ.text().strip()
        if not texte:
            return
        if self.client.envoyer_texte(texte):
            self.champ.clear()
        else:
            self._note("Pas connecté : message non envoyé.")

    def _choisir_fichiers(self) -> None:
        motifs = " ".join(f"*{e}" for exts in EXTENSIONS.values() for e in sorted(exts))
        chemins, _ = QFileDialog.getOpenFileNames(self, "Envoyer des photos ou vidéos", str(Path.home()),
                                                  f"Photos et vidéos ({motifs})")
        if chemins:
            self.client.envoyer_fichiers([Path(c) for c in chemins])

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        chemins = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        self.client.envoyer_fichiers([c for c in chemins if c.is_file()])

    # --- Fil de discussion --------------------------------------------------

    def _ajouter(self, contenu: QWidget, auteur: str | None, heure: str = "") -> None:
        """Place `contenu` à droite (vous), à gauche avec avatar et nom (autres) ou au centre (note)."""
        moi = auteur == self.client.pseudo
        suite = auteur is not None and auteur == self.dernier_auteur  # même auteur : on regroupe
        self.dernier_auteur = auteur

        rangee = QHBoxLayout()
        rangee.setContentsMargins(0, 0 if suite else 6, 0, 0)
        rangee.setSpacing(8)
        if auteur is None:
            rangee.addStretch()
            rangee.addWidget(contenu)
            rangee.addStretch()
        elif moi:
            rangee.addStretch()
            rangee.addWidget(contenu)
        else:
            if suite:
                rangee.addSpacing(TAILLE_AVATAR_FIL)
            else:
                rangee.addWidget(Avatar(auteur, TAILLE_AVATAR_FIL, self.photos), 0, Qt.AlignBottom)
            colonne = QVBoxLayout()
            colonne.setSpacing(3)
            if not suite:
                nom = label(f"{auteur}  ·  {heure}", "petit")
                nom.setTextFormat(Qt.PlainText)
                nom.setContentsMargins(12, 0, 0, 0)
                colonne.addWidget(nom)
            colonne.addWidget(contenu)
            rangee.addLayout(colonne)
            rangee.addStretch()
        conteneur = QWidget()
        conteneur.setLayout(rangee)
        self.fil.insertWidget(self.fil.count() - 1, conteneur)
        self._defiler()

    def _defiler(self) -> None:
        barre = self.zone.verticalScrollBar()
        QTimer.singleShot(40, lambda: barre.setValue(barre.maximum()))

    def _bulle_texte(self, auteur: str, texte: str, heure: str) -> None:
        moi = auteur == self.client.pseudo
        bulle = QFrame()
        bulle.setObjectName("bulle-moi" if moi else "bulle-autre")
        bulle.setMaximumWidth(LARGEUR_BULLE)
        bulle.setToolTip(heure)
        v = QVBoxLayout(bulle)
        v.setContentsMargins(14, 9, 14, 9)
        corps = label(texte)
        corps.setObjectName("bulle-texte")
        corps.setTextFormat(Qt.PlainText)  # jamais de HTML venant du réseau
        corps.setWordWrap(True)
        corps.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # Un QLabel replié propose une largeur trop petite : on donne celle du texte.
        corps.ensurePolished()
        largeur = max(corps.fontMetrics().horizontalAdvance(l) for l in texte.splitlines() or [""])
        corps.setMinimumWidth(min(largeur + 4, LARGEUR_BULLE - 28))
        v.addWidget(corps)
        self._ajouter(bulle, auteur, heure)

    def _bulle_fichier(self, m: dict) -> None:
        nom, id_ = m["nom"], m["id"]
        bloc = QFrame()
        bloc.setObjectName("bulle-autre")
        v = QVBoxLayout(bloc)
        v.setContentsMargins(6, 6, 6, 8)
        v.setSpacing(6)

        local: dict[str, Path] = {}

        def avec_fichier(action: Callable[[Path], None]) -> None:
            if "chemin" in local:
                action(local["chemin"])
                return
            etat.setText("Téléchargement…")

            def fini(chemin: Path | None) -> None:
                if chemin is None:
                    etat.setText("Fichier indisponible")
                    return
                local["chemin"] = chemin
                etat.setText(taille_lisible(m["taille"]))
                action(chemin)

            self.client.telecharger(id_, nom, fini, lambda r, t: t > 0 and etat.setText(
                f"Téléchargement… {r * 100 // t} %"))

        ouvrir = lambda: avec_fichier(lambda c: QDesktopServices.openUrl(QUrl.fromLocalFile(str(c))))

        if m.get("genre") == "image":
            apercu = Cliquable(ouvrir)
            apercu.setObjectName("apercu")
            apercu.setFixedSize(260, 180)
            apercu.setAlignment(Qt.AlignCenter)
            apercu.setPixmap(theme.icone("image", theme.c("doux"), 40).pixmap(40, 40))
            apercu.setToolTip("Ouvrir en grand")
            v.addWidget(apercu)

            def afficher(chemin: Path) -> None:
                pix = QPixmap(str(chemin))
                if pix.isNull():
                    etat.setText("Image illisible")
                    return
                ratio = apercu.devicePixelRatioF()
                pix = pix.scaled(IMAGE_MAX * ratio, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pix = arrondir(pix, 14 * ratio)
                pix.setDevicePixelRatio(ratio)
                apercu.setFixedSize(pix.deviceIndependentSize().toSize())
                apercu.setObjectName("")
                apercu.setStyleSheet("background: transparent;")
                apercu.setPixmap(pix)
                barre = self.zone.verticalScrollBar()
                if barre.maximum() - barre.value() < 400:  # on suit le fil, sauf si on lit plus haut
                    self._defiler()

            QTimer.singleShot(0, lambda: avec_fichier(afficher))
        else:
            vignette = Cliquable(ouvrir)
            vignette.setObjectName("vignette")
            vignette.setFixedSize(300, 170)
            vignette.setAlignment(Qt.AlignCenter)
            vignette.setPixmap(theme.icone("play", theme.BLEU, 44).pixmap(44, 44))
            vignette.setToolTip("Lire la vidéo")
            v.addWidget(vignette)
            bloc.setMaximumWidth(vignette.width() + 12)

        pied = QHBoxLayout()
        pied.setContentsMargins(8, 0, 0, 0)
        infos = QVBoxLayout()
        infos.setSpacing(2)
        titre = label(nom)
        titre.setTextFormat(Qt.PlainText)
        titre.setStyleSheet("font-weight: 600;")
        titre.setMaximumWidth(250)
        titre.setToolTip(nom)
        infos.addWidget(titre)
        etat = label(taille_lisible(m["taille"]), "petit")
        infos.addWidget(etat)
        pied.addLayout(infos, 1)
        sauver = bouton_icone("download", "Enregistrer dans Téléchargements/LocalNet", 36)
        sauver.clicked.connect(lambda: avec_fichier(
            lambda c: etat.setText(f"Enregistré : {enregistrer(c, nom).name}")))
        pied.addWidget(sauver, 0, Qt.AlignBottom)
        v.addLayout(pied)
        self._ajouter(bloc, m["de"], m.get("heure", ""))

    def _note(self, texte: str) -> None:
        note = label(texte, "note")
        note.setTextFormat(Qt.PlainText)
        note.setWordWrap(True)
        self._ajouter(note, None)
