"""Point d'entrée de l'exécutable autonome (PyInstaller).

    LocalNet                      application
    LocalNet --serveur [options]  salon seul, sans interface (voir chat/serveur.py)
"""

import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serveur":
        from chat.serveur import main as serveur

        sys.exit(serveur(sys.argv[2:]))
    from desktop.app import main

    sys.exit(main())
