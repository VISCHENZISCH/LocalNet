"""Serveur du salon : relaie messages, photos et vidéos entre les clients.

Usage :
    .venv/bin/python -m chat.serveur              # port 8765, annoncé en mDNS
    .venv/bin/python -m chat.serveur --port 9000 --quota 2

Pas besoin de root. Un seul port, en TLS : le salon en WebSocket (/ws), les
fichiers et photos de profil en HTTPS, et le client web pour les téléphones
(/). Les fichiers reçus sont gardés dans un dossier temporaire le temps de la
session, dans la limite du quota. Les comptes, les photos de profil et le
certificat sont gardés dans ~/.local/share/LocalNet/ (voir comptes.py, tls.py).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import mimetypes
import re
import shutil
import socket
import sys
import tempfile
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

from aiohttp import WSMsgType, web

from . import tls
from .comptes import Comptes, ErreurCompte, dossier_donnees
from .decouverte import ip_locale
from .protocole import (
    CHEMIN_AVATARS, CHEMIN_FICHIERS, CHEMIN_WS, FICHIER_MAX, PORT_DEFAUT, QUOTA_DEFAUT, TAILLE_ID,
    TAILLE_MAX, TAILLE_TRAME, TYPE_SERVICE, VERSION, decoder, encoder, genre, heure, nom_sur, taille_lisible,
)

WEB = Path(__file__).resolve().parent / "web"
_ID_CLIENT = re.compile(rf"[0-9a-f]{{{TAILLE_ID}}}")
FILE_MAX = 2000  # messages en attente pour un membre ; au-delà, il est trop lent et on le coupe


def journal(texte: str) -> None:
    print(f"{heure()}  {texte}", flush=True)


class Limiteur:
    """Au plus `maximum` événements par adresse sur une fenêtre glissante de `fenetre` secondes."""

    def __init__(self, maximum: int, fenetre: float):
        self.maximum, self.fenetre = maximum, fenetre
        self.dates: dict[str, deque[float]] = defaultdict(deque)

    def attente(self, cle: str) -> float:
        """Secondes avant le prochain essai autorisé ; 0 si on peut y aller."""
        dates, maintenant = self.dates[cle], time.monotonic()
        while dates and dates[0] <= maintenant - self.fenetre:
            dates.popleft()
        if not dates:
            del self.dates[cle]
            return 0
        return dates[0] + self.fenetre - maintenant if len(dates) >= self.maximum else 0

    def noter(self, cle: str) -> None:
        self.dates[cle].append(time.monotonic())


class Membre:
    """Un client connecté. Les envois passent par une file : un client lent ne bloque pas le salon,
    et chacun reçoit les messages dans l'ordre."""

    def __init__(self, pseudo: str, ws: web.WebSocketResponse):
        self.pseudo, self.ws = pseudo, ws
        self.file: asyncio.Queue[str | None] = asyncio.Queue()
        self.ferme = False
        self.tache = asyncio.create_task(self._ecrire())

    def envoyer(self, texte: str) -> None:
        if self.ferme:
            return
        if self.file.qsize() >= FILE_MAX:
            journal(f"  {self.pseudo} ne suit plus : déconnecté")
            self.fermer()
            return
        self.file.put_nowait(texte)

    def fermer(self, raison: str | None = None) -> None:
        """Ferme après les envois en cours ; `raison` : erreur fatale envoyée avant."""
        if self.ferme:
            return
        if raison:
            self.file.put_nowait(encoder("erreur", texte=raison, fatal=True))
        self.file.put_nowait(None)
        self.ferme = True

    async def _ecrire(self) -> None:
        try:
            while (texte := await self.file.get()) is not None:
                await self.ws.send_str(texte)
        except (ConnectionError, RuntimeError):
            pass  # connexion déjà fermée
        finally:
            self.ferme = True
            await self.ws.close()


@dataclass
class Envoi:
    """Fichier en cours de réception depuis un client."""
    nom: str
    genre: str
    taille: int
    chemin: Path
    flux: BinaryIO
    recu: int = 0


@dataclass
class Fichier:
    chemin: Path
    nom: str
    taille: int


