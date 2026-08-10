"""Firestore erişim adaptörü — byc/v1 temiz yol."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from config import (
    APP_VERSION,
    FIREBASE_COLLECTION_HAREKETLER,
    FIREBASE_COLLECTION_SIPARISLER,
    FIREBASE_CREDENTIALS_PATH,
    FIREBASE_ENABLED,
    FIREBASE_PROJECT_ID,
    FIREBASE_ROOT,
    FIREBASE_SCHEMA_VERSION,
)

_lock = threading.Lock()
_app = None
_db = None
_init_hata: str = ""


def hazir_mi() -> bool:
    return FIREBASE_ENABLED and bool(db())


def init_hata() -> str:
    return _init_hata


def credentials_var_mi() -> bool:
    return os.path.isfile(FIREBASE_CREDENTIALS_PATH)


def schema_path() -> str:
    """Mobil/web için kanonik kök: byc/v1"""
    return f"{FIREBASE_ROOT}/{FIREBASE_SCHEMA_VERSION}"


def db():
    """Firestore client; başarısızsa None."""
    global _app, _db, _init_hata
    if not FIREBASE_ENABLED:
        _init_hata = "FIREBASE_ENABLED kapalı"
        return None
    if not credentials_var_mi():
        _init_hata = f"Anahtar yok: {FIREBASE_CREDENTIALS_PATH}"
        return None
    with _lock:
        if _db is not None:
            return _db
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
                opts = {}
                if FIREBASE_PROJECT_ID:
                    opts["projectId"] = FIREBASE_PROJECT_ID
                _app = firebase_admin.initialize_app(cred, opts or None)
            _db = firestore.client()
            _init_hata = ""
            return _db
        except Exception as exc:
            _init_hata = str(exc)[:400]
            _app = None
            _db = None
            return None


def _schema_doc():
    client = db()
    if not client:
        return None
    return client.collection(FIREBASE_ROOT).document(FIREBASE_SCHEMA_VERSION)


def siparis_col():
    base = _schema_doc()
    if not base:
        return None
    return base.collection(FIREBASE_COLLECTION_SIPARISLER)


def hareket_col(siparis_id: str):
    col = siparis_col()
    if not col:
        return None
    return col.document(siparis_id).collection(FIREBASE_COLLECTION_HAREKETLER)


def yaz_meta(*, siparis_sayisi: int = 0, hareket_sayisi: int = 0) -> None:
    """byc/v1 belgesi — mobil istemciler şema keşfi için okur."""
    ref = _schema_doc()
    if not ref:
        raise RuntimeError(init_hata() or "Firestore hazır değil")
    ref.set(
        {
            "schema_version": FIREBASE_SCHEMA_VERSION,
            "root": FIREBASE_ROOT,
            "app": "byc-uretim-planlama",
            "app_version": APP_VERSION,
            "paths": {
                "siparisler": f"{schema_path()}/{FIREBASE_COLLECTION_SIPARISLER}",
                "hareketler": (
                    f"{schema_path()}/{FIREBASE_COLLECTION_SIPARISLER}/{{id}}/"
                    f"{FIREBASE_COLLECTION_HAREKETLER}"
                ),
            },
            "collections": {
                "siparisler": FIREBASE_COLLECTION_SIPARISLER,
                "hareketler": FIREBASE_COLLECTION_HAREKETLER,
            },
            "conflict": "last_write_wins_guncelleme",
            "siparis_sayisi": int(siparis_sayisi),
            "hareket_sayisi": int(hareket_sayisi),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        merge=True,
    )


def upsert_siparis(doc_id: str, data: dict[str, Any]) -> None:
    col = siparis_col()
    if not col:
        raise RuntimeError(init_hata() or "Firestore hazır değil")
    payload = dict(data)
    payload["id"] = doc_id
    payload["schema_version"] = FIREBASE_SCHEMA_VERSION
    col.document(doc_id).set(payload, merge=True)


def soft_delete_siparis(doc_id: str, guncelleme: str) -> None:
    col = siparis_col()
    if not col:
        raise RuntimeError(init_hata() or "Firestore hazır değil")
    col.document(doc_id).set(
        {
            "id": doc_id,
            "deleted": True,
            "guncelleme": guncelleme or "",
            "schema_version": FIREBASE_SCHEMA_VERSION,
        },
        merge=True,
    )


def upsert_hareket(siparis_id: str, client_uid: str, data: dict[str, Any]) -> None:
    col = hareket_col(siparis_id)
    if not col:
        raise RuntimeError(init_hata() or "Firestore hazır değil")
    if not client_uid:
        raise ValueError("client_uid zorunlu")
    payload = dict(data)
    payload["client_uid"] = client_uid
    payload["siparis_id"] = siparis_id
    payload["schema_version"] = FIREBASE_SCHEMA_VERSION
    col.document(client_uid).set(payload, merge=True)


def listele_siparisler() -> list[dict[str, Any]]:
    col = siparis_col()
    if not col:
        raise RuntimeError(init_hata() or "Firestore hazır değil")
    sonuc = []
    for d in col.stream():
        data = d.to_dict() or {}
        data["id"] = data.get("id") or d.id
        sonuc.append(data)
    return sonuc


def listele_hareketler(siparis_id: str) -> list[dict[str, Any]]:
    col = hareket_col(siparis_id)
    if not col:
        raise RuntimeError(init_hata() or "Firestore hazır değil")
    sonuc = []
    for d in col.stream():
        data = d.to_dict() or {}
        data["client_uid"] = data.get("client_uid") or d.id
        data["siparis_id"] = siparis_id
        sonuc.append(data)
    return sonuc


def siparis_getir_remote(doc_id: str) -> Optional[dict[str, Any]]:
    col = siparis_col()
    if not col:
        return None
    snap = col.document(doc_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data["id"] = data.get("id") or snap.id
    return data
