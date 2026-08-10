"""Senkron orkestrasyon: outbox push + Firestore pull (LWW)."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from config import FIREBASE_CREDENTIALS_PATH, FIREBASE_ENABLED
from sync import firestore_client as fs
from sync import outbox
from sync.connectivity import internet_var
from sync.mapper import (
    hareket_to_remote,
    remote_daha_yeni,
    siparis_from_remote,
    siparis_to_remote,
)

_sync_lock = threading.Lock()
_son_calisma: dict[str, Any] = {}


def durum() -> dict[str, Any]:
    o = outbox.durum_ozet()
    return {
        "online": internet_var(),
        "firebase_enabled": bool(FIREBASE_ENABLED),
        "credentials": fs.credentials_var_mi(),
        "hazir": fs.hazir_mi(),
        "init_hata": fs.init_hata(),
        "path": fs.schema_path(),
        "calisiyor": _sync_lock.locked(),
        "bekleyen": o["bekleyen"],
        "hatali": o["hatali"],
        "son_outbox_hata": o["son_outbox_hata"],
        "son_sync": o["son_sync"],
        "son_pull": o["son_pull"],
        "son_hata": o["son_hata"],
        "son_mesaj": o.get("son_mesaj") or _son_calisma.get("son_mesaj", ""),
        "son_seed": o.get("son_seed") or outbox.meta_get("son_seed", ""),
    }


def mevcut_siparisleri_kuyruga_al() -> int:
    """İlk kurulum: tüm yerel sipariş + hareketleri outbox'a yazar."""
    from database import baglanti, tum_siparisler

    n = 0
    for s in tum_siparisler():
        outbox.enqueue("siparis_upsert", str(s["id"]), {"id": s["id"]})
        n += 1
    with baglanti() as conn:
        rows = conn.execute(
            "SELECT client_uid, siparis_id FROM asama_hareket WHERE IFNULL(client_uid,'')!=''"
        ).fetchall()
    for r in rows:
        outbox.enqueue(
            "hareket_upsert",
            str(r["client_uid"]),
            {"client_uid": r["client_uid"], "siparis_id": r["siparis_id"]},
        )
        n += 1
    outbox.meta_set("ilk_kuyruk", datetime.now().isoformat(timespec="seconds"))
    return n


def _push_one(item: dict) -> None:
    tur = item["tur"]
    entity_id = item["entity_id"]
    if tur == "siparis_upsert":
        from database import siparis_getir

        sip = siparis_getir(entity_id)
        if not sip:
            return
        fs.upsert_siparis(entity_id, siparis_to_remote(sip, deleted=False))
    elif tur == "siparis_delete":
        gunc = (item.get("payload") or {}).get("guncelleme") or datetime.now().isoformat(
            timespec="seconds"
        )
        fs.soft_delete_siparis(entity_id, gunc)
    elif tur == "hareket_upsert":
        from database import baglanti

        uid = entity_id
        with baglanti() as conn:
            row = conn.execute(
                """SELECT id, siparis_id, istasyon, tur, adet, neden, not_metin,
                          kullanici, zaman, client_uid
                   FROM asama_hareket WHERE client_uid=?""",
                (uid,),
            ).fetchone()
        if not row:
            return
        h = dict(row)
        h["auto"] = "Otomatik aktarım" in (h.get("not_metin") or "")
        fs.upsert_hareket(str(h["siparis_id"]), str(h["client_uid"]), hareket_to_remote(h))
    else:
        raise ValueError(f"Bilinmeyen outbox türü: {tur}")


def _push_outbox(limit: int = 80) -> dict[str, int]:
    ok = hata = 0
    for item in outbox.listele_bekleyen(limit=limit):
        try:
            _push_one(item)
            outbox.isaretle_ok(int(item["id"]))
            ok += 1
        except Exception as exc:
            outbox.isaretle_hata(int(item["id"]), str(exc))
            hata += 1
    return {"push_ok": ok, "push_hata": hata}


def _uygula_remote_siparis(remote: dict) -> str:
    from database import baglanti, siparis_ekle, siparis_getir, siparis_sil
    from sync.hooks import skip_sync

    sid = str(remote.get("id") or "")
    if not sid:
        return "atlandi"
    if remote.get("deleted"):
        local = siparis_getir(sid)
        if local:
            with skip_sync():
                siparis_sil(sid)
            return "silindi"
        return "atlandi"

    lokal = siparis_getir(sid)
    veri = siparis_from_remote(remote)
    if not lokal:
        with skip_sync():
            siparis_ekle(veri)
        return "eklendi"

    if not remote_daha_yeni(remote.get("guncelleme") or "", lokal.get("guncelleme") or ""):
        return "atlandi"

    with skip_sync():
        from database import _ekle_conn

        veri["olusturma"] = lokal.get("olusturma") or veri.get("olusturma")
        with baglanti() as conn:
            _ekle_conn(conn, veri, yeni_id=sid)
    return "guncellendi"