@dataclass
class Salon:
    dossier: Path
    comptes: Comptes
    taille_historique: int = 80
    quota: int = QUOTA_DEFAUT
    delai_echec: float = 1.0  # secondes d'attente après un mauvais mot de passe
    membres: dict[str, Membre] = field(default_factory=dict)
    fichiers: dict[str, Fichier] = field(default_factory=dict)  # id -> fichier, du plus ancien au plus récent
    occupe: int = 0   # octets des fichiers gardés
    reserve: int = 0  # octets annoncés par les envois en cours
    echecs: Limiteur = field(default_factory=lambda: Limiteur(5, 60))       # mots de passe faux / IP
    creations: Limiteur = field(default_factory=lambda: Limiteur(5, 3600))  # comptes créés / IP

    def __post_init__(self) -> None:
        self.historique: deque[dict] = deque(maxlen=self.taille_historique)
        self.verrous_ip: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.scrypt = asyncio.Semaphore(4)  # calculs de mot de passe simultanés

    def liste(self) -> list[str]:
        return sorted(self.membres, key=str.lower)

    def diffuser(self, message: str, sauf: str | None = None) -> None:
        for pseudo, membre in self.membres.items():
            if pseudo != sauf:
                membre.envoyer(message)

    def publier(self, type_: str, **champs) -> None:
        """Diffuse à tous (auteur compris : même ordre pour tous) et garde dans l'historique."""
        champs["heure"] = heure()
        self.historique.append({"type": type_, **champs})
        self.diffuser(encoder(type_, **champs))

    # --- Connexion WebSocket ------------------------------------------------

    async def websocket(self, requete: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=TAILLE_TRAME, heartbeat=20)
        await ws.prepare(requete)
        ip = requete.remote or "?"
        pseudo = await self._presentation(ws, ip)
        if pseudo is None:
            await ws.close()
            return ws

        # Rien n'attend entre la vérification et ici : deux connexions au même compte
        # ne peuvent pas s'intercaler, la dernière arrivée remplace l'autre.
        membre = Membre(pseudo, ws)
        ancien = self.membres.get(pseudo)
        self.membres[pseudo] = membre
        if ancien:
            ancien.fermer("Ce compte vient de se connecter depuis un autre appareil.")
        envois: dict[bytes, Envoi] = {}
        journal(f"+ {pseudo} ({ip}) — {len(self.membres)} en ligne" + (" (remplace l'ancienne connexion)"
                                                                      if ancien else ""))
        membre.envoyer(encoder("bienvenue", pseudo=pseudo, membres=self.liste(),
                               historique=list(self.historique), avatars=self.comptes.avatars()))
        if not ancien:
            self.diffuser(encoder("arrivee", pseudo=pseudo, heure=heure(), membres=self.liste()), sauf=pseudo)
        try:
            async for brut in ws:
                if brut.type == WSMsgType.BINARY:
                    self._morceau(pseudo, membre, envois, brut.data)
                elif brut.type == WSMsgType.TEXT and (message := decoder(brut.data)) is not None:
                    self._traiter(pseudo, membre, envois, message)
        finally:
            for envoi in envois.values():
                self._abandonner(envoi)
            membre.fermer()
            if self.membres.get(pseudo) is membre:  # sinon, une connexion plus récente a pris la place
                del self.membres[pseudo]
                journal(f"- {pseudo} — {len(self.membres)} en ligne")
                self.diffuser(encoder("depart", pseudo=pseudo, heure=heure(), membres=self.liste()))
        return ws

    async def _presentation(self, ws: web.WebSocketResponse, ip: str) -> str | None:
        try:
            brut = await ws.receive(timeout=10)
        except TimeoutError:
            return None
        message = decoder(brut.data) if brut.type == WSMsgType.TEXT else None
        if not message or message["type"] != "bonjour":
            return None

        # Une présentation à la fois par adresse : ouvrir 100 connexions en parallèle
        # ne permet pas d'essayer 100 mots de passe d'un coup.
        async with self.verrous_ip[ip]:
            try:
                pseudo = await self._verifier(message, ip)
            except ErreurCompte as e:
                await ws.send_str(encoder("erreur", texte=str(e), fatal=True))
                return None
        return pseudo

    async def _verifier(self, message: dict, ip: str) -> str:
        if attente := self.echecs.attente(ip):
            raise ErreurCompte(f"Trop d'essais de mot de passe : réessayez dans {attente:.0f} s.")
        pseudo, mdp = message.get("pseudo"), message.get("mot_de_passe")
        async with self.scrypt:  # scrypt prend ~50 ms : hors de la boucle pour ne pas bloquer le salon
            if message.get("nouveau") is True:
                if attente := self.creations.attente(ip):
                    raise ErreurCompte(f"Trop de comptes créés depuis cet appareil : "
                                       f"réessayez dans {attente / 60:.0f} min.")
                cree = await asyncio.to_thread(self.comptes.creer, pseudo, mdp)
                self.creations.noter(ip)
                journal(f"  compte créé : {cree} ({ip})")
                return cree
            try:
                return await asyncio.to_thread(self.comptes.verifier, pseudo, mdp)
            except ErreurCompte:
                self.echecs.noter(ip)
                await asyncio.sleep(self.delai_echec)
                raise

    def _traiter(self, pseudo: str, membre: Membre, envois: dict[bytes, Envoi], message: dict) -> None:
        if message["type"] == "avatar":
            donnees = message.get("donnees")
            try:
                brut = None if donnees is None else base64.b64decode(str(donnees), validate=True)
                self.comptes.definir_avatar(pseudo, brut)
            except (ErreurCompte, binascii.Error) as e:
                self._erreur(membre, str(e) if isinstance(e, ErreurCompte) else "Photo illisible.")
                return
            self.diffuser(encoder("avatars", avatars=self.comptes.avatars()))

        elif message["type"] == "message":
            texte = message.get("texte")
            if not isinstance(texte, str) or not texte.strip():
                return
            if len(texte) > TAILLE_MAX:
                self._erreur(membre, f"Message trop long (max. {TAILLE_MAX} caractères).")
                return
            self.publier("message", de=pseudo, texte=texte.strip())

        elif message["type"] == "fichier":
            id_client, nom, taille = message.get("id"), nom_sur(message.get("nom")), message.get("taille")
            if not isinstance(id_client, str) or not _ID_CLIENT.fullmatch(id_client):
                return
            if (genre_ := genre(nom)) is None:
                self._erreur(membre, f"« {nom} » : seules les photos et vidéos sont acceptées.")
            elif not isinstance(taille, int) or not 0 < taille <= min(FICHIER_MAX, self.quota):
                self._erreur(membre, f"« {nom} » : taille maximale "
                                     f"{taille_lisible(min(FICHIER_MAX, self.quota))}.")
            elif not self._faire_place(taille):
                self._erreur(membre, f"« {nom} » : le salon est plein (envois en cours), réessayez plus tard.")
            else:
                chemin = self.dossier / uuid.uuid4().hex
                self.reserve += taille
                envois[id_client.encode()] = Envoi(nom, genre_, taille, chemin, chemin.open("wb"))

    def _faire_place(self, taille: int) -> bool:
        """Supprime les fichiers les plus anciens jusqu'à pouvoir en garder `taille` octets de plus."""
        while self.occupe + self.reserve + taille > self.quota and self.fichiers:
            id_ = next(iter(self.fichiers))
            fichier = self.fichiers.pop(id_)
            self.occupe -= fichier.taille
            try:
                fichier.chemin.unlink(missing_ok=True)
            except OSError:  # Windows : en cours de téléchargement, il partira avec le dossier
                pass
            journal(f"  quota atteint : {fichier.nom} supprimé")
        return self.occupe + self.reserve + taille <= self.quota

    def _abandonner(self, envoi: Envoi) -> None:
        envoi.flux.close()
        envoi.chemin.unlink(missing_ok=True)
        self.reserve -= envoi.taille

    def _morceau(self, pseudo: str, membre: Membre, envois: dict[bytes, Envoi], trame: bytes) -> None:
        cle, morceau = trame[:TAILLE_ID], trame[TAILLE_ID:]
        envoi = envois.get(cle)
        if envoi is None:
            return  # envoi refusé : on ignore la suite
        if envoi.recu + len(morceau) > envoi.taille:
            del envois[cle]
            self._abandonner(envoi)
            self._erreur(membre, f"« {envoi.nom} » : plus de données qu'annoncé, envoi annulé.")
            return
        envoi.flux.write(morceau)
        envoi.recu += len(morceau)
        if envoi.recu == envoi.taille:
            del envois[cle]
            envoi.flux.close()
            self.reserve -= envoi.taille
            self.occupe += envoi.taille
            id_ = envoi.chemin.name
            self.fichiers[id_] = Fichier(envoi.chemin, envoi.nom, envoi.taille)
            journal(f"  {pseudo} partage {envoi.nom} ({taille_lisible(envoi.taille)})")
            self.publier("fichier", de=pseudo, id=id_, nom=envoi.nom, taille=envoi.taille, genre=envoi.genre)

    @staticmethod
    def _erreur(membre: Membre, texte: str) -> None:
        membre.envoyer(encoder("erreur", texte=texte, fatal=False))

    # --- HTTP ---------------------------------------------------------------

    async def fichier(self, requete: web.Request) -> web.StreamResponse:
        """GET /fichiers/<id> : lu au fil de l'eau, reprise (Range) possible pour les vidéos."""
        fichier = self.fichiers.get(requete.match_info["id"])
        if fichier is None or not fichier.chemin.exists():
            raise web.HTTPNotFound(text="Fichier introuvable (salon fermé ou quota dépassé).\n")
        type_mime = mimetypes.guess_type(fichier.nom)[0] or "application/octet-stream"
        return web.FileResponse(fichier.chemin, headers={
            "Content-Type": type_mime,
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(fichier.nom)}",
            "Cache-Control": "private, max-age=86400, immutable",
        })

    async def avatar(self, requete: web.Request) -> web.StreamResponse:
        chemin = self.comptes.chemin_avatar(requete.match_info["id"])
        if chemin is None:
            raise web.HTTPNotFound(text="Photo introuvable.\n")
        type_mime = "image/png" if chemin.read_bytes()[:4] == b"\x89PNG" else "image/jpeg"
        return web.FileResponse(chemin, headers={"Content-Type": type_mime,
                                                 "Cache-Control": "private, max-age=86400, immutable"})


