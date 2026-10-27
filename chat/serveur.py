"""Serveur du salon : relaie messages, photos et vidéos entre les clients.

Usage :
    .venv/bin/python -m chat.serveur              # port 8765, annoncé en mDNS
    .venv/bin/python -m chat.serveur --port 9000

Pas besoin de root. Les fichiers reçus sont gardés dans un dossier temporaire
le temps de la session et servis en HTTP sur le même port.
"""

from __future__ import annotations

import argparse
import asyncio
import email.utils
import mimetypes
import re
import shutil
import socket
import sys
import tempfile
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from websockets.asyncio.server import ServerConnection, broadcast, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from .decouverte import ip_locale
from .protocole import (
    CHEMIN_FICHIERS, FICHIER_MAX, PORT_DEFAUT, TAILLE_ID, TAILLE_MAX, TAILLE_TRAME, TYPE_SERVICE,
    decoder, encoder, genre, heure, nom_sur, pseudo_valide, taille_lisible,
)

_ID_CLIENT = re.compile(rf"[0-9a-f]{{{TAILLE_ID}}}")


def journal(texte: str) -> None:
    print(f"{heure()}  {texte}", flush=True)


@dataclass
class Envoi:
    """Fichier en cours de réception depuis un client."""
    nom: str
    genre: str
    taille: int
    chemin: Path
    flux: BinaryIO
    recu: int = 0


class Salon:
    def __init__(self, dossier: Path, taille_historique: int = 80):
        self.dossier = dossier
        self.membres: dict[str, ServerConnection] = {}
        self.historique: deque[dict] = deque(maxlen=taille_historique)
        self.fichiers: dict[str, tuple[Path, str]] = {}  # id -> (chemin, nom)

    def liste(self) -> list[str]:
        return sorted(self.membres, key=str.lower)

    def diffuser(self, message: str, sauf: str | None = None) -> None:
        broadcast([c for p, c in self.membres.items() if p != sauf], message)

    def publier(self, type_: str, **champs) -> None:
        """Diffuse à tous (auteur compris : même ordre pour tous) et garde dans l'historique."""
        champs["heure"] = heure()
        self.historique.append({"type": type_, **champs})
        self.diffuser(encoder(type_, **champs))

    # --- Connexion WebSocket ------------------------------------------------

    async def accueillir(self, ws: ServerConnection) -> None:
        pseudo = await self._presentation(ws)
        if pseudo is None:
            return

        self.membres[pseudo] = ws
        envois: dict[bytes, Envoi] = {}
        journal(f"+ {pseudo} ({ws.remote_address[0]}) — {len(self.membres)} en ligne")
        await ws.send(encoder("bienvenue", pseudo=pseudo, membres=self.liste(),
                              historique=list(self.historique)))
        self.diffuser(encoder("arrivee", pseudo=pseudo, heure=heure(), membres=self.liste()), sauf=pseudo)
        try:
            async for brut in ws:
                if isinstance(brut, bytes):
                    await self._morceau(pseudo, ws, envois, brut)
                elif (message := decoder(brut)) is not None:
                    await self._traiter(pseudo, ws, envois, message)
        except ConnectionClosed:
            pass
        finally:
            for envoi in envois.values():
                envoi.flux.close()
                envoi.chemin.unlink(missing_ok=True)
            del self.membres[pseudo]
            journal(f"- {pseudo} — {len(self.membres)} en ligne")
            self.diffuser(encoder("depart", pseudo=pseudo, heure=heure(), membres=self.liste()))

    async def _presentation(self, ws: ServerConnection) -> str | None:
        try:
            message = decoder(await asyncio.wait_for(ws.recv(), timeout=10))
        except (TimeoutError, ConnectionClosed):
            return None

        pseudo = message.get("pseudo") if message and message["type"] == "bonjour" else None
        if not pseudo_valide(pseudo):
            erreur = "Pseudo invalide : 1 à 20 caractères parmi lettres, chiffres, « . », « _ », « - »."
        elif any(p.lower() == pseudo.lower() for p in self.membres):
            erreur = f"Le pseudo « {pseudo} » est déjà pris."
        else:
            return pseudo
        await ws.send(encoder("erreur", texte=erreur, fatal=True))
        await ws.close()
        return None

    async def _traiter(self, pseudo: str, ws: ServerConnection, envois: dict[bytes, Envoi],
                       message: dict) -> None:
        if message["type"] == "message":
            texte = message.get("texte")
            if not isinstance(texte, str) or not texte.strip():
                return
            if len(texte) > TAILLE_MAX:
                await self._erreur(ws, f"Message trop long (max. {TAILLE_MAX} caractères).")
                return
            self.publier("message", de=pseudo, texte=texte.strip())

        elif message["type"] == "fichier":
            id_client, nom, taille = message.get("id"), nom_sur(message.get("nom")), message.get("taille")
            if not isinstance(id_client, str) or not _ID_CLIENT.fullmatch(id_client):
                return
            if genre(nom) is None:
                await self._erreur(ws, f"« {nom} » : seules les photos et vidéos sont acceptées.")
            elif not isinstance(taille, int) or not 0 < taille <= FICHIER_MAX:
                await self._erreur(ws, f"« {nom} » : taille maximale {taille_lisible(FICHIER_MAX)}.")
            else:
                chemin = self.dossier / uuid.uuid4().hex
                envois[id_client.encode()] = Envoi(nom, genre(nom), taille, chemin, chemin.open("wb"))

    async def _morceau(self, pseudo: str, ws: ServerConnection, envois: dict[bytes, Envoi],
                       trame: bytes) -> None:
        cle, morceau = trame[:TAILLE_ID], trame[TAILLE_ID:]
        envoi = envois.get(cle)
        if envoi is None:
            return  # envoi refusé : on ignore la suite
        if envoi.recu + len(morceau) > envoi.taille:
            del envois[cle]
            envoi.flux.close()
            envoi.chemin.unlink(missing_ok=True)
            await self._erreur(ws, f"« {envoi.nom} » : plus de données qu'annoncé, envoi annulé.")
            return
        envoi.flux.write(morceau)
        envoi.recu += len(morceau)
        if envoi.recu == envoi.taille:
            del envois[cle]
            envoi.flux.close()
            id_ = envoi.chemin.name
            self.fichiers[id_] = (envoi.chemin, envoi.nom)
            journal(f"  {pseudo} partage {envoi.nom} ({taille_lisible(envoi.taille)})")
            self.publier("fichier", de=pseudo, id=id_, nom=envoi.nom, taille=envoi.taille, genre=envoi.genre)

    @staticmethod
    async def _erreur(ws: ServerConnection, texte: str) -> None:
        await ws.send(encoder("erreur", texte=texte, fatal=False))

    # --- Téléchargement HTTP ------------------------------------------------

    async def servir_fichier(self, connexion: ServerConnection, requete: Request) -> Response | None:
        """GET /fichiers/<id> -> contenu ; toute autre requête continue en WebSocket."""
        chemin = requete.path.split("?", 1)[0]
        if not chemin.startswith(CHEMIN_FICHIERS):
            return None
        fichier = self.fichiers.get(chemin.removeprefix(CHEMIN_FICHIERS))
        if fichier is None:
            return connexion.respond(404, "Fichier introuvable.\n")
        contenu = await asyncio.to_thread(fichier[0].read_bytes)
        type_mime = mimetypes.guess_type(fichier[1])[0] or "application/octet-stream"
        entetes = Headers([
            ("Date", email.utils.formatdate(usegmt=True)),
            ("Connection", "close"),
            ("Content-Length", str(len(contenu))),
            ("Content-Type", type_mime),
        ])
        return Response(200, "OK", entetes, contenu)


