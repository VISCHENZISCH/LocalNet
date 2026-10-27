"""Connexion au salon (QWebSocket), envoi et réception de photos/vidéos.

Les fichiers partent en morceaux au fil de l'eau (jamais entièrement en
mémoire) et sont téléchargés en HTTP depuis le serveur, avec un cache local.
"""

from __future__ import annotations

import os
import secrets
import signal
import sys
from collections import deque
from pathlib import Path
from typing import BinaryIO, Callable

from PySide6.QtCore import QObject, QProcess, QStandardPaths, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWebSockets import QWebSocket

from chat.protocole import (
    CHEMIN_FICHIERS, FICHIER_MAX, TAILLE_MORCEAU, decoder, encoder, genre, nom_sur, taille_lisible,
)

RACINE = Path(__file__).resolve().parent.parent


def dossier_cache() -> Path:
    d = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation)) / "fichiers"
    d.mkdir(parents=True, exist_ok=True)
    return d


class ClientSalon(QObject):
    bienvenue = Signal(str, list)  # pseudo, historique
    recu = Signal(dict)            # message ou fichier
    membres = Signal(list)
    note = Signal(str)             # arrivée, départ, erreur…
    etat = Signal(str)             # « connexion… », « en ligne », « hors ligne »
    refuse = Signal(str)           # connexion refusée (pseudo pris…)
    envoi = Signal(str, int, int)  # nom, octets envoyés, total ; total 0 = terminé

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.url: str | None = None
        self.pseudo = ""
        self.deja_connecte = False
        self.ws = QWebSocket()
        self.ws.connected.connect(lambda: self.ws.sendTextMessage(encoder("bonjour", pseudo=self.pseudo)))
        self.ws.disconnected.connect(self._deconnecte)
        self.ws.textMessageReceived.connect(self._message)
        self.ws.bytesWritten.connect(self._ecrit)
        self.reseau = QNetworkAccessManager(self)

        self.file_envois: deque[Path] = deque()
        self.flux: BinaryIO | None = None
        self.id_envoi = b""
        self.nom_envoi = ""
        self.taille_envoi = self.lu = self.ecrit = 0

    @property
    def base_http(self) -> str:
        return (self.url or "").replace("ws://", "http://", 1)

    # --- Connexion ----------------------------------------------------------

    def connecter(self, url: str, pseudo: str) -> None:
        self.url, self.pseudo, self.deja_connecte = url, pseudo, False
        self.etat.emit("connexion…")
        self.ws.open(QUrl(url))

    def fermer(self) -> None:
        self.url = None
        self._annuler_envois()
        self.ws.close()

    def _deconnecte(self) -> None:
        self._annuler_envois()
        self.membres.emit([])
        if not self.url:
            return
        if not self.deja_connecte:  # jamais entré : adresse fausse ou salon fermé
            raison = self.ws.errorString() or "salon injoignable"
            self.url = None
            self.refuse.emit(f"Connexion impossible : {raison}")
            return
        self.etat.emit("hors ligne — reconnexion…")
        QTimer.singleShot(3000, lambda: self.url and self.ws.open(QUrl(self.url)))

    def _message(self, brut: str) -> None:
        m = decoder(brut)
        if m is None:
            return
        type_ = m["type"]
        if type_ == "bienvenue":
            self.pseudo = m["pseudo"]
            self.etat.emit("en ligne")
            self.bienvenue.emit(self.pseudo, [] if self.deja_connecte else m.get("historique", []))
            self.deja_connecte = True
            self.membres.emit(m["membres"])
        elif type_ in ("message", "fichier"):
            self.recu.emit(m)
        elif type_ in ("arrivee", "depart"):
            verbe = "a rejoint" if type_ == "arrivee" else "a quitté"
            self.note.emit(f"{m['pseudo']} {verbe} le salon")
            self.membres.emit(m["membres"])
        elif type_ == "erreur":
            if m.get("fatal"):
                self.url = None
                self.refuse.emit(m.get("texte", "Connexion refusée."))
            else:
                self.note.emit(m.get("texte", "Erreur"))

    # --- Envoi --------------------------------------------------------------

    def envoyer_texte(self, texte: str) -> bool:
        if not self.ws.isValid():
            return False
        self.ws.sendTextMessage(encoder("message", texte=texte))
        return True

    def envoyer_fichiers(self, chemins: list[Path]) -> None:
        for chemin in chemins:
            if genre(chemin.name) is None:
                self.note.emit(f"« {chemin.name} » ignoré : seules les photos et vidéos sont acceptées.")
            elif not 0 < chemin.stat().st_size <= FICHIER_MAX:
                self.note.emit(f"« {chemin.name} » ignoré : vide ou plus de {taille_lisible(FICHIER_MAX)}.")
            else:
                self.file_envois.append(chemin)
        if self.flux is None:
            self._envoi_suivant()

    def _envoi_suivant(self) -> None:
        if not self.file_envois or not self.ws.isValid():
            return
        chemin = self.file_envois.popleft()
        self.flux = chemin.open("rb")
        self.id_envoi = secrets.token_hex(4).encode()
        self.nom_envoi = nom_sur(chemin.name)
        self.taille_envoi = chemin.stat().st_size
        self.lu = self.ecrit = 0
        self.ws.sendTextMessage(encoder("fichier", id=self.id_envoi.decode(), nom=self.nom_envoi,
                                        taille=self.taille_envoi))
        self._alimenter()

    def _alimenter(self) -> None:
        """Garde au plus quelques morceaux en attente d'écriture sur la socket."""
        while self.flux and self.lu < self.taille_envoi and self.lu - self.ecrit < 4 * TAILLE_MORCEAU:
            morceau = self.flux.read(TAILLE_MORCEAU)
            if not morceau:
                break
            self.lu += len(morceau)
            self.ws.sendBinaryMessage(self.id_envoi + morceau)

    def _ecrit(self, octets: int) -> None:
        if self.flux is None:
            return
        self.ecrit = min(self.ecrit + octets, self.lu)  # octets d'en-tête compris : approximation
        self.envoi.emit(self.nom_envoi, self.ecrit, self.taille_envoi)
        if self.lu >= self.taille_envoi and self.ecrit >= self.lu:
            self.flux.close()
            self.flux = None
            self.envoi.emit(self.nom_envoi, 0, 0)
            self._envoi_suivant()
        else:
            self._alimenter()

    def _annuler_envois(self) -> None:
        if self.flux:
            self.flux.close()
            self.flux = None
            self.envoi.emit(self.nom_envoi, 0, 0)
        self.file_envois.clear()

    # --- Réception ----------------------------------------------------------

    def telecharger(self, id_: str, nom: str, fini: Callable[[Path | None], None],
                    progression: Callable[[int, int], None] | None = None) -> None:
        """Télécharge (ou reprend du cache) le fichier ; `fini(None)` en cas d'échec."""
        chemin = dossier_cache() / f"{id_}_{nom_sur(nom)}"
        if chemin.exists():
            fini(chemin)
            return
        partiel = chemin.with_name(chemin.name + ".part")
        sortie = partiel.open("wb")
        reponse = self.reseau.get(QNetworkRequest(QUrl(self.base_http + CHEMIN_FICHIERS + id_)))
        reponse.readyRead.connect(lambda: sortie.write(bytes(reponse.readAll())))
        if progression:
            reponse.downloadProgress.connect(progression)

        def termine() -> None:
            sortie.write(bytes(reponse.readAll()))
            sortie.close()
            if reponse.error() == QNetworkReply.NoError:
                partiel.replace(chemin)
                fini(chemin)
            else:
                partiel.unlink(missing_ok=True)
                fini(None)
            reponse.deleteLater()

        reponse.finished.connect(termine)


