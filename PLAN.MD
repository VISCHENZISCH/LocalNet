# LocalNet

Discussion et partage de **photos et vidéos** entre les appareils d'un même
réseau local (PC avec l'application, téléphones avec le navigateur). Rien ne
passe par Internet.

Principe : **compte → IP du salon → chat + médias.**

1. Un PC héberge le salon (bouton vert « Héberger un salon sur ce PC ») ; son IP
   s'affiche en grand sur l'écran d'accueil.
2. Chacun entre son **nom d'utilisateur** et son **mot de passe**
   (onglet « Créer un compte » la première fois, « Se connecter » ensuite),
   puis l'IP du salon — ou clique sur un salon détecté automatiquement (mDNS).
   Sur téléphone : `https://<IP>:8765` dans le navigateur.
3. On discute, on envoie photos et vidéos (bouton image ou glisser-déposer).
   Les photos s'affichent dans le fil ; les vidéos s'ouvrent dans le lecteur
   du système. Bouton « Enregistrer » → `~/Téléchargements/LocalNet/`.
4. **Paramètres** (roue dentée) : photo de profil, thème clair ou sombre.

## Lancer

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"             # aiohttp, cryptography, zeroconf, PySide6 + outils

.venv/bin/python -m desktop.app               # application (sans sudo)
.venv/bin/python -m chat.serveur              # salon seul, sans interface (port 8765)
```

## Fonctionnement

- **Serveur** (`chat/serveur.py`, aiohttp) : un seul port (8765), en TLS, toutes
  interfaces. `/ws` : le salon (WebSocket) ; `/fichiers/<id>`, `/avatars/<id>` :
  téléchargements, servis en flux (jamais lus entièrement en mémoire, Range
  géré) ; `/` et `/web/` : version mobile. Relaie les messages, garde un
  historique des 80 derniers éléments, s'annonce en mDNS (`_localnet-chat._tcp`,
  version 3). Chaque membre a une file d'envoi : un client lent ne bloque pas
  les autres (coupé au-delà de 2000 messages en attente).
- **Connexion** : un compte n'est connecté qu'une fois ; une nouvelle connexion
  réussie remplace l'ancienne (erreur fatale « autre appareil », pas de
  reconnexion en boucle). Le remplacement se fait sans `await` entre la
  vérification et l'inscription : deux connexions simultanées ne peuvent pas
  s'intercaler.
- **Limites** : une présentation à la fois par IP, 5 mauvais mots de passe par
  minute et par IP, 5 comptes créés par heure et par IP, 4 calculs scrypt
  simultanés ; quota de fichiers (5 Go par défaut, `--quota`) qui compte les
  envois en cours, et supprime les fichiers les plus anciens.
- **TLS** (`chat/tls.py`) : certificat auto-signé ECDSA P-256 créé au premier
  lancement dans `<données>/tls/`, valable 10 ans. Le client de bureau retient
  l'empreinte SHA-256 par « hôte:port » (QSettings `certificats/…`) et demande
  confirmation si elle change. Les téléchargements HTTPS vérifient la même
  empreinte.
- **Comptes** (`chat/comptes.py`) : propres à chaque salon, gardés sur le PC qui
  l'héberge dans `~/.local/share/LocalNet/comptes.json` (droits 600). Mots de
  passe hachés avec scrypt + sel ; 1 s d'attente après un échec.
- **Photos de profil** : recadrées en 256×256 (JPEG) par le client, gardées par
  le serveur dans `avatars/`, servies en `GET /avatars/<id>`. La photo choisie
  sur ce PC fait foi : elle est renvoyée au salon si elle diffère. Sans photo
  sur ce PC, celle du salon est gardée (choisie depuis un téléphone, par exemple).
- **Fichiers** : envoyés en trames binaires de 256 Ko (8 octets d'identifiant +
  données), écrits dans un dossier temporaire, puis servis en HTTP sur le même
  port (`GET /fichiers/<id>`). Le dossier est supprimé à la fermeture du salon.
  Formats : png, jpg, gif, webp, bmp, mp4, webm, mov, mkv, avi, m4v ; 500 Mo max.
- **Client** (`desktop/client.py`) : QWebSocket ; l'envoi lit le fichier au fur
  et à mesure (jamais entièrement en mémoire) avec barre de progression ;
  les fichiers reçus sont mis en cache dans `~/.cache/LocalNet/fichiers/`.
  Le salon hébergé tourne dans un thread de l'application (`ServeurLocal`),
  arrêté par un `asyncio.Event` : nettoyage identique sous Linux et Windows, et
  fonctionne dans l'exécutable PyInstaller.
- **Version mobile** (`chat/web/`) : HTML/CSS/JS sans bibliothèque, même
  protocole. Envoi par morceaux de 256 Ko avec contrôle de `bufferedAmount` ;
  photo de profil recadrée en 256×256 dans un canvas ; reconnexion automatique
  (et au retour sur l'onglet) ; fil reconstruit depuis l'historique à chaque
  bienvenue. CSP stricte (aucun script en ligne) ; les fichiers des membres
  sont servis avec `nosniff` et `sandbox`.
- **Réglages de ce PC** (`desktop/reglages.py`) : thème, dernier nom
  d'utilisateur, photo de profil. Le mot de passe n'est jamais enregistré.
- Protocole complet documenté dans `chat/protocole.py`.

## Interface

Accent bleu `#1877F2`, thème **clair** (fond `#F0F2F5`, cartes blanches à ombre
douce) ou **sombre** (fond `#18191A`, cartes `#242526`), modifiable à chaud dans
les paramètres. Boutons et champs arrondis à 20 px. Messages regroupés par
auteur, avatar à gauche des messages des autres, vos bulles en bleu à droite.
Icônes [Lucide](https://lucide.dev) (licence ISC, `desktop/ressources/icones/`),
logo maison `desktop/ressources/logo.svg`,
police Plus Jakarta Sans (licence OFL, `desktop/ressources/polices/`).

## Structure

```
LocalNet/
├── chat/                   # réseau, sans Qt
│   ├── protocole.py        # format des messages, limites, formats acceptés
│   ├── serveur.py          # salon WebSocket + fichiers/avatars HTTPS + version mobile + mDNS
│   ├── comptes.py          # comptes, mots de passe (scrypt), photos de profil
│   ├── tls.py              # certificat auto-signé, empreinte
│   ├── decouverte.py       # IP locale, recherche mDNS des salons
│   └── web/                # version mobile : index.html, app.js, style.css
└── desktop/                # application PySide6
    ├── app.py              # fenêtre, enchaînement accueil → salon
    ├── accueil.py          # votre IP, connexion / création de compte, salons détectés
    ├── salon.py            # membres, fil (texte, photos, vidéos), saisie
    ├── parametres.py       # photo de profil, thème clair / sombre
    ├── client.py           # connexion, certificat, envoi/téléchargement, photos, salon local
    ├── reglages.py         # réglages de ce PC (QSettings + profil.jpg)
    ├── widgets.py          # fond, cartes, boutons, avatars ronds
    ├── theme.py            # palettes, feuille de style, icônes, logo, police
    └── ressources/         # logo.svg, icones/*.svg, polices/
```

## Limites

- Certificat auto-signé : la première connexion à un salon fait confiance au
  certificat présenté (TOFU). Les navigateurs affichent un avertissement.
  iOS Safari peut refuser le WebSocket malgré l'exception (non testé).
- Les comptes sont liés au PC qui héberge : un autre salon a ses propres comptes.
- Pas encore de changement de mot de passe (supprimer l'entrée dans
  `comptes.json` sur le PC hôte pour réinitialiser un compte).
- Les fichiers ne vivent que le temps du salon (dossier temporaire du serveur),
  dans la limite du quota.
- Si le pare-feu bloque le port 8765, les autres appareils ne pourront pas
  rejoindre le salon.

## Pistes

- Changer son mot de passe depuis les paramètres.
- Lecture des vidéos directement dans le fil de l'application de bureau (QtMultimedia).
- QR code sur l'écran d'accueil de l'hôte pour ouvrir la version mobile.
- Historique persistant (SQLite) et date complète des messages.
- Notifications système, « en train d'écrire… », messages privés.