@web.middleware
async def _entetes(request: web.Request,
                   handler: Callable[[web.Request], Awaitable[web.StreamResponse]]) -> web.StreamResponse:
    reponse = await handler(request)
    reponse.headers.setdefault("X-Content-Type-Options", "nosniff")
    reponse.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.path.startswith((CHEMIN_FICHIERS, CHEMIN_AVATARS)):
        # Contenu envoyé par les membres : jamais interprété comme une page.
        reponse.headers.setdefault("Content-Security-Policy", "default-src 'none'; sandbox")
    elif request.path != CHEMIN_WS:
        reponse.headers.setdefault("Content-Security-Policy", (
            "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
            f"connect-src 'self' wss://{request.host}; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"))
    return reponse


def creer_app(salon: Salon) -> web.Application:
    app = web.Application(middlewares=[_entetes])
    app.router.add_get(CHEMIN_WS, salon.websocket)
    app.router.add_get(CHEMIN_FICHIERS + "{id:[0-9a-f]{32}}", salon.fichier)
    app.router.add_get(CHEMIN_AVATARS + "{id:[0-9a-f]{16}}", salon.avatar)

    async def accueil(_requete: web.Request) -> web.FileResponse:
        return web.FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})

    app.router.add_get("/", accueil)
    app.router.add_static("/web/", WEB)
    return app


