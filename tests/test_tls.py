import os
import sys

from chat import tls


def test_certificat_cree_une_fois(tmp_path):
    certificat, cle = tls.fichiers(tmp_path, "192.168.1.42")
    empreinte = tls.empreinte(certificat)
    assert len(empreinte) == 64
    tls.fichiers(tmp_path, "10.0.0.1")  # déjà là : pas recréé, même si l'IP a changé
    assert tls.empreinte(certificat) == empreinte
    if sys.platform != "win32":
        assert os.stat(cle).st_mode & 0o777 == 0o600


def test_contexte(tmp_path):
    contexte, empreinte = tls.contexte(tmp_path)
    assert empreinte == tls.empreinte(tmp_path / "tls" / "certificat.pem")
    assert tls.empreinte_lisible(empreinte).count(":") == 7
