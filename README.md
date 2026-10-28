# LocalNet

Application pour discuter et partager des photos et des vidéos entre les
appareils d'un même réseau local (même box, même Wi-Fi). Rien ne passe par
Internet : un PC héberge le salon, les autres PC s'y connectent avec
l'application, les téléphones avec leur navigateur.

## Fonctionnalités

- Salon de discussion hébergé sur un des PC du réseau, sans serveur externe.
- Connexion par adresse IP, ou en un clic sur les salons détectés
  automatiquement sur le réseau.
- **Version mobile** : depuis un téléphone ou une tablette, ouvrez l'adresse
  du salon dans le navigateur. Rien à installer.
- Comptes avec nom d'utilisateur et mot de passe, les mêmes sur PC et mobile.
- Échanges **chiffrés** (TLS).
- Envoi de photos et de vidéos (jusqu'à 500 Mo), par bouton ou par
  glisser-déposer, avec barre de progression.
- Photos affichées dans la discussion, vidéos ouvertes dans le lecteur du
  système (lues directement dans la page sur mobile), enregistrement en un clic.
- Photo de profil visible par les autres membres.
- Thème clair ou sombre.

## Installation

### Exécutable (sans Python)

Les versions publiées sur GitHub (onglet *Releases*) contiennent
`LocalNet-windows.zip` et `LocalNet-linux.tar.gz`. Décompressez l'archive et
lancez `LocalNet` (`LocalNet.exe` sous Windows).

### Depuis les sources

Python 3.11 ou plus récent, Linux (testé) ou Windows.

Linux :

```bash
cd LocalNet
python3 -m venv .venv
.venv/bin/pip install -e .
```

Sur Debian, Ubuntu ou Parrot, si la création du `.venv` échoue :
`sudo apt install python3-venv`.

Windows (PowerShell) :

```powershell
cd LocalNet
py -m venv .venv
.venv\Scripts\pip install -e .
```

Pour copier le projet sur un autre PC, ne copiez pas le dossier `.venv` :
recréez-le sur place avec les commandes ci-dessus.

## Lancement

Linux : `.venv/bin/python -m desktop.app` — Windows : `.venv\Scripts\python -m desktop.app`

Les droits administrateur ne sont pas nécessaires.

## Utilisation

1. **Héberger un salon.** Sur un des PC, remplissez nom d'utilisateur et mot
   de passe, puis cliquez sur « Héberger un salon sur ce PC ». L'adresse IP de
   ce PC est affichée sur l'écran d'accueil : c'est elle que les autres
   utiliseront.
2. **Rejoindre depuis un PC.** Choisissez l'onglet « Créer un compte » la
   première fois (« Se connecter » ensuite), entrez nom d'utilisateur et mot
   de passe, puis l'IP du salon. Vous pouvez aussi cliquer sur le salon s'il
   apparaît dans « Salons détectés ».
3. **Rejoindre depuis un téléphone.** Ouvrez `https://<IP du salon>:8765` dans
   le navigateur, par exemple `https://192.168.1.42:8765`. La première fois,
   le navigateur prévient que la connexion n'est pas sécurisée (voir
   [Sécurité](#sécurité)) : choisissez « Paramètres avancés », puis
   « Continuer vers le site ». Pour retrouver le salon plus vite, utilisez
   « Ajouter à l'écran d'accueil ».
4. **Discuter et partager.** Écrivez dans la zone de saisie. Pour envoyer une
   photo ou une vidéo, utilisez le bouton image (sur téléphone, il ouvre la
   galerie ou l'appareil photo) ou glissez le fichier dans la fenêtre.
5. **Paramètres.** La roue dentée (sur PC) ou votre avatar en haut à gauche
   (sur mobile) permet de choisir sa photo de profil.

Formats acceptés : png, jpg, jpeg, gif, webp, bmp, mp4, webm, mov, mkv, avi, m4v.
Sur mobile, les vidéos mp4, webm, mov et m4v se lisent dans la page ; les mkv
et avi se téléchargent.

### Salon sans interface

Pour héberger un salon sur une machine qui reste allumée, sans ouvrir
l'application :

```bash
.venv/bin/python -m chat.serveur              # port 8765
.venv/bin/python -m chat.serveur --port 9000  # autre port
.venv/bin/python -m chat.serveur --quota 20   # garder jusqu'à 20 Go de fichiers (5 par défaut)
LocalNet --serveur                            # même chose avec l'exécutable
```

## Dépannage

**Les autres appareils n'arrivent pas à se connecter.** Le pare-feu du PC qui
héberge bloque probablement le port 8765.

- Linux avec ufw : `sudo ufw allow 8765/tcp`
- Windows : acceptez la demande du pare-feu au premier lancement du salon, en
  cochant « Réseaux privés ».

**« Certificat du salon modifié ».** L'application retient le certificat de
chaque salon rejoint. S'il change, elle demande confirmation. C'est normal
si le PC hôte a été réinstallé ou si ses données LocalNet ont été effacées.
Comparez l'empreinte affichée avec celle que le salon indique à son lancement
(ligne « certificat AB:CD:… »). Si vous avez un doute, refusez.

**iPhone / iPad : la page s'ouvre mais la connexion échoue.** Safari applique
parfois mal l'exception de certificat aux connexions WebSocket. Essayez de
recharger la page après avoir accepté l'avertissement, ou utilisez un autre
navigateur. *Ce cas n'a pas encore été testé sur un vrai appareil.*

**Le salon n'apparaît pas dans « Salons détectés ».** Certaines box bloquent la
détection automatique. Saisissez l'adresse IP à la main : la connexion
fonctionne quand même.

**Aucun appareil ne se voit.** Sur un Wi-Fi invité ou public, les appareils
sont souvent isolés les uns des autres. Utilisez le réseau principal.

**« Trop d'essais de mot de passe ».** Après 5 mauvais mots de passe en une
minute depuis un même appareil, le salon refuse les connexions de cet
appareil pendant une minute.

**Mot de passe oublié.** Sur le PC qui héberge, supprimez l'entrée du compte
dans `comptes.json` (voir ci-dessous), puis recréez le compte.

## Où sont les données

| Contenu                                                | Emplacement (Linux)                                         |
| ------------------------------------------------------ | ----------------------------------------------------------- |
| Comptes, photos de profil et certificat TLS (PC hôte)  | `~/.local/share/LocalNet/`                                  |
| Votre photo de profil et vos réglages                  | `~/.local/share/LocalNet/profil.jpg`, `~/.config/LocalNet/` |
| Photos et vidéos reçues (cache)                        | `~/.cache/LocalNet/fichiers/`                               |
| Fichiers enregistrés                                   | `~/Téléchargements/LocalNet/`                               |

Sous Windows, ces dossiers se trouvent dans `%APPDATA%` et `%LOCALAPPDATA%`.

Les fichiers partagés dans un salon ne sont conservés par le serveur que tant
que le salon est ouvert, et dans la limite de 5 Go : au-delà, les plus
anciens sont supprimés.

## Sécurité

- Les échanges sont **chiffrés** (TLS) : messages, fichiers et mots de passe
  ne circulent plus en clair sur le réseau.
- Le certificat est créé par le PC hôte au premier lancement, sans autorité
  de certification. C'est pour cela que les navigateurs affichent un
  avertissement la première fois. L'application de bureau retient le
  certificat à la première connexion et prévient s'il change, comme SSH.
  La toute première connexion à un salon reste donc à faire sur un réseau de
  confiance.
- Les mots de passe sont enregistrés hachés (scrypt avec sel) sur le PC qui
  héberge, jamais en clair. Le mot de passe n'est pas mémorisé par
  l'application ni par la page mobile.
- Les essais de mot de passe et les créations de compte sont limités par
  appareil.
- Les comptes appartiennent au salon : un autre PC qui héberge un salon a ses
  propres comptes.

## Développement

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest          # tests
.venv/bin/ruff check .              # style
.venv/bin/mypy                      # types (dossier chat/)
.venv/bin/pyinstaller packaging/localnet.spec   # exécutable dans dist/LocalNet/
```

La CI GitHub Actions lance ces vérifications sous Linux et Windows à chaque
push. Pour une étiquette `v*` (par exemple `git tag v0.3.0 && git push --tags`),
elle construit aussi les exécutables et les joint à la release.

## Structure du projet

```
LocalNet/
├── chat/            serveur, protocole, comptes, TLS, découverte réseau (sans Qt)
│   └── web/         version mobile (HTML/CSS/JS), servie par le salon
├── desktop/         application PySide6 (écrans, thème, widgets)
│   └── ressources/  logo, icônes, police
├── tests/           tests pytest
├── packaging/       lanceur et configuration PyInstaller
├── pyproject.toml
└── PLAN.MD          notes techniques et pistes d'évolution
```

Le format des messages échangés est décrit dans `chat/protocole.py`.

## Crédits

- Icônes : [Lucide](https://lucide.dev), licence ISC
  (`desktop/ressources/icones/LICENSE`).
- Police : [Plus Jakarta Sans](https://github.com/tokotype/PlusJakartaSans),
  licence SIL Open Font License 1.1 (`desktop/ressources/polices/OFL.txt`).
- Bibliothèques : PySide6, aiohttp, cryptography, zeroconf.
