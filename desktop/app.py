"""LocalNet : discussion et partage de photos/vidéos sur le réseau local.

Usage : .venv/bin/python -m desktop.app
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedLayout

from chat.protocole import PORT_DEFAUT

from . import reglages, theme
from .accueil import Accueil
from .client import ClientSalon, ServeurLocal
from .parametres import Parametres
from .salon import Salon
from .widgets import Fond


class Fenetre(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalNet")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        self.client = ClientSalon(self)
        self.serveur = ServeurLocal(self)
        self.accueil = Accueil()
        self.salon = Salon(self.client)
        self.hote: tuple[str, str, bool] | None = None  # identifiants en attente du salon local

        fond = Fond()
        self.pages = QStackedLayout(fond)
        self.pages.addWidget(self.accueil)
        self.pages.addWidget(self.salon)
        self.setCentralWidget(fond)

        self.accueil.rejoindre.connect(self.rejoindre)
        self.accueil.heberger.connect(self.heberger)
        self.accueil.parametres.connect(self.parametres)
        self.salon.parametres.connect(self.parametres)
        self.salon.quitter.connect(self.quitter)
        self.client.bienvenue.connect(self._entre)
        self.client.refuse.connect(self._refuse)
        self.serveur.pret.connect(self._salon_pret)
        self.serveur.echec.connect(self._echec_serveur)

    def rejoindre(self, url: str, pseudo: str, mot_de_passe: str, nouveau: bool, nom: str) -> None:
        self.accueil.erreur("")
        self.salon.ouvrir(nom, url, pseudo)
        self.client.connecter(url, pseudo, mot_de_passe, nouveau)

    def heberger(self, pseudo: str, mot_de_passe: str, nouveau: bool) -> None:
        self.hote = (pseudo, mot_de_passe, nouveau)
        self.serveur.demarrer()

    def _salon_pret(self) -> None:
        self.accueil.hebergement_fini()
        if self.hote:
            self.rejoindre(f"ws://{self.accueil.ip}:{PORT_DEFAUT}", *self.hote, "ce PC")
            self.hote = None

    def _entre(self) -> None:
        self.accueil.vider_mot_de_passe()
        self.pages.setCurrentWidget(self.salon)

    def parametres(self) -> None:
        pseudo = self.client.pseudo if self.client.url else self.accueil.utilisateur.text().strip()
        dialogue = Parametres(self, self.client.photos, pseudo)
        dialogue.photo_changee.connect(lambda: self.client.envoyer_photo(reglages.octets_photo()))
        dialogue.exec()

    def quitter(self) -> None:
        self.client.fermer()
        self.serveur.arreter()
        self.pages.setCurrentWidget(self.accueil)
        QTimer.singleShot(0, self.accueil.rechercher)

    def _refuse(self, texte: str) -> None:
        self.pages.setCurrentWidget(self.accueil)
        self.accueil.erreur(texte)

    def _echec_serveur(self, texte: str) -> None:
        self.hote = None
        self.accueil.hebergement_fini()
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
    theme.appliquer(reglages.lire("theme", "clair"))
    fenetre = Fenetre()
    fenetre.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
