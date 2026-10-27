"""Écran du salon : membres à gauche, fil de discussion et saisie à droite."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, QSize, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QScrollArea,
    QVBoxLayout, QWidget,
)

from chat.protocole import EXTENSIONS, taille_lisible

from . import theme
from .client import ClientSalon
from .widgets import Verre, avatar, bouton, bouton_icone, label

LARGEUR_BULLE = 460
IMAGE_MAX = QSize(420, 320)


def arrondir(pix: QPixmap, rayon: int = 14) -> QPixmap:
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

    def __init__(self, client: ClientSalon):
        super().__init__()
        self.client = client
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
        racine.setContentsMargins(20, 20, 20, 20)
        racine.setSpacing(20)

        # Barre latérale
        cote = Verre(marges=22, espacement=12)
        cote.setFixedWidth(270)
        marque = QHBoxLayout()
        marque.setSpacing(12)
        logo = label()
        logo.setPixmap(theme.logo(38))
        marque.addWidget(logo)
        marque.addWidget(label("LocalNet", "sous-titre"))
        marque.addStretch()
        cote.lay.addLayout(marque)
        cote.lay.addSpacing(16)

        cote.lay.addWidget(label("SALON", "section"))
        bloc = Verre(marges=14, espacement=2, fin=True)
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
        cote.lay.addSpacing(12)

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

        sortir = bouton("Quitter le salon", "verre", icone="log-out")
        sortir.clicked.connect(self.quitter)
        cote.lay.addWidget(sortir)
        racine.addWidget(cote)

        # Zone principale
        principal = Verre(marges=0, espacement=0)
        entete = QHBoxLayout()
        entete.setContentsMargins(28, 22, 28, 18)
        self.titre = label("", "sous-titre")
        entete.addWidget(self.titre)
        entete.addStretch()
        self.etat = label("", "petit")
        entete.addWidget(self.etat)
        principal.lay.addLayout(entete)
        separation = QFrame()
        separation.setFixedHeight(1)
        separation.setStyleSheet(f"background: {theme.LISERE};")
        principal.lay.addWidget(separation)

        self.zone = QScrollArea()
        self.zone.setWidgetResizable(True)
        self.zone.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        fil = QWidget()
        self.fil = QVBoxLayout(fil)
        self.fil.setContentsMargins(28, 20, 22, 20)
        self.fil.setSpacing(10)
        self.fil.addStretch()
        self.zone.setWidget(fil)
        principal.lay.addWidget(self.zone, 1)

        bas = QVBoxLayout()
        bas.setContentsMargins(20, 8, 20, 20)
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

        saisie = Verre(marges=8, espacement=6, fin=True, horizontal=True)
        saisie.setObjectName("saisie")
        joindre = bouton_icone("paperclip", "Envoyer une photo ou une vidéo (ou glissez-la ici)", 42)
        joindre.clicked.connect(self._choisir_fichiers)
        saisie.lay.addWidget(joindre)
        self.champ = QLineEdit()
        self.champ.setPlaceholderText("Écrire un message…")
        self.champ.setStyleSheet("background: transparent; border: none; padding: 8px 4px; font-size: 14px;")
        self.champ.returnPressed.connect(self._envoyer)
        saisie.lay.addWidget(self.champ, 1)
        envoyer = bouton("", icone="send-horizontal")
        envoyer.setFixedSize(46, 42)
        envoyer.setToolTip("Envoyer")
        envoyer.clicked.connect(self._envoyer)
        saisie.lay.addWidget(envoyer)
        bas.addWidget(saisie)
        principal.lay.addLayout(bas)
        racine.addWidget(principal, 1)

    def ouvrir(self, nom: str, url: str) -> None:
        self._vider_fil()
        self.nom_salon.setText(nom)
        self.adresse.setText(url.removeprefix("ws://"))
        self.titre.setText(f"Salon · {nom}")
        self.champ.setFocus()

    def _vider_fil(self) -> None:
        while self.fil.count() > 1:
            if w := self.fil.takeAt(0).widget():
                w.deleteLater()

    # --- Événements du client -----------------------------------------------

    def _bienvenue(self, _pseudo: str, historique: list) -> None:
        for m in historique:
            self._recu(m)

    def _recu(self, m: dict) -> None:
        if m.get("type") == "message":
            self._bulle_texte(m["de"], m["texte"], m.get("heure", ""))
        elif m.get("type") == "fichier":
            self._bulle_fichier(m)

    def _etat(self, texte: str) -> None:
        self.etat.setText(("● " if texte == "en ligne" else "") + texte)
        self.etat.setStyleSheet(f"color: {theme.SAUGE};" if texte == "en ligne" else "")

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
            h.addWidget(avatar(pseudo))
            h.addWidget(label(pseudo + ("  (vous)" if pseudo == self.client.pseudo else "")))
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

    def _ajouter(self, widget: QWidget, moi: bool | None) -> None:
        rangee = QHBoxLayout()
        rangee.setContentsMargins(0, 0, 0, 0)
        if moi is not False:
            rangee.addStretch()
        rangee.addWidget(widget)
        if moi is not True:
            rangee.addStretch()
        conteneur = QWidget()
        conteneur.setLayout(rangee)
        self.fil.insertWidget(self.fil.count() - 1, conteneur)
        barre = self.zone.verticalScrollBar()
        QTimer.singleShot(40, lambda: barre.setValue(barre.maximum()))

    def _entete(self, auteur: str, heure: str, moi: bool) -> QLabel:
        meta = label(heure if moi else f"{auteur}  ·  {heure}", "petit")
        meta.setTextFormat(Qt.PlainText)
        if not moi:
            meta.setStyleSheet(f"color: {theme.teinte(auteur)}; font-size: 11px; font-weight: 600;")
        return meta

    def _bulle_texte(self, auteur: str, texte: str, heure: str) -> None:
        moi = auteur == self.client.pseudo
        bulle = QFrame()
        bulle.setObjectName("bulle-moi" if moi else "bulle-autre")
        bulle.setMaximumWidth(LARGEUR_BULLE)
        v = QVBoxLayout(bulle)
        v.setContentsMargins(16, 10, 16, 10)
        v.setSpacing(4)
        v.addWidget(self._entete(auteur, heure, moi), 0, Qt.AlignRight if moi else Qt.AlignLeft)
        corps = label(texte)
        corps.setTextFormat(Qt.PlainText)  # jamais de HTML venant du réseau
        corps.setWordWrap(True)
        corps.setTextInteractionFlags(Qt.TextSelectableByMouse)
        corps.setStyleSheet("font-size: 14px;")
        # Un QLabel replié propose une largeur trop petite : on donne celle du texte.
        corps.ensurePolished()
        largeur = max(corps.fontMetrics().horizontalAdvance(l) for l in texte.splitlines() or [""])
        corps.setMinimumWidth(min(largeur + 4, LARGEUR_BULLE - 32))
        v.addWidget(corps)
        if moi:
            v.itemAt(0).widget().setStyleSheet("color: rgba(255,255,255,0.75); font-size: 11px;")
        self._ajouter(bulle, moi)

    def _bulle_fichier(self, m: dict) -> None:
        moi = m["de"] == self.client.pseudo
        nom, id_ = m["nom"], m["id"]
        bloc = QFrame()
        bloc.setObjectName("bulle-autre")
        v = QVBoxLayout(bloc)
        v.setContentsMargins(8, 8, 8, 10)
        v.setSpacing(8)

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
            apercu.setFixedSize(260, 180)
            apercu.setAlignment(Qt.AlignCenter)
            apercu.setPixmap(theme.icone("image", "#94A3B8", 40).pixmap(40, 40))
            apercu.setStyleSheet(f"background: {theme.VERRE}; border-radius: 14px;")
            apercu.setToolTip("Ouvrir en grand")
            v.addWidget(apercu)

            def afficher(chemin: Path) -> None:
                pix = QPixmap(str(chemin))
                if pix.isNull():
                    etat.setText("Image illisible")
                    return
                ratio = apercu.devicePixelRatioF()
                pix = pix.scaled(IMAGE_MAX * ratio, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pix = arrondir(pix, int(14 * ratio))
                pix.setDevicePixelRatio(ratio)
                apercu.setFixedSize(pix.deviceIndependentSize().toSize())
                apercu.setStyleSheet("")
                apercu.setPixmap(pix)

            QTimer.singleShot(0, lambda: avec_fichier(afficher))
        else:
            vignette = Cliquable(ouvrir)
            vignette.setFixedSize(300, 170)
            vignette.setAlignment(Qt.AlignCenter)
            vignette.setPixmap(theme.icone("play", "#FFFFFF", 44).pixmap(44, 44))
            vignette.setStyleSheet(
                f"border-radius: 14px; background: {theme.FORET}; border: 1px solid {theme.VERT};")
            vignette.setToolTip("Lire la vidéo")
            v.addWidget(vignette)
            bloc.setMaximumWidth(vignette.width() + 16)

        pied = QHBoxLayout()
        pied.setContentsMargins(6, 0, 0, 0)
        infos = QVBoxLayout()
        infos.setSpacing(2)
        infos.addWidget(self._entete(m["de"], m.get("heure", ""), moi))
        titre = label(nom)
        titre.setTextFormat(Qt.PlainText)
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
        self._ajouter(bloc, moi)

    def _note(self, texte: str) -> None:
        note = label(texte, "note")
        note.setTextFormat(Qt.PlainText)
        note.setWordWrap(True)
        self._ajouter(note, None)
