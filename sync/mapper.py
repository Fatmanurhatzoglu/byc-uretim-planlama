"""SQLite ↔ Firestore belge eşlemesi (mobil/web uyumlu)."""

from __future__ import annotations

from typing import Any

from config import FIREBASE_SCHEMA_VERSION
from rota_utils import normalize_rota


def siparis_to_remote(sip: dict, *, deleted: bool = False) -> dict[str, Any]:
    """Sipariş → Firestore belgesi (kanonik alanlar + mobil kolaylıkları)."""
    adet = int(sip.get("adet") or 0)
    hazir = int(sip.get("hazir_adet") or 0)
    rota_list = normalize_rota(sip.get("rotalar") or "")
    detay = sip.get("uretim_detay") or {}
    if not isinstance(detay, dict):
        detay = {}
    return {
        "schema_version": FIREBASE_SCHEMA_VERSION,
        "id": str(sip.get("id") or ""),
        "musteri": sip.get("musteri") or "",
        "urun": sip.get("urun") or "",
        "olcu": sip.get("olcu") or "",
        "adet": adet,
        "hazir_adet": hazir,
        "kalan_adet": max(0, adet - hazir),
        "bitis": sip.get("bitis") or "",
        "durum": sip.get("durum") or "Beklemede",
        "oncelik": sip.get("oncelik") or "Normal",
        "rotalar": sip.get("rotalar") or "",
        "rota_listesi": rota_list,
        "istasyon_kapasiteleri": sip.get("istasyon_kapasiteleri") or {},
        "fire_oranlari": sip.get("fire_oranlari") or {},
        "uretim_detay": detay,
        "olusturma": sip.get("olusturma") or "",
        "guncelleme": sip.get("guncelleme") or "",
        "deleted": bool(deleted),
        "source": "fabrika",
    }


def siparis_from_remote(doc: dict[str, Any]) -> dict:
    """Firestore → yerel sipariş dict."""
    return {
        "id": str(doc.get("id") or ""),
        "musteri": doc.get("musteri") or "",
        "urun": doc.get("urun") or "",
        "olcu": doc.get("olcu") or "",
        "adet": str(int(doc.get("adet") or 0)),
        "hazir_adet": str(int(doc.get("hazir_adet") or 0)),
        "bitis": doc.get("bitis") or "",
        "durum": doc.get("durum") or "Beklemede",
        "oncelik": doc.get("oncelik") or "Normal",
        "rotalar": doc.get("rotalar") or (
            ",".join(doc.get("rota_listesi") or []) if doc.get("rota_listesi") else ""
        ),
        "istasyon_kapasiteleri": doc.get("istasyon_kapasiteleri") or {},
        "fire_oranlari": doc.get("fire_oranlari") or {},
        "uretim_detay": doc.get("uretim_detay") or {},
        "olusturma": doc.get("olusturma") or "",
        "guncelleme": doc.get("guncelleme") or "",
        "_sync_apply": True,
    }


def hareket_to_remote(h: dict) -> dict[str, Any]:
    return {
        "schema_version": FIREBASE_SCHEMA_VERSION,
        "client_uid": str(h.get("client_uid") or ""),
        "siparis_id": str(h.get("siparis_id") or ""),
        "istasyon": h.get("istasyon") or "",
        "tur": h.get("tur") or "",
        "adet": int(h.get("adet") or 0),
        "neden": h.get("neden") or "",
        "not_metin": h.get("not_metin") or "",
        "kullanici": h.get("kullanici") or "",
        "zaman": h.get("zaman") or "",
        "auto": bool(h.get("auto") or ("Otomatik aktarım" in (h.get("not_metin") or ""))),
        "source": "fabrika",
    }


def _zaman_karsilastir(a: str, b: str) -> int:
    aa = (a or "").strip()
    bb = (b or "").strip()
    if aa == bb:
        return 0
    return 1 if aa > bb else -1


def remote_daha_yeni(remote_guncelleme: str, local_guncelleme: str) -> bool:
    return _zaman_karsilastir(remote_guncelleme, local_guncelleme) > 0
