import asyncio
import base64
import socket
import ssl

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer

from chat import serveur
from chat.comptes import Comptes
from chat.serveur import Limiteur, Salon, creer_app

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 100


@pytest.fixture
def salon(tmp_path):
    (tmp_path / "fichiers").mkdir()
    return Salon(tmp_path / "fichiers", Comptes(tmp_path / "donnees"), delai_echec=0)


@pytest.fixture
async def client(salon):
    async with TestClient(TestServer(creer_app(salon))) as c:
        yield c


async def bonjour(client, pseudo="alice", mdp="secret", nouveau=False):
    ws = await client.ws_connect("/ws")
    await ws.send_json({"type": "bonjour", "pseudo": pseudo, "mot_de_passe": mdp, "nouveau": nouveau})
    return ws, await ws.receive_json(timeout=5)


async def creer(client, pseudo="alice"):
    ws, m = await bonjour(client, pseudo, nouveau=True)
    assert m["type"] == "bienvenue"
    await ws.close()


async def lire_tout(ws, delai=0.5):
    """Messages reçus jusqu'à la fermeture ou `delai` secondes de silence ; (types, fermée)."""
    types = []
    while True:
        try:
            m = await ws.receive(timeout=delai)
        except TimeoutError:
            return types, False
        if m.type != aiohttp.WSMsgType.TEXT:
            return types, True
        types.append(m.json()["type"])


async def attendre(ws, type_):
    """Prochain message de ce type (les autres sont ignorés)."""
    while True:
        m = await ws.receive_json(timeout=5)
        if m["type"] == type_:
            return m


async def envoyer_fichier(ws, contenu, nom="photo.png", id_="0123abcd"):
    await ws.send_json({"type": "fichier", "id": id_, "nom": nom, "taille": len(contenu)})
    for i in range(0, len(contenu), 200_000):
        await ws.send_bytes(id_.encode() + contenu[i:i + 200_000])


# --- Comptes et connexion -------------------------------------------------------


async def test_creation_puis_connexion(client):
    ws, m = await bonjour(client, nouveau=True)
    assert m["type"] == "bienvenue" and m["membres"] == ["alice"]
    await ws.close()
    ws, m = await bonjour(client)
    assert m["type"] == "bienvenue"


async def test_mauvais_mot_de_passe(client):
    await creer(client)
    ws, m = await bonjour(client, mdp="mauvais")
    assert m == {"type": "erreur", "texte": "Mot de passe incorrect.", "fatal": True}
    assert (await ws.receive()).type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)


async def test_trop_d_essais(client, salon):
    ws, _ = await bonjour(client, nouveau=True)
    await ws.close()
    for _ in range(5):
        _, m = await bonjour(client, mdp="mauvais")
        assert "incorrect" in m["texte"]
    _, m = await bonjour(client)  # même le bon mot de passe est refusé un moment
    assert m["fatal"] and "Trop d'essais" in m["texte"]


async def test_trop_de_comptes(client):
    for i in range(5):
        ws, m = await bonjour(client, f"membre{i}", nouveau=True)
        assert m["type"] == "bienvenue"
        await ws.close()
    _, m = await bonjour(client, "membre5", nouveau=True)
    assert m["fatal"] and "Trop de comptes" in m["texte"]


async def test_essais_en_parallele_un_a_la_fois(client, salon, monkeypatch):
    """Ouvrir plein de connexions d'un coup ne fait pas tester plus d'un mot de passe à la fois."""
    await creer(client)
    en_cours = maximum = 0
    verifier = salon.comptes.verifier

    def compter(*args):
        nonlocal en_cours, maximum
        en_cours += 1
        maximum = max(maximum, en_cours)
        try:
            return verifier(*args)
        finally:
            en_cours -= 1

    monkeypatch.setattr(salon.comptes, "verifier", compter)
    salon.delai_echec = 0.05
    await asyncio.gather(*(bonjour(client, mdp=f"essai{i}") for i in range(8)))
    assert maximum == 1