async def annoncer(ip: str, port: int):
    """Annonce le salon en mDNS pour que les clients le trouvent sans IP."""
    from zeroconf import ServiceInfo
    from zeroconf.asyncio import AsyncZeroconf

    nom = socket.gethostname()
    info = ServiceInfo(
        TYPE_SERVICE, f"{nom}.{TYPE_SERVICE}",
        addresses=[socket.inet_aton(ip)], port=port,
        properties={"version": VERSION}, server=f"{nom}.local.",
    )
    azc = AsyncZeroconf(interfaces=[ip])
    await azc.async_register_service(info)
    return azc, info


async def lancer(port: int = PORT_DEFAUT, annonce: bool = True, donnees: Path | None = None,
                 quota: int = QUOTA_DEFAUT, pret: Callable[[], None] | None = None,
                 arret: asyncio.Event | None = None) -> None:
    """Fait tourner le salon jusqu'à ce que `arret` soit levé (ou Ctrl+C). `pret` : appelé une fois ouvert."""
    ip = ip_locale()
    donnees = donnees or dossier_donnees()
    contexte_ssl, empreinte = tls.contexte(donnees, ip)
    dossier = Path(tempfile.mkdtemp(prefix="localnet-"))
    salon = Salon(dossier, Comptes(donnees), quota=quota)
    runner = web.AppRunner(creer_app(salon), access_log=None, shutdown_timeout=2)
    await runner.setup()
    mdns = None
    try:
        await web.TCPSite(runner, "0.0.0.0", port, ssl_context=contexte_ssl).start()
        if annonce:
            try:
                mdns = await annoncer(ip, port)
            except Exception as e:  # le salon fonctionne aussi sans mDNS
                journal(f"Annonce mDNS impossible : {e}")
        journal(f"Salon ouvert sur {ip}:{port}" + (" (annoncé en mDNS)" if mdns else ""))
        journal(f"Téléphones : https://{ip}:{port}  ·  certificat {tls.empreinte_lisible(empreinte)}")
        if pret:
            pret()
        await (arret or asyncio.Event()).wait()
    finally:
        for membre in list(salon.membres.values()):
            membre.fermer("Le salon a été fermé.")
        if mdns:
            azc, info = mdns
            await azc.async_unregister_service(info)
            await azc.async_close()
        await runner.cleanup()
        shutil.rmtree(dossier, ignore_errors=True)
        journal("Salon fermé.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Serveur du salon LocalNet.")
    p.add_argument("-p", "--port", type=int, default=PORT_DEFAUT, help=f"port (défaut : {PORT_DEFAUT})")
    p.add_argument("--sans-annonce", action="store_true", help="ne pas s'annoncer en mDNS")
    p.add_argument("--donnees", type=Path, help="dossier des comptes et du certificat "
                                                "(défaut : ~/.local/share/LocalNet)")
    p.add_argument("--quota", type=float, default=QUOTA_DEFAUT / 1024**3,
                   help="Go de fichiers gardés au plus ; au-delà, les plus anciens sont supprimés (défaut : 5)")
    args = p.parse_args(argv)
    try:
        asyncio.run(lancer(args.port, not args.sans_annonce, args.donnees, int(args.quota * 1024**3)))
    except OSError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
