"""Olay tetiklemeli senkron — sürekli döngü yok.

İstasyon Kaydet/Onayla sonrası `trigger_async` çağrılır.
Manuel /api/sync/now ve Ayarlar butonu da aynı yolu kullanır.
"""

from __future__ import annotations

import threading
from typing import Optional

from config import FIREBASE_ENABLED
from sync.service import sync_now

_lock = threading.Lock()
_timer: Optional[threading.Timer] = None
# Aynı saniyede birden fazla Kaydet → tek senkron (Firestore/SQLite yormasın)
_DEBOUNCE_SEC = 2.0


def trigger_async(neden: str = "istasyon") -> None:
    """Kaydet sonrası arka planda senkron kuyruğa alır (UI beklemez)."""
    if not FIREBASE_ENABLED:
        return

    global _timer
    with _lock:
        if _timer is not None:
            try:
                _timer.cancel()
            except Exception:
                pass

        def _calis():
            try:
                sync_now()
            except Exception:
                pass

        _timer = threading.Timer(_DEBOUNCE_SEC, _calis)
        _timer.daemon = True
        _timer.start()


def baslat() -> None:
    """Eski sürekli worker yok — sadece olay tetiklemeli.

    Geriye dönük: web_app `sync_worker_baslat()` çağırır; artık no-op.
    """
    return


def durdur() -> None:
    global _timer
    with _lock:
        if _timer is not None:
            try:
                _timer.cancel()
            except Exception:
                pass
            _timer = None