async def annoncer(ip: str, port: int):
    """Annonce le salon en mDNS pour que les clients le trouvent sans IP."""
    from zeroconf import ServiceInfo
    from zeroconf.asyncio import AsyncZeroconf

    nom = socket.gethostname()
    info = ServiceInfo(
        TYPE_SERVICE, f"{nom}.{TYPE_SERVICE}",
        addresses=[socket.inet_aton(ip)], port=port,
        properties={"version": "2"}, server=f"{nom}.local.",
    )
    azc = AsyncZeroconf(interfaces=[ip])
    await azc.async_register_service(info)
    return azc, info


async def lancer(args: argparse.Namespace) -> None:
    ip = ip_locale()
    dossier = Path(tempfile.mkdtemp(prefix="localnet-"))
    salon = Salon(dossier)
    try:
        async with serve(salon.accueillir, "0.0.0.0", args.port, max_size=TAILLE_TRAME,
                         process_request=salon.servir_fichier) as serveur:
            annonce = None
            if not args.sans_annonce:
                try:
                    annonce = await annoncer(ip, args.port)
                except Exception as e:  # le salon fonctionne aussi sans mDNS
                    journal(f"Annonce mDNS impossible : {e}")

            journal(f"Salon ouvert sur {ip}:{args.port}" + (" (annoncé en mDNS)" if annonce else ""))
            try:
                await serveur.serve_forever()
            finally:
                if annonce:
                    azc, info = annonce
                    await azc.async_unregister_service(info)
                    await azc.async_close()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Serveur du salon LocalNet.")
    p.add_argument("-p", "--port", type=int, default=PORT_DEFAUT, help=f"port (défaut : {PORT_DEFAUT})")
    p.add_argument("--sans-annonce", action="store_true", help="ne pas s'annoncer en mDNS")
    args = p.parse_args(argv)
    try:
        asyncio.run(lancer(args))
    except OSError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        journal("Salon fermé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