async def test_nouvelle_connexion_remplace_l_ancienne(client, salon):
    ancien, _ = await bonjour(client, nouveau=True)
    temoin, _ = await bonjour(client, "bob", nouveau=True)
    nouveau, m = await bonjour(client)
    assert m["type"] == "bienvenue"

    m = await attendre(ancien, "erreur")
    assert m["fatal"] and "autre appareil" in m["texte"]
    await asyncio.sleep(0.1)
    assert salon.membres["alice"].ws is not None and not nouveau.closed
    assert sorted(salon.membres) == ["alice", "bob"]

    # Le départ de l'ancienne connexion n'est pas annoncé : alice est toujours là.
    await temoin.send_json({"type": "message", "texte": "toujours là ?"})
    m = await temoin.receive_json(timeout=5)
    assert m["type"] == "message"


async def test_connexions_simultanees_au_meme_compte(client, salon):
    """Ancien bug : les deux passaient, et la fermeture de l'une retirait l'autre de la liste."""
    await creer(client)
    await asyncio.sleep(0.1)
    (a, ma), (b, mb) = await asyncio.gather(bonjour(client), bonjour(client))
    assert ma["type"] == mb["type"] == "bienvenue"
    (types_a, ferme_a), (types_b, ferme_b) = await asyncio.gather(lire_tout(a), lire_tout(b))
    assert ferme_a != ferme_b  # une seule des deux est coupée…
    assert "erreur" in (types_a if ferme_a else types_b)  # … et elle sait pourquoi
    assert list(salon.membres) == ["alice"]
    await (b if ferme_a else a).close()
    await asyncio.sleep(0.1)
    assert salon.membres == {}


async def test_message_diffuse_a_tous(client):
    a, _ = await bonjour(client, nouveau=True)
    b, _ = await bonjour(client, "bob", nouveau=True)
    await attendre(a, "arrivee")
    await b.send_json({"type": "message", "texte": "  bonjour  "})
    for ws in (a, b):
        m = await attendre(ws, "message")
        assert (m["de"], m["texte"]) == ("bob", "bonjour")


# --- Fichiers --------------------------------------------------------------------


