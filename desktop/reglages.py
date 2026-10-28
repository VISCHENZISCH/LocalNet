"""Réglages de ce PC : thème, dernier nom d'utilisateur, photo de profil,
empreintes des certificats des salons déjà rejoints.

Le mot de passe n'est jamais enregistré.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSettings, QStandardPaths, Qt
from PySide6.QtGui import QImage, QPixmap

COTE_PHOTO = 256


def _reglages() -> QSettings:
    return QSettings("LocalNet", "LocalNet")


def lire(cle: str, defaut: str = "") -> str:
    return str(_reglages().value(cle, defaut))


def ecrire(cle: str, valeur: str) -> None:
    _reglages().setValue(cle, valeur)


def empreinte(salon: str) -> str:
    """Empreinte du certificat retenue pour « hôte:port », ou « »."""
    return lire(f"certificats/{salon}")


def retenir_empreinte(salon: str, empreinte_: str) -> None:
    ecrire(f"certificats/{salon}", empreinte_)


def _chemin_photo() -> Path:
    dossier = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier / "profil.jpg"


def octets_photo() -> bytes | None:
    chemin = _chemin_photo()
    return chemin.read_bytes() if chemin.exists() else None


def photo() -> QPixmap | None:
    donnees = octets_photo()
    pix = QPixmap()
    return pix if donnees and pix.loadFromData(donnees) else None


def enregistrer_photo(source: Path) -> bool:
    """Recadre au centre en 256×256 et enregistre en JPEG ; False si l'image est illisible."""
    image = QImage(str(source))
    if image.isNull():
        return False
    image = image.scaled(COTE_PHOTO, COTE_PHOTO, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    image = image.copy((image.width() - COTE_PHOTO) // 2, (image.height() - COTE_PHOTO) // 2,
                       COTE_PHOTO, COTE_PHOTO).convertToFormat(QImage.Format_RGB32)
    tampon = QByteArray()
    flux = QBuffer(tampon)
    flux.open(QIODevice.WriteOnly)
    image.save(flux, "JPEG", 88)
    _chemin_photo().write_bytes(bytes(tampon))
    return True


def supprimer_photo() -> None:
    _chemin_photo().unlink(missing_ok=True)
