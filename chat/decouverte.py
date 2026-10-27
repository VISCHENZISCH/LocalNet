"""Trouver les salons du réseau (mDNS) et l'adresse IP de ce PC."""

from __future__ import annotations

import socket
import time
from urllib.parse import urlparse

from .protocole import PORT_DEFAUT, TYPE_SERVICE


def ip_locale() -> str:
    """IP de l'interface qui sort vers le réseau (aucun paquet envoyé)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def decouvrir(duree: float = 2.0) -> list[tuple[str, str]]:
    """Cherche les salons annoncés en mDNS ; renvoie [(nom, url)]."""
    from zeroconf import IPVersion, ServiceBrowser, Zeroconf

    trouves: dict[str, str] = {}

    class Ecouteur:
        def add_service(self, zc, type_, nom):
            info = zc.get_service_info(type_, nom, timeout=1500)
            if info:
                for ip in info.parsed_addresses(IPVersion.V4Only):
                    trouves[nom] = f"ws://{ip}:{info.port}"

        def update_service(self, zc, type_, nom):
            pass

        def remove_service(self, zc, type_, nom):
            pass

    zc = Zeroconf(ip_version=IPVersion.V4Only)
    try:
        ServiceBrowser(zc, TYPE_SERVICE, Ecouteur())
        time.sleep(duree)
    finally:
        zc.close()
    return [(nom.removesuffix("." + TYPE_SERVICE), url) for nom, url in sorted(trouves.items())]


def normaliser(adresse: str) -> str:
    """« 192.168.1.74 » -> « ws://192.168.1.74:8765 »."""
    adresse = adresse.strip()
    if "://" not in adresse:
        adresse = f"ws://{adresse}"
    if urlparse(adresse).port is None:
        adresse = f"{adresse.rstrip('/')}:{PORT_DEFAUT}"
    return adresse
