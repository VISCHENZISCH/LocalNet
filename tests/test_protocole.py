from chat.decouverte import normaliser
from chat.protocole import decoder, genre, nom_sur, taille_lisible


def test_genre():
    assert genre("photo.JPG") == "image"
    assert genre("film.mkv") == "video"
    assert genre("script.html") is None
    assert genre("sans_extension") is None


def test_nom_sur_retire_chemins_et_caracteres_genants():
    assert nom_sur("../../etc/passwd") == "passwd"
    assert nom_sur("C:\\Users\\moi\\photo.png") == "photo.png"
    assert nom_sur("a<b>c.png") == "a_b_c.png"
    assert nom_sur("...") == "fichier"
    assert len(nom_sur("x" * 200 + ".png")) == 80


def test_decoder_ne_leve_jamais():
    assert decoder('{"type": "message"}') == {"type": "message"}
    for brut in ("pas du json", "[1, 2]", '{"type": 3}', b"\xff\xfe", "null"):
        assert decoder(brut) is None


def test_taille_lisible():
    assert taille_lisible(512) == "512 o"
    assert taille_lisible(2048) == "2 Ko"
    assert taille_lisible(3 * 1024**3) == "3.0 Go"


def test_normaliser():
    assert normaliser("192.168.1.42") == "wss://192.168.1.42:8765"
    assert normaliser(" 192.168.1.42:9000 ") == "wss://192.168.1.42:9000"
    assert normaliser("https://192.168.1.42:8765/") == "wss://192.168.1.42:8765"
    assert normaliser("ws://192.168.1.42") == "wss://192.168.1.42:8765"
