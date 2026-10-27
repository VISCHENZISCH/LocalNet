# LocalNet

Discussion et partage de **photos et vidéos** entre les appareils d'un même
réseau local. Rien ne passe par Internet.

Principe : **IP → salon → chat + médias.**

1. Un PC crée un salon (bouton « Créer un salon sur ce PC ») ; son IP s'affiche
   en grand sur l'écran d'accueil.
2. Les autres saisissent cette IP, ou cliquent sur le salon détecté
   automatiquement (annonce mDNS).
3. On discute, on envoie photos et vidéos (trombone ou glisser-déposer).
   Les photos s'affichent dans le fil ; les vidéos s'ouvrent dans le lecteur
   du système. Bouton « Enregistrer » → `~/Téléchargements/LocalNet/`.

## Lancer

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # websockets, zeroconf, PySide6

.venv/bin/python -m desktop.app               # application (sans sudo)
.venv/bin/python -m chat.serveur              # salon seul, sans interface (port 8765)
```

## Fonctionnement

- **Serveur** (`chat/serveur.py`) : WebSocket sur le port 8765, toutes interfaces.
  Relaie les messages, garde un historique des 80 derniers éléments, s'annonce
  en mDNS (`_localnet-chat._tcp`).
- **Fichiers** : envoyés en trames binaires de 256 Ko (8 octets d'identifiant +
  données), écrits dans un dossier temporaire, puis servis en HTTP sur le même
  port (`GET /fichiers/<id>`). Le dossier est supprimé à la fermeture du salon.
  Formats : png, jpg, gif, webp, bmp, mp4, webm, mov, mkv, avi, m4v ; 500 Mo max.
- **Client** (`desktop/client.py`) : QWebSocket ; l'envoi lit le fichier au fur
  et à mesure (jamais entièrement en mémoire) avec barre de progression ;
  les fichiers reçus sont mis en cache dans `~/.cache/LocalNet/fichiers/`.
- Protocole complet documenté dans `chat/protocole.py`.

## Interface

Thème sombre « verre dépoli » : fond uni très sombre, panneaux translucides,
accents verts (`#58855C`, `#9EB8A0`, `#0D3311`) ; boutons et champs arrondis à 20 px.
Icônes [Lucide](https://lucide.dev) (licence ISC, `desktop/ressources/icones/`),
logo maison `desktop/ressources/logo.svg`,
police Plus Jakarta Sans (licence OFL, `desktop/ressources/polices/`).

## Structure

```
LocalNet/
├── chat/                   # réseau, sans Qt
│   ├── protocole.py        # format des messages, limites, formats acceptés
│   ├── serveur.py          # salon WebSocket + fichiers HTTP + annonce mDNS
│   └── decouverte.py       # IP locale, recherche mDNS des salons
└── desktop/                # application PySide6
    ├── app.py              # fenêtre, enchaînement accueil → salon
    ├── accueil.py          # votre IP, rejoindre par IP, salons détectés, créer
    ├── salon.py            # membres, fil (texte, photos, vidéos), saisie
    ├── client.py           # connexion, envoi/téléchargement, serveur local
    ├── widgets.py          # fond uni, panneaux de verre, boutons, avatars
    ├── theme.py            # palette, feuille de style, icônes, logo
    └── ressources/         # logo.svg, icones/*.svg, polices/
```

## Limites

- Pas de chiffrement ni d'authentification : tout est lisible sur le réseau
  local. À n'utiliser que sur un réseau de confiance.
- Les fichiers ne vivent que le temps du salon (dossier temporaire du serveur).
- Si le pare-feu bloque le port 8765, les autres appareils ne pourront pas
  rejoindre le salon.

## Pistes

- Client web servi par le salon, pour rejoindre depuis un téléphone sans rien installer.
- Lecture des vidéos directement dans le fil (QtMultimedia).
