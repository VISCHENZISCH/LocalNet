# LocalNet

Application de bureau pour discuter et partager des photos et des vidéos entre
les ordinateurs d'un même réseau local (même box, même Wi-Fi). Rien ne passe
par Internet : un PC héberge le salon, les autres s'y connectent avec son
adresse IP.

## Fonctionnalités

- Salon de discussion hébergé sur un des PC du réseau, sans serveur externe.
- Connexion par adresse IP, ou en un clic sur les salons détectés
  automatiquement sur le réseau.
- Comptes avec nom d'utilisateur et mot de passe.
- Envoi de photos et de vidéos (jusqu'à 500 Mo), par bouton ou par
  glisser-déposer, avec barre de progression.
- Photos affichées dans la discussion, vidéos ouvertes dans le lecteur du
  système, enregistrement en un clic dans `Téléchargements/LocalNet/`.
- Photo de profil visible par les autres membres.
- Thème clair ou sombre.

## Prérequis

- Python 3.11 ou plus récent
- Linux (testé) ou Windows
- Les ordinateurs doivent être sur le même réseau local

## Installation

Linux :

```bash
cd LocalNet
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Sur Debian, Ubuntu ou Parrot, si la création du `.venv` échoue :
`sudo apt install python3-venv`.

Windows (PowerShell) :

```powershell
cd LocalNet
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Pour copier le projet sur un autre PC, ne copiez pas le dossier `.venv` :
recréez-le sur place avec les commandes ci-dessus.

## Lancement

Linux :

```bash
.venv/bin/python -m desktop.app
```

Windows :

```powershell
.venv\Scripts\python -m desktop.app
```

Les droits administrateur ne sont pas nécessaires.

## Utilisation

1. **Héberger un salon.** Sur un des PC, remplissez nom d'utilisateur et mot
   de passe, puis cliquez sur « Héberger un salon sur ce PC ». L'adresse IP de
   ce PC est affichée sur l'écran d'accueil : c'est elle que les autres
   utiliseront.
2. **Rejoindre le salon.** Sur les autres PC, choisissez l'onglet
   « Créer un compte » la première fois (« Se connecter » ensuite), entrez
   nom d'utilisateur et mot de passe, puis l'IP du salon. Vous pouvez aussi
   cliquer sur le salon s'il apparaît dans « Salons détectés ».
3. **Discuter et partager.** Écrivez dans la zone de saisie. Pour envoyer une
   photo ou une vidéo, cliquez sur le bouton image ou glissez le fichier dans
   la fenêtre.
4. **Paramètres.** La roue dentée (sur l'accueil ou en bas de la barre
   latérale) permet de choisir sa photo de profil et le thème.

Formats acceptés : png, jpg, jpeg, gif, webp, bmp, mp4, webm, mov, mkv, avi, m4v.

### Salon sans interface

Pour héberger un salon sur une machine qui reste allumée, sans ouvrir
l'application :

```bash
.venv/bin/python -m chat.serveur              # port 8765
.venv/bin/python -m chat.serveur --port 9000  # autre port
```

## Dépannage

**Les autres PC n'arrivent pas à se connecter.** Le pare-feu du PC qui héberge
bloque probablement le port 8765.

- Linux avec ufw : `sudo ufw allow 8765/tcp`
- Windows : acceptez la demande du pare-feu au premier lancement du salon, en
  cochant « Réseaux privés ».

**Le salon n'apparaît pas dans « Salons détectés ».** Certaines box bloquent la
détection automatique. Saisissez l'adresse IP à la main : la connexion
fonctionne quand même.

**Aucun appareil ne se voit.** Sur un Wi-Fi invité ou public, les appareils
sont souvent isolés les uns des autres. Utilisez le réseau principal.

**Mot de passe oublié.** Sur le PC qui héberge, supprimez l'entrée du compte
dans `comptes.json` (voir ci-dessous), puis recréez le compte.

## Où sont les données

| Contenu                                        | Emplacement (Linux)                                         |
| ---------------------------------------------- | ----------------------------------------------------------- |
| Comptes du salon et photos de profil (PC hôte) | `~/.local/share/LocalNet/`                                  |
| Votre photo de profil et vos réglages          | `~/.local/share/LocalNet/profil.jpg`, `~/.config/LocalNet/` |
| Photos et vidéos reçues (cache)                | `~/.cache/LocalNet/fichiers/`                               |
| Fichiers enregistrés                           | `~/Téléchargements/LocalNet/`                               |

Sous Windows, ces dossiers se trouvent dans `%APPDATA%` et `%LOCALAPPDATA%`.

Les fichiers partagés dans un salon ne sont conservés par le serveur que tant
que le salon est ouvert.

## Sécurité

- Les échanges ne sont **pas chiffrés** : messages, fichiers et mots de passe
  circulent en clair sur le réseau local. N'utilisez LocalNet que sur un réseau
  de confiance, et choisissez un mot de passe que vous n'utilisez nulle part
  ailleurs.
- Les mots de passe sont enregistrés hachés (scrypt avec sel) sur le PC qui
  héberge, jamais en clair. Le mot de passe n'est pas mémorisé par
  l'application cliente.
- Les comptes appartiennent au salon : un autre PC qui héberge un salon a ses
  propres comptes.

## Structure du projet

```
LocalNet/
├── chat/            serveur, protocole, comptes, découverte réseau (sans Qt)
├── desktop/         application PySide6 (écrans, thème, widgets)
│   └── ressources/  logo, icônes, police
├── requirements.txt
└── PLAN.MD          notes techniques et pistes d'évolution
```

Le format des messages échangés est décrit dans `chat/protocole.py`.

## Crédits

- Icônes : [Lucide](https://lucide.dev), licence ISC
  (`desktop/ressources/icones/LICENSE`).
- Police : [Plus Jakarta Sans](https://github.com/tokotype/PlusJakartaSans),
  licence SIL Open Font License 1.1 (`desktop/ressources/polices/OFL.txt`).
- Bibliothèques : PySide6, websockets, zeroconf.