async def test_envoi_et_telechargement(client, salon):
    ws, _ = await bonjour(client, nouveau=True)
    contenu = bytes(range(256)) * 2000  # 512 Ko, en plusieurs trames
    await envoyer_fichier(ws, contenu, "vacances.png")
    m = await attendre(ws, "fichier")
    assert (m["nom"], m["taille"], m["genre"]) == ("vacances.png", len(contenu), "image")

    reponse = await client.get(f"/fichiers/{m['id']}")
    assert reponse.status == 200
    assert reponse.headers["Content-Type"] == "image/png"
    assert reponse.headers["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in reponse.headers["Content-Security-Policy"]
    assert await reponse.read() == contenu

    partiel = await client.get(f"/fichiers/{m['id']}", headers={"Range": "bytes=100-199"})
    assert partiel.status == 206 and await partiel.read() == contenu[100:200]
    assert salon.occupe == len(contenu) and salon.reserve == 0


async def test_fichier_refuse(client):
    ws, _ = await bonjour(client, nouveau=True)
    await ws.send_json({"type": "fichier", "id": "0123abcd", "nom": "page.html", "taille": 10})
    assert "photos et vidéos" in (await attendre(ws, "erreur"))["texte"]


async def test_plus_de_donnees_qu_annonce(client, salon):
    ws, _ = await bonjour(client, nouveau=True)
    await ws.send_json({"type": "fichier", "id": "0123abcd", "nom": "a.png", "taille": 10})
    await ws.send_bytes(b"0123abcd" + b"x" * 20)
    assert "plus de données" in (await attendre(ws, "erreur"))["texte"]
    assert list(salon.dossier.iterdir()) == [] and salon.reserve == 0


async def test_deconnexion_pendant_un_envoi(client, salon):
    ws, _ = await bonjour(client, nouveau=True)
    await ws.send_json({"type": "fichier", "id": "0123abcd", "nom": "a.mp4", "taille": 1000})
    await ws.send_bytes(b"0123abcd" + b"x" * 100)
    await ws.close()
    await asyncio.sleep(0.1)
    assert list(salon.dossier.iterdir()) == [] and salon.reserve == 0


async def test_quota_supprime_les_plus_anciens(client, salon):
    salon.quota = 1000
    ws, _ = await bonjour(client, nouveau=True)
    await envoyer_fichier(ws, b"a" * 600, "a.png", "0000000a")
    premier = await attendre(ws, "fichier")
    await envoyer_fichier(ws, b"b" * 600, "b.png", "0000000b")
    second = await attendre(ws, "fichier")

    assert (await client.get(f"/fichiers/{premier['id']}")).status == 404
    assert await (await client.get(f"/fichiers/{second['id']}")).read() == b"b" * 600
    assert salon.occupe == 600 and len(list(salon.dossier.iterdir())) == 1


async def test_quota_compte_les_envois_en_cours(client, salon):
    salon.quota = 1000
    ws, _ = await bonjour(client, nouveau=True)
    await ws.send_json({"type": "fichier", "id": "0000000a", "nom": "a.png", "taille": 700})
    await ws.send_json({"type": "fichier", "id": "0000000b", "nom": "b.png", "taille": 700})
    assert "plein" in (await attendre(ws, "erreur"))["texte"]
    await ws.send_json({"type": "fichier", "id": "0000000c", "nom": "c.png", "taille": 2000})
    assert "taille maximale" in (await attendre(ws, "erreur"))["texte"]


async def test_avatar(client):
    ws, _ = await bonjour(client, nouveau=True)
    await ws.send_json({"type": "avatar", "donnees": base64.b64encode(PNG).decode()})
    id_ = (await attendre(ws, "avatars"))["avatars"]["alice"]
    reponse = await client.get(f"/avatars/{id_}")
    assert reponse.status == 200 and reponse.headers["Content-Type"] == "image/png"
    assert await reponse.read() == PNG


# --- HTTP ------------------------------------------------------------------------


async def test_client_web_servi(client):
    reponse = await client.get("/")
    assert reponse.status == 200 and "LocalNet" in await reponse.text()
    assert "frame-ancestors 'none'" in reponse.headers["Content-Security-Policy"]
    for chemin in ("/web/app.js", "/web/style.css", "/web/logo.svg", "/web/manifest.json"):
        assert (await client.get(chemin)).status == 200, chemin


async def test_chemins_inconnus(client):
    for chemin in ("/fichiers/0123456789abcdef0123456789abcdef", "/fichiers/../comptes.json",
                   "/avatars/zzzz", "/web/../serveur.py", "/web/%2e%2e/serveur.py"):
        assert (await client.get(chemin)).status in (403, 404), chemin


# --- Outils ----------------------------------------------------------------------


def test_limiteur(monkeypatch):
    maintenant = [1000.0]
    monkeypatch.setattr(serveur.time, "monotonic", lambda: maintenant[0])
    limiteur = Limiteur(2, 60)
    assert limiteur.attente("ip") == 0
    limiteur.noter("ip")
    limiteur.noter("ip")
    assert limiteur.attente("ip") == 60
    assert limiteur.attente("autre") == 0
    maintenant[0] += 61
    assert limiteur.attente("ip") == 0
    assert "ip" not in limiteur.dates  # les vieilles adresses ne s'accumulent pas


async def test_lancer_en_tls_puis_arreter(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    pret, arret = asyncio.Event(), asyncio.Event()
    tache = asyncio.create_task(serveur.lancer(port, annonce=False, donnees=tmp_path, pret=pret.set, arret=arret))
    await asyncio.wait_for(pret.wait(), 10)

    contexte = ssl.create_default_context()
    contexte.check_hostname, contexte.verify_mode = False, ssl.CERT_NONE
    async with aiohttp.ClientSession() as session, \
            session.ws_connect(f"wss://127.0.0.1:{port}/ws", ssl=contexte) as ws:
        await ws.send_json({"type": "bonjour", "pseudo": "alice", "mot_de_passe": "secret", "nouveau": True})
        assert (await ws.receive_json(timeout=5))["type"] == "bienvenue"
        arret.set()
        m = await ws.receive_json(timeout=5)
        assert m["fatal"] and "fermé" in m["texte"]
    await asyncio.wait_for(tache, 10)
    assert (tmp_path / "tls" / "certificat.pem").exists()
