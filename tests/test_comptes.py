import os
import sys

import pytest

from chat.comptes import Comptes, ErreurCompte

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 100


def test_creer_puis_verifier(tmp_path):
    comptes = Comptes(tmp_path)
    assert comptes.creer("Alice", "secret") == "Alice"
    assert comptes.verifier("alice", "secret") == "Alice"  # nom insensible à la casse, nom exact renvoyé
    with pytest.raises(ErreurCompte, match="incorrect"):
        comptes.verifier("alice", "mauvais")
    with pytest.raises(ErreurCompte, match="inconnu"):
        comptes.verifier("bob", "secret")


def test_nom_deja_pris_et_invalide(tmp_path):
    comptes = Comptes(tmp_path)
    comptes.creer("alice", "secret")
    with pytest.raises(ErreurCompte, match="déjà utilisé"):
        comptes.creer("ALICE", "autre")
    with pytest.raises(ErreurCompte):
        comptes.creer("nom avec espaces", "secret")
    with pytest.raises(ErreurCompte):
        comptes.creer("bob", "abc")


def test_verifier_types_inattendus(tmp_path):
    comptes = Comptes(tmp_path)
    comptes.creer("alice", "secret")
    for pseudo, mdp in ((None, "secret"), (42, "secret"), ("alice", None), ("alice", ["secret"])):
        with pytest.raises(ErreurCompte):
            comptes.verifier(pseudo, mdp)


def test_persistance_sans_mot_de_passe_en_clair(tmp_path):
    Comptes(tmp_path).creer("alice", "secret")
    assert "secret" not in (tmp_path / "comptes.json").read_text()
    assert Comptes(tmp_path).verifier("alice", "secret") == "alice"
    if sys.platform != "win32":
        assert os.stat(tmp_path / "comptes.json").st_mode & 0o777 == 0o600


def test_avatar(tmp_path):
    comptes = Comptes(tmp_path)
    comptes.creer("alice", "secret")
    comptes.definir_avatar("alice", PNG)
    id_ = comptes.avatars()["alice"]
    assert comptes.chemin_avatar(id_).read_bytes() == PNG
    assert comptes.chemin_avatar("../comptes.json") is None
    with pytest.raises(ErreurCompte):
        comptes.definir_avatar("alice", b"<html>pas une image</html>")
    comptes.definir_avatar("alice", None)
    assert comptes.avatars() == {}
