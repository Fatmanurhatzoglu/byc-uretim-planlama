"""İnternet erişilebilirlik kontrolü."""

from __future__ import annotations

import socket

from config import FIREBASE_CONNECTIVITY_HOST, FIREBASE_CONNECTIVITY_PORT


def internet_var(timeout: float = 2.5) -> bool:
    """DNS/TLS hedefine TCP denemesi — firewall dostu basit kontrol."""
    try:
        with socket.create_connection(
            (FIREBASE_CONNECTIVITY_HOST, int(FIREBASE_CONNECTIVITY_PORT)),
            timeout=timeout,
        ):
            return True
    except OSError:
        return False
