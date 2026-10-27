"""Comptes du salon : nom d'utilisateur, mot de passe haché (scrypt), photo de profil.

Gardés sur le PC qui héberge le salon, dans `~/.local/share/LocalNet/` :
    comptes.json        {clé en minuscules: {"pseudo", "sel", "empreinte", "avatar"}}
    avatars/<id>        photos, nommées par l'empreinte de leur contenu
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from pathlib import Path

from .protocole import AVATAR_MAX, mot_de_passe_valide, pseudo_valide

_ID_AVATAR = re.compile(r"[0-9a-f]{16}")
_SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")  # JPEG, PNG


class ErreurCompte(Exception):
    pass


def dossier_donnees() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "LocalNet"


def _hacher(mot_de_passe: str, sel: bytes) -> bytes:
    return hashlib.scrypt(mot_de_passe.encode(), salt=sel, n=2**14, r=8, p=1, dklen=32)


class Comptes:
    def __init__(self, dossier: Path | None = None):
        self.dossier = dossier or dossier_donnees()
        self.dossier_avatars = self.dossier / "avatars"
        self.dossier_avatars.mkdir(parents=True, exist_ok=True)
        self.fichier = self.dossier / "comptes.json"
        try:
            self.comptes: dict[str, dict] = json.loads(self.fichier.read_text())
        except (OSError, ValueError):
            self.comptes = {}

    def _sauver(self) -> None:
        temporaire = self.fichier.with_suffix(".tmp")
        temporaire.write_text(json.dumps(self.comptes, ensure_ascii=False, indent=1))
        os.chmod(temporaire, 0o600)
        temporaire.replace(self.fichier)

    def creer(self, pseudo: str, mot_de_passe: str) -> str:
        if not pseudo_valide(pseudo):
            raise ErreurCompte("Nom d'utilisateur invalide : 1 à 20 caractères parmi lettres, "
                               "chiffres, « . », « _ », « - ».")
        if not mot_de_passe_valide(mot_de_passe):
            raise ErreurCompte("Le mot de passe doit faire de 4 à 64 caractères.")
        if pseudo.lower() in self.comptes:
            raise ErreurCompte(f"Le nom « {pseudo} » est déjà utilisé sur ce salon.")
        sel = secrets.token_bytes(16)
        self.comptes[pseudo.lower()] = {"pseudo": pseudo, "sel": sel.hex(),
                                        "empreinte": _hacher(mot_de_passe, sel).hex(), "avatar": None}
        self._sauver()
        return pseudo

    def verifier(self, pseudo: object, mot_de_passe: object) -> str:
        """Renvoie le nom exact du compte, ou lève ErreurCompte."""
        compte = self.comptes.get(pseudo.lower()) if isinstance(pseudo, str) else None
        if compte is None:
            raise ErreurCompte("Compte inconnu sur ce salon : choisissez « Créer un compte ».")
        if not isinstance(mot_de_passe, str) or not hmac.compare_digest(
                _hacher(mot_de_passe, bytes.fromhex(compte["sel"])), bytes.fromhex(compte["empreinte"])):
            raise ErreurCompte("Mot de passe incorrect.")
        return compte["pseudo"]

    def definir_avatar(self, pseudo: str, donnees: bytes | None) -> None:
        if donnees is not None and (len(donnees) > AVATAR_MAX or not donnees.startswith(_SIGNATURES)):
            raise ErreurCompte("Photo de profil refusée (JPEG ou PNG, 400 Ko max.).")
        compte = self.comptes[pseudo.lower()]
        if donnees is None:
            compte["avatar"] = None
        else:
            id_ = hashlib.sha256(donnees).hexdigest()[:16]
            (self.dossier_avatars / id_).write_bytes(donnees)
            compte["avatar"] = id_
        self._sauver()

    def avatars(self) -> dict[str, str]:
        return {c["pseudo"]: c["avatar"] for c in self.comptes.values() if c.get("avatar")}

    def chemin_avatar(self, id_: str) -> Path | None:
        if not _ID_AVATAR.fullmatch(id_):
            return None
        chemin = self.dossier_avatars / id_
        return chemin if chemin.exists() else None
