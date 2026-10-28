"""Certificat TLS du salon : auto-signé, créé au premier lancement, gardé ensuite.

    <données>/tls/certificat.pem
    <données>/tls/cle.pem       (droits 600)

Aucune autorité ne le signe : les clients de bureau retiennent son empreinte à
la première connexion (comme SSH) et préviennent si elle change ; les
navigateurs affichent un avertissement à accepter une fois.
"""

from __future__ import annotations

import datetime
import ipaddress
import os
import socket
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

DUREE = datetime.timedelta(days=3650)


def _creer(certificat: Path, cle: Path, ip: str | None) -> None:
    prive = ec.generate_private_key(ec.SECP256R1())
    hote = socket.gethostname()
    nom = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"LocalNet {hote}"[:64])])
    noms: list[x509.GeneralName] = [x509.DNSName(f"{hote}.local"), x509.DNSName("localhost")]
    if ip:
        noms.append(x509.IPAddress(ipaddress.ip_address(ip)))
    maintenant = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nom).issuer_name(nom)
        .public_key(prive.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(maintenant - datetime.timedelta(days=1))
        .not_valid_after(maintenant + DUREE)
        .add_extension(x509.SubjectAlternativeName(noms), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(prive, hashes.SHA256())
    )
    cle.parent.mkdir(parents=True, exist_ok=True)
    descripteur = os.open(cle, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descripteur, "wb") as f:
        f.write(prive.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    certificat.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def fichiers(dossier: Path, ip: str | None = None) -> tuple[Path, Path]:
    """(certificat, clé), créés s'ils n'existent pas encore."""
    certificat, cle = dossier / "tls" / "certificat.pem", dossier / "tls" / "cle.pem"
    if not (certificat.exists() and cle.exists()):
        _creer(certificat, cle, ip)
    return certificat, cle


def empreinte(certificat: Path) -> str:
    """SHA-256 du certificat (DER), en hexadécimal minuscule."""
    cert = x509.load_pem_x509_certificate(certificat.read_bytes())
    return cert.fingerprint(hashes.SHA256()).hex()


def empreinte_lisible(hexa: str) -> str:
    """Les 8 premiers octets, « AB:CD:… », pour comparer à l'œil."""
    return ":".join(hexa[i:i + 2] for i in range(0, 16, 2)).upper()


def contexte(dossier: Path, ip: str | None = None) -> tuple[ssl.SSLContext, str]:
    certificat, cle = fichiers(dossier, ip)
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certificat, cle)
    return ctx, empreinte(certificat)
