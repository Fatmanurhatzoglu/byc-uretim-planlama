"""DB yazma kancaları — yerel işlem asla senkron hatasına düşmez."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

_tls = threading.local()


@contextmanager
def skip_sync() -> Iterator[None]:
    """Uzak uygulamada outbox'a tekrar yazmayı engeller (döngü kırıcı)."""
    once = getattr(_tls, "skip", 0)
    _tls.skip = once + 1
    try:
        yield
    finally:
        _tls.skip = once


def _aktif() -> bool:
    return getattr(_tls, "skip", 0) <= 0


def siparis_degisti(siparis_id: str) -> None:
    if not _aktif() or not siparis_id:
        return
    try:
        from sync import outbox

        outbox.enqueue("siparis_upsert", str(siparis_id), {"id": str(siparis_id)})
    except Exception:
        pass


def siparis_silindi(siparis_id: str) -> None:
    if not _aktif() or not siparis_id:
        return
    try:
        from sync import outbox

        outbox.enqueue(
            "siparis_delete",
            str(siparis_id),
            {
                "id": str(siparis_id),
                "guncelleme": datetime.now().isoformat(timespec="seconds"),
            },
        )
    except Exception:
        pass


def hareket_eklendi(client_uid: str, siparis_id: str) -> None:
    if not _aktif() or not client_uid:
        return
    try:
        from sync import outbox

        outbox.enqueue(
            "hareket_upsert",
            str(client_uid),
            {"client_uid": str(client_uid), "siparis_id": str(siparis_id)},
        )
        # Durum/guncelleme değişmiş olabilir
        siparis_degisti(siparis_id)
    except Exception:
        pass
