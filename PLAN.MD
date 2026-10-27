# LocalNet

Discussion et partage de **photos et vidéos** entre les appareils d'un même
réseau local. Rien ne passe par Internet.

Principe : **compte → IP du salon → chat + médias.**

1. Un PC héberge le salon (bouton vert « Héberger un salon sur ce PC ») ; son IP
   s'affiche en grand sur l'écran d'accueil.
2. Chacun entre son **nom d'utilisateur** et son **mot de passe**
   (onglet « Créer un compte » la première fois, « Se connecter » ensuite),
   puis l'IP du salon — ou clique sur un salon détecté automatiquement (mDNS).
3. On discute, on envoie photos et vidéos (bouton image ou glisser-déposer).
   Les photos s'affichent dans le fil ; les vidéos s'ouvrent dans le lecteur
   du système. Bouton « Enregistrer » → `~/Téléchargements/LocalNet/`.
4. **Paramètres** (roue dentée) : photo de profil, thème clair ou sombre.

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
- **Comptes** (`chat/comptes.py`) : propres à chaque salon, gardés sur le PC qui
  l'héberge dans `~/.local/share/LocalNet/comptes.json` (droits 600). Mots de
  passe hachés avec scrypt + sel ; 1 s d'attente après un échec. Un même compte
  ne peut être connecté qu'une fois.
- **Photos de profil** : recadrées en 256×256 (JPEG) par le client, gardées par
  le serveur dans `avatars/`, servies en `GET /avatars/<id>`. La photo choisie
  sur ce PC fait foi : elle est renvoyée au salon si elle diffère.
- **Fichiers** : envoyés en trames binaires de 256 Ko (8 octets d'identifiant +
  données), écrits dans un dossier temporaire, puis servis en HTTP sur le même
  port (`GET /fichiers/<id>`). Le dossier est supprimé à la fermeture du salon.
  Formats : png, jpg, gif, webp, bmp, mp4, webm, mov, mkv, avi, m4v ; 500 Mo max.
- **Client** (`desktop/client.py`) : QWebSocket ; l'envoi lit le fichier au fur
  et à mesure (jamais entièrement en mémoire) avec barre de progression ;
  les fichiers reçus sont mis en cache dans `~/.cache/LocalNet/fichiers/`.
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
│   ├── serveur.py          # salon WebSocket + fichiers/avatars HTTP + annonce mDNS
│   ├── comptes.py          # comptes, mots de passe (scrypt), photos de profil
│   └── decouverte.py       # IP locale, recherche mDNS des salons
└── desktop/                # application PySide6
    ├── app.py              # fenêtre, enchaînement accueil → salon
    ├── accueil.py          # votre IP, connexion / création de compte, salons détectés
    ├── salon.py            # membres, fil (texte, photos, vidéos), saisie
    ├── parametres.py       # photo de profil, thème clair / sombre
    ├── client.py           # connexion, envoi/téléchargement, photos, serveur local
    ├── reglages.py         # réglages de ce PC (QSettings + profil.jpg)
    ├── widgets.py          # fond, cartes, boutons, avatars ronds
    ├── theme.py            # palettes, feuille de style, icônes, logo, police
    └── ressources/         # logo.svg, icones/*.svg, polices/
```

## Limites

- **Pas de chiffrement** : messages, fichiers et mots de passe circulent en
  clair sur le réseau local. Le mot de passe empêche qu'on prenne votre nom
  dans le salon, mais quelqu'un qui écoute le réseau peut le lire. N'utilisez
  pas un mot de passe qui sert ailleurs, et seulement sur un réseau de confiance.
- Les comptes sont liés au PC qui héberge : un autre salon a ses propres comptes.
- Pas encore de changement de mot de passe (supprimer l'entrée dans
  `comptes.json` sur le PC hôte pour réinitialiser un compte).
- Les fichiers ne vivent que le temps du salon (dossier temporaire du serveur).
- Si le pare-feu bloque le port 8765, les autres appareils ne pourront pas
  rejoindre le salon.

## Pistes

- Chiffrement (WSS avec certificat auto-signé).
- Changer son mot de passe depuis les paramètres.
- Client web servi par le salon, pour rejoindre depuis un téléphone sans rien installer.
- Lecture des vidéos directement dans le fil (QtMultimedia).
