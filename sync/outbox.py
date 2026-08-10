"""Yerel yazma kuyruğu — internet yokken birikir, gelince gönderilir."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from database import baglanti


def enqueue(tur: str, entity_id: str, payload: Optional[dict] = None) -> int:
    """Outbox'a iş ekle. Aynı upsert için bekleyen eski satırı günceller (sıkıştırma)."""
    simdi = datetime.now().isoformat(timespec="seconds")
    body = json.dumps(payload or {}, ensure_ascii=False)
    with baglanti() as conn:
        if tur in ("siparis_upsert", "siparis_delete"):
            conn.execute(
                "DELETE FROM sync_outbox WHERE tur=? AND entity_id=? AND durum='bekliyor'",
                (tur if tur == "siparis_delete" else "siparis_upsert", entity_id),
            )
            # Silme, bekleyen upsert'i geçersiz kılar
            if tur == "siparis_delete":
                conn.execute(
                    "DELETE FROM sync_outbox WHERE tur='siparis_upsert' AND entity_id=? AND durum='bekliyor'",
                    (entity_id,),
                )
            elif tur == "siparis_upsert":
                conn.execute(
                    "DELETE FROM sync_outbox WHERE tur='siparis_delete' AND entity_id=? AND durum='bekliyor'",
                    (entity_id,),
                )
        cur = conn.execute(
            """INSERT INTO sync_outbox (tur, entity_id, payload, durum, deneme, hata, olusturma, guncelleme)
               VALUES (?,?,?,'bekliyor',0,'',?,?)""",
            (tur, entity_id, body, simdi, simdi),
        )
        return int(cur.lastrowid)


def listele_bekleyen(limit: int = 80) -> list[dict]:
    with baglanti() as conn:
        rows = conn.execute(
            """SELECT id, tur, entity_id, payload, durum, deneme, hata, olusturma
               FROM sync_outbox
               WHERE durum='bekliyor'
               ORDER BY id ASC
               LIMIT ?""",
            (max(1, int(limit)),),
        ).fetchall()
    sonuc = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d.get("payload") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["payload"] = {}
        sonuc.append(d)
    return sonuc


def isaretle_ok(outbox_id: int) -> None:
    simdi = datetime.now().isoformat(timespec="seconds")
    with baglanti() as conn:
        conn.execute(
            "UPDATE sync_outbox SET durum='gonderildi', hata='', guncelleme=? WHERE id=?",
            (simdi, outbox_id),
        )


def isaretle_hata(outbox_id: int, hata: str) -> None:
    simdi = datetime.now().isoformat(timespec="seconds")
    with baglanti() as conn:
        conn.execute(
            """UPDATE sync_outbox
               SET deneme=deneme+1, hata=?, guncelleme=?,
                   durum=CASE WHEN deneme+1 >= 25 THEN 'hata' ELSE 'bekliyor' END
               WHERE id=?""",
            ((hata or "")[:500], simdi, outbox_id),
        )


def bekleyen_sayisi() -> int:
    with baglanti() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM sync_outbox WHERE durum='bekliyor'"
            ).fetchone()["c"]
        )


def meta_get(anahtar: str, varsayilan: str = "") -> str:
    with baglanti() as conn:
        row = conn.execute(
            "SELECT deger FROM sync_meta WHERE anahtar=?", (anahtar,)
        ).fetchone()
    return row["deger"] if row else varsayilan


def meta_set(anahtar: str, deger: str) -> None:
    with baglanti() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sync_meta (anahtar, deger) VALUES (?, ?)",
            (anahtar, deger),
        )


def durum_ozet() -> dict[str, Any]:
    with baglanti() as conn:
        bek = conn.execute(
            "SELECT COUNT(*) AS c FROM sync_outbox WHERE durum='bekliyor'"
        ).fetchone()["c"]
        hata = conn.execute(
            "SELECT COUNT(*) AS c FROM sync_outbox WHERE durum='hata'"
        ).fetchone()["c"]
        son_hata = conn.execute(
            """SELECT hata FROM sync_outbox
               WHERE hata!='' ORDER BY guncelleme DESC LIMIT 1"""
        ).fetchone()
    return {
        "bekleyen": int(bek),
        "hatali": int(hata),
        "son_outbox_hata": (son_hata["hata"] if son_hata else "") or "",
        "son_sync": meta_get("son_sync", ""),
        "son_pull": meta_get("son_pull", ""),
        "son_hata": meta_get("son_hata", ""),
        "son_mesaj": meta_get("son_mesaj", ""),
    }
