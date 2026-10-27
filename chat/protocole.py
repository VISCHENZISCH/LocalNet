"""Protocole du salon : JSON sur WebSocket, fichiers en trames binaires.

Client -> serveur
    {"type": "bonjour", "pseudo", "mot_de_passe", "nouveau": bool}
        premier message, obligatoire ; nouveau = créer le compte sur ce salon
    {"type": "avatar", "donnees": "<JPEG ou PNG en base64>" | null}
    {"type": "message", "texte": "..."}
    {"type": "fichier", "id": "ab12cd34", "nom": "...", "taille": 123}
        suivi de trames binaires : 8 octets d'id (ASCII) + morceau du fichier,
        jusqu'à atteindre la taille annoncée.

Serveur -> client
    {"type": "bienvenue", "pseudo", "membres", "historique", "avatars"}
    {"type": "avatars", "avatars": {pseudo: id}}            photo à GET /avatars/<id>
    {"type": "message", "de", "texte", "heure"}
    {"type": "fichier", "de", "id", "nom", "taille", "genre", "heure"}
        genre : "image" | "video" ; contenu à GET http://<serveur>/fichiers/<id>
    {"type": "arrivee" | "depart", "pseudo", "heure", "membres"}
    {"type": "erreur", "texte", "fatal"}                    fatal : connexion fermée
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import PurePath

TYPE_SERVICE = "_localnet-chat._tcp.local."  # annonce mDNS du salon
PORT_DEFAUT = 8765
TAILLE_MAX = 2000  # caractères par message
TAILLE_TRAME = 1024 * 1024  # octets par trame WebSocket
TAILLE_MORCEAU = 256 * 1024  # octets de fichier par trame binaire
TAILLE_ID = 8
FICHIER_MAX = 500 * 1024 * 1024
CHEMIN_FICHIERS = "/fichiers/"
CHEMIN_AVATARS = "/avatars/"
AVATAR_MAX = 400 * 1024  # octets ; le client envoie une photo 256×256

EXTENSIONS = {
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"},
    "video": {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"},
}

_PSEUDO = re.compile(r"[\w.-]{1,20}")


def pseudo_valide(pseudo: object) -> bool:
    return isinstance(pseudo, str) and _PSEUDO.fullmatch(pseudo) is not None


def mot_de_passe_valide(mdp: object) -> bool:
    return isinstance(mdp, str) and 4 <= len(mdp) <= 64


def genre(nom: str) -> str | None:
    """« image », « video », ou None si le fichier n'est pas accepté."""
    ext = PurePath(nom).suffix.lower()
    return next((g for g, exts in EXTENSIONS.items() if ext in exts), None)


def nom_sur(nom: object) -> str:
    """Nom de fichier sans chemin ni caractères gênants."""
    nom = PurePath(str(nom).replace("\\", "/")).name
    nom = re.sub(r"[^\w.\- ]", "_", nom).strip(" .")
    return nom[:80] or "fichier"


def encoder(type_: str, **champs) -> str:
    return json.dumps({"type": type_, **champs}, ensure_ascii=False)


def decoder(brut: str | bytes) -> dict | None:
    """Renvoie le message, ou None s'il est mal formé (jamais d'exception)."""
    try:
        message = json.loads(brut)
    except (ValueError, TypeError):
        return None
    if isinstance(message, dict) and isinstance(message.get("type"), str):
        return message
    return None


def heure() -> str:
    return datetime.now().strftime("%H:%M")


def taille_lisible(octets: int) -> str:
    for unite in ("o", "Ko", "Mo"):
        if octets < 1024:
            return f"{octets:.0f} {unite}"
        octets /= 1024
    return f"{octets:.1f} Go"
