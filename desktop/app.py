"""LocalNet : discussion et partage de photos/vidéos sur le réseau local.

Usage : .venv/bin/python -m desktop.app
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedLayout

from chat.protocole import PORT_DEFAUT

from . import theme
from .accueil import Accueil
from .client import ClientSalon, ServeurLocal
from .salon import Salon
from .widgets import Fond


class Fenetre(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalNet")
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)

        self.client = ClientSalon(self)
        self.serveur = ServeurLocal(self)
        self.accueil = Accueil()
        self.salon = Salon(self.client)
        self.pseudo_hote = ""

        fond = Fond()
        self.pages = QStackedLayout(fond)
        self.pages.addWidget(self.accueil)
        self.pages.addWidget(self.salon)
        self.setCentralWidget(fond)

        self.accueil.rejoindre.connect(self.rejoindre)
        self.accueil.creer.connect(self.creer)
        self.salon.quitter.connect(self.quitter)
        self.client.bienvenue.connect(lambda *_: self.pages.setCurrentWidget(self.salon))
        self.client.refuse.connect(self._refuse)
        self.serveur.pret.connect(self._salon_pret)
        self.serveur.echec.connect(self._echec_serveur)

    def rejoindre(self, url: str, pseudo: str, nom: str) -> None:
        self.accueil.erreur("")
        self.salon.ouvrir(nom, url)
        self.client.connecter(url, pseudo)

    def creer(self, pseudo: str) -> None:
        self.pseudo_hote = pseudo
        self.serveur.demarrer()

    def _salon_pret(self) -> None:
        self.accueil.creation_finie()
        self.rejoindre(f"ws://{self.accueil.ip}:{PORT_DEFAUT}", self.pseudo_hote, "ce PC")

    def quitter(self) -> None:
        self.client.fermer()
        self.serveur.arreter()
        self.pages.setCurrentWidget(self.accueil)
        QTimer.singleShot(0, self.accueil.rechercher)

    def _refuse(self, texte: str) -> None:
        self.pages.setCurrentWidget(self.accueil)
        self.accueil.erreur(texte)

    def _echec_serveur(self, texte: str) -> None:
        self.accueil.creation_finie()
        self.accueil.erreur(f"Impossible d'ouvrir le salon : {texte}")

    def closeEvent(self, event) -> None:
        self.client.fermer()
        self.serveur.arreter()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("LocalNet")
    app.setWindowIcon(QIcon(theme.logo(128)))
    theme.charger_police()
    app.setFont(QFont(theme.POLICE, 10))
    app.setStyleSheet(theme.QSS)
    fenetre = Fenetre()
    fenetre.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