class ServeurLocal(QObject):
    """Salon hébergé sur ce PC (`python -m chat.serveur` en processus séparé)."""

    pret = Signal()
    echec = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.proc: QProcess | None = None

    @property
    def actif(self) -> bool:
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    def demarrer(self) -> None:
        if self.actif:
            self.pret.emit()
            return
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(str(RACINE))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.setProgram(sys.executable)
        self.proc.setArguments(["-u", "-m", "chat.serveur"])
        sortie = []

        def lire() -> None:
            texte = bytes(self.proc.readAll()).decode("utf-8", "replace")
            sortie.append(texte)
            if "Salon ouvert" in texte:
                self.pret.emit()

        self.proc.readyRead.connect(lire)
        self.proc.finished.connect(lambda code, _s: code and self.echec.emit(
            ("".join(sortie).strip().splitlines() or [f"code {code}"])[-1]))
        self.proc.start()

    def arreter(self) -> None:
        if self.actif:
            self.proc.finished.disconnect()  # arrêt voulu : pas un échec
            # SIGINT : le serveur retire son annonce mDNS et vide son dossier temporaire.
            os.kill(self.proc.processId(), signal.SIGINT)
            if not self.proc.waitForFinished(5000):
                self.proc.kill()
                self.proc.waitForFinished(1000)
