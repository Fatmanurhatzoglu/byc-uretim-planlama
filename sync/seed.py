"""Yerel SQLite → Firestore byc/v1 temiz aktarım (seed)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sync import firestore_client as fs
from sync.mapper import hareket_to_remote, siparis_to_remote
from sync import outbox


def seed_tum_veriler(*, yaz_meta: bool = True) -> dict[str, Any]:
    """Tüm sipariş + aşama hareketlerini byc/v1 altına yazar.

    Outbox kullanmaz — doğrudan temiz belge set eder (mobil/web kaynağı).
    """
    from database import baglanti, tum_siparisler

    if not fs.db():
        return {
            "ok": False,
            "mesaj": fs.init_hata() or "Firestore hazır değil",
            "path": fs.schema_path(),
        }

    siparisler = tum_siparisler()
    sip_ok = 0
    har_ok = 0
    hatalar: list[str] = []

    for s in siparisler:
        sid = str(s.get("id") or "")
        if not sid:
            continue
        try:
            fs.upsert_siparis(sid, siparis_to_remote(s, deleted=False))
            sip_ok += 1
        except Exception as exc:
            hatalar.append(f"siparis {sid}: {exc}")
            continue

        with baglanti() as conn:
            rows = conn.execute(
                """SELECT client_uid, siparis_id, istasyon, tur, adet, neden,
                          not_metin, kullanici, zaman
                   FROM asama_hareket WHERE siparis_id=?
                   ORDER BY id ASC""",
                (sid,),
            ).fetchall()
        for r in rows:
            h = dict(r)
            uid = str(h.get("client_uid") or "")
            if not uid:
                continue
            try:
                fs.upsert_hareket(sid, uid, hareket_to_remote(h))
                har_ok += 1
            except Exception as exc:
                hatalar.append(f"hareket {uid}: {exc}")

    if yaz_meta:
        try:
            fs.yaz_meta(siparis_sayisi=sip_ok, hareket_sayisi=har_ok)
        except Exception as exc:
            hatalar.append(f"meta: {exc}")

    simdi = datetime.now().isoformat(timespec="seconds")
    outbox.meta_set("son_seed", simdi)
    outbox.meta_set(
        "son_mesaj",
        f"Seed byc/v1: {sip_ok} sipariş, {har_ok} hareket",
    )
    # Sonraki normal sync ilk_kuyruk atlamasın diye işaretle
    if not outbox.meta_get("ilk_kuyruk"):
        outbox.meta_set("ilk_kuyruk", simdi)

    return {
        "ok": len(hatalar) == 0,
        "path": fs.schema_path(),
        "siparis": sip_ok,
        "hareket": har_ok,
        "hata_sayisi": len(hatalar),
        "hatalar": hatalar[:15],
        "mesaj": (
            f"Firebase {fs.schema_path()} <- {sip_ok} siparis, {har_ok} hareket"
            + (f" ({len(hatalar)} hata)" if hatalar else "")
        ),
        "zaman": simdi,
    }