def _uygula_remote_hareket(h: dict) -> str:
    from database import baglanti, siparis_getir
    from sync.hooks import skip_sync

    uid = str(h.get("client_uid") or "")
    sid = str(h.get("siparis_id") or "")
    if not uid or not sid:
        return "atlandi"
    if not siparis_getir(sid):
        return "atlandi"
    with baglanti() as conn:
        var = conn.execute(
            "SELECT id FROM asama_hareket WHERE client_uid=?", (uid,)
        ).fetchone()
        if var:
            return "atlandi"
    with skip_sync():
        with baglanti() as conn:
            conn.execute(
                """INSERT INTO asama_hareket
                   (siparis_id, istasyon, tur, adet, neden, not_metin, kullanici, zaman, client_uid)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    h.get("istasyon") or "",
                    h.get("tur") or "",
                    int(h.get("adet") or 0),
                    h.get("neden") or "",
                    h.get("not_metin") or "",
                    h.get("kullanici") or "",
                    h.get("zaman") or datetime.now().isoformat(timespec="seconds"),
                    uid,
                ),
            )
    return "eklendi"


def _pull() -> dict[str, int]:
    stats = {"pull_siparis": 0, "pull_hareket": 0, "pull_sil": 0}
    for remote in fs.listele_siparisler():
        sonuc = _uygula_remote_siparis(remote)
        if sonuc in ("eklendi", "guncellendi"):
            stats["pull_siparis"] += 1
        elif sonuc == "silindi":
            stats["pull_sil"] += 1
        sid = str(remote.get("id") or "")
        if not sid or remote.get("deleted"):
            continue
        try:
            hareketler = fs.listele_hareketler(sid)
        except Exception:
            continue
        for h in hareketler:
            if _uygula_remote_hareket(h) == "eklendi":
                stats["pull_hareket"] += 1
    return stats


def sync_now(*, force_queue_all: bool = False) -> dict[str, Any]:
    """Push + pull. İnternet yoksa outbox korunur; bağlantı gelince yazar."""
    global _son_calisma
    if not _sync_lock.acquire(blocking=False):
        return {"ok": False, "mesaj": "Senkron zaten çalışıyor", "online": internet_var()}

    try:
        online = internet_var()
        if not online:
            mesaj = "İnternet yok — yerel kayıtlar korunuyor; bağlantı gelince yazılacak."
            outbox.meta_set("son_mesaj", mesaj)
            _son_calisma = {"son_mesaj": mesaj}
            return {"ok": True, "online": False, "mesaj": mesaj, **outbox.durum_ozet()}

        if not FIREBASE_ENABLED:
            return {"ok": False, "mesaj": "FIREBASE_ENABLED kapalı", "online": True}

        if not fs.credentials_var_mi():
            mesaj = f"Firebase anahtarı yok ({FIREBASE_CREDENTIALS_PATH})"
            outbox.meta_set("son_hata", mesaj)
            return {"ok": False, "mesaj": mesaj, "online": True, "credentials": False}

        if not fs.db():
            mesaj = fs.init_hata() or "Firestore başlatılamadı"
            outbox.meta_set("son_hata", mesaj)
            return {"ok": False, "mesaj": mesaj, "online": True}

        if force_queue_all or not outbox.meta_get("ilk_kuyruk"):
            mevcut_siparisleri_kuyruga_al()

        push = _push_outbox()
        pull = _pull()
        simdi = datetime.now().isoformat(timespec="seconds")
        outbox.meta_set("son_sync", simdi)
        outbox.meta_set("son_pull", simdi)
        outbox.meta_set("son_hata", "")
        mesaj = (
            f"Push {push['push_ok']} ok / {push['push_hata']} hata · "
            f"Pull sipariş {pull['pull_siparis']} · hareket {pull['pull_hareket']}"
        )
        outbox.meta_set("son_mesaj", mesaj)
        _son_calisma = {"son_mesaj": mesaj}
        return {
            "ok": True,
            "online": True,
            "mesaj": mesaj,
            "zaman": simdi,
            **push,
            **pull,
            **outbox.durum_ozet(),
        }
    except Exception as exc:
        hata = str(exc)[:400]
        outbox.meta_set("son_hata", hata)
        return {"ok": False, "mesaj": hata, "online": internet_var()}
    finally:
        _sync_lock.release()
