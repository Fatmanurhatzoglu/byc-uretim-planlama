"""SQLite veritabanı — çok kullanıcılı erişim için."""

from __future__ import annotations

import json
import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from werkzeug.security import generate_password_hash
from config import (
    BOLUM_KAPASITELERI,
    DATA_FILE,
    DB_FILE,
    SETTINGS_FILE,
    TUM_MAKINELER,
    VARSAYILAN_FIRE_ORANLARI,
    VARSAYILAN_KAPASITELER,
)
from rota_utils import (
    ESKI_RODAJ,
    YENI_RODAJLAR,
    esle_kapasite_anahtarlari,
    kapasiteyi_bol,
    normalize_rota,
    paralel_giris_hedefleri,
    paralel_grubu,
    rota_metni,
)


@contextmanager
def baglanti():
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with baglanti() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS siparisler (
                id TEXT PRIMARY KEY,
                musteri TEXT NOT NULL,
                urun TEXT NOT NULL,
                olcu TEXT DEFAULT '',
                adet INTEGER NOT NULL DEFAULT 0,
                hazir_adet INTEGER NOT NULL DEFAULT 0,
                bitis TEXT NOT NULL,
                durum TEXT NOT NULL DEFAULT 'Beklemede',
                oncelik TEXT NOT NULL DEFAULT 'Normal',
                rotalar TEXT NOT NULL DEFAULT '',
                istasyon_kapasiteleri TEXT NOT NULL DEFAULT '{}',
                olusturma TEXT NOT NULL,
                guncelleme TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ayarlar (
                anahtar TEXT PRIMARY KEY,
                deger TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS kullanicilar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kullanici_adi TEXT UNIQUE NOT NULL,
                sifre_hash TEXT NOT NULL,
                ad TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'ofis',
                olusturma TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS aktivite_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kullanici TEXT NOT NULL,
                islem TEXT NOT NULL,
                detay TEXT,
                hedef_id TEXT,
                zaman TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS makine_takvimi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarih TEXT NOT NULL,
                makine TEXT NOT NULL DEFAULT '*',
                tur TEXT NOT NULL DEFAULT 'tatil',
                aciklama TEXT DEFAULT '',
                olusturma TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bildirimler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tur TEXT NOT NULL,
                baslik TEXT NOT NULL,
                mesaj TEXT NOT NULL,
                okundu INTEGER NOT NULL DEFAULT 0,
                olusturma TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS asama_hareket (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                siparis_id TEXT NOT NULL,
                istasyon TEXT NOT NULL,
                tur TEXT NOT NULL,
                adet INTEGER NOT NULL,
                neden TEXT NOT NULL DEFAULT '',
                not_metin TEXT NOT NULL DEFAULT '',
                kullanici TEXT NOT NULL DEFAULT '',
                zaman TEXT NOT NULL,
                FOREIGN KEY (siparis_id) REFERENCES siparisler(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_asama_siparis ON asama_hareket(siparis_id);
            CREATE INDEX IF NOT EXISTS idx_asama_istasyon ON asama_hareket(siparis_id, istasyon);

            CREATE TABLE IF NOT EXISTS plaka_stok (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cam_turu TEXT NOT NULL DEFAULT 'Düzcam',
                kalinlik REAL NOT NULL DEFAULT 4,
                boy REAL NOT NULL DEFAULT 3210,
                en REAL NOT NULL DEFAULT 2250,
                adet INTEGER NOT NULL DEFAULT 0,
                not_metin TEXT NOT NULL DEFAULT '',
                guncelleme TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plaka_hareket (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stok_id INTEGER,
                tur TEXT NOT NULL,
                adet INTEGER NOT NULL,
                cam_turu TEXT NOT NULL DEFAULT '',
                kalinlik REAL NOT NULL DEFAULT 0,
                boy REAL NOT NULL DEFAULT 0,
                en REAL NOT NULL DEFAULT 0,
                siparis_id TEXT NOT NULL DEFAULT '',
                kullanici TEXT NOT NULL DEFAULT '',
                neden TEXT NOT NULL DEFAULT '',
                geri_alindi INTEGER NOT NULL DEFAULT 0,
                zaman TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_plaka_hareket_zaman ON plaka_hareket(zaman);
            CREATE INDEX IF NOT EXISTS idx_plaka_hareket_sip ON plaka_hareket(siparis_id);

            CREATE TABLE IF NOT EXISTS cizelgeler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zaman TEXT NOT NULL,
                veri TEXT NOT NULL
            );
            """
        )
        # Eski kurulumlara sipariş bazlı fire sütunu ekle
        kolonlar = {r[1] for r in conn.execute("PRAGMA table_info(siparisler)").fetchall()}
        if "fire_oranlari" not in kolonlar:
            conn.execute(
                "ALTER TABLE siparisler ADD COLUMN fire_oranlari TEXT NOT NULL DEFAULT '{}'"
            )
        if "uretim_detay" not in kolonlar:
            conn.execute(
                "ALTER TABLE siparisler ADD COLUMN uretim_detay TEXT NOT NULL DEFAULT '{}'"
            )
        mevcut = conn.execute("SELECT COUNT(*) AS c FROM ayarlar").fetchone()["c"]
        if mevcut == 0:
            conn.execute(
                "INSERT INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                ("varsayilan_kapasiteler", json.dumps(VARSAYILAN_KAPASITELER, ensure_ascii=False)),
            )

        k_sayi = conn.execute("SELECT COUNT(*) AS c FROM kullanicilar").fetchone()["c"]
        if k_sayi == 0:
            simdi = datetime.now().isoformat(timespec="seconds")
            varsayilan = [
                ("admin", "Yönetici", "admin", "admin123"),
                ("ofis", "Ofis Kullanıcı", "ofis", "ofis123"),
                ("saha", "Saha Tablet", "saha", "saha123"),
            ]
            for ka, ad, rol, sf in varsayilan:
                conn.execute(
                    "INSERT INTO kullanicilar (kullanici_adi, sifre_hash, ad, rol, olusturma) VALUES (?,?,?,?,?)",
                    (ka, generate_password_hash(sf), ad, rol, simdi),
                )

    _json_dan_tasi()
    _rodaj_cift_makine_migrate()


def _rodaj_cift_makine_migrate() -> None:
    """Eski tekil 'Rodaj' → Rodaj 1 / Rodaj 2 (sipariş, ayar, aşama hareket).

    Siparişleri silmez; yalnızca anahtar/rota metnini günceller.
    """
    with baglanti() as conn:
        # Ayarlar: kapasite + fire
        for anahtar, varsayilan in (
            ("varsayilan_kapasiteler", VARSAYILAN_KAPASITELER),
            ("fire_oranlari", VARSAYILAN_FIRE_ORANLARI),
        ):
            row = conn.execute(
                "SELECT deger FROM ayarlar WHERE anahtar=?", (anahtar,)
            ).fetchone()
            if not row:
                # Fire için yoksa varsayılanı yaz (eksik kurulum)
                if anahtar == "fire_oranlari":
                    conn.execute(
                        "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                        (anahtar, json.dumps(dict(varsayilan), ensure_ascii=False)),
                    )
                continue
            try:
                data = json.loads(row["deger"] or "{}")
            except (json.JSONDecodeError, TypeError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            yeni = esle_kapasite_anahtarlari(data)
            # Eksik yeni makineleri varsayılandan tamamla
            for m in TUM_MAKINELER:
                if m not in yeni and m in varsayilan:
                    yeni[m] = varsayilan[m]
            if yeni != data:
                conn.execute(
                    "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                    (anahtar, json.dumps(yeni, ensure_ascii=False)),
                )

        # Siparişler: rota + kapasite + fire anahtarları
        for row in conn.execute(
            "SELECT id, rotalar, istasyon_kapasiteleri, fire_oranlari FROM siparisler"
        ).fetchall():
            eski_rota = row["rotalar"] or ""
            yeni_tokens = normalize_rota(eski_rota)
            yeni_rota = rota_metni(yeni_tokens)

            try:
                kap = json.loads(row["istasyon_kapasiteleri"] or "{}")
            except (json.JSONDecodeError, TypeError):
                kap = {}
            try:
                fire = json.loads(row["fire_oranlari"] or "{}")
            except (json.JSONDecodeError, TypeError):
                fire = {}
            yeni_kap = esle_kapasite_anahtarlari(kap if isinstance(kap, dict) else {})
            yeni_fire = esle_kapasite_anahtarlari(fire if isinstance(fire, dict) else {})

            if (
                yeni_rota != eski_rota
                or yeni_kap != kap
                or yeni_fire != fire
            ):
                conn.execute(
                    """UPDATE siparisler
                       SET rotalar=?, istasyon_kapasiteleri=?, fire_oranlari=?
                       WHERE id=?""",
                    (
                        yeni_rota,
                        json.dumps(yeni_kap, ensure_ascii=False),
                        json.dumps(yeni_fire, ensure_ascii=False),
                        row["id"],
                    ),
                )

        # Aşama hareket: istasyon='Rodaj' → 'Rodaj 1' (stok sürekliliği)
        conn.execute(
            "UPDATE asama_hareket SET istasyon=? WHERE istasyon=?",
            (YENI_RODAJLAR[0], ESKI_RODAJ),
        )


# ── JSON taşıma ──────────────────────────────────────────────

def _json_dan_tasi() -> None:
    with baglanti() as conn:
        sayi = conn.execute("SELECT COUNT(*) AS c FROM siparisler").fetchone()["c"]
        if sayi > 0:
            return
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    for sip in json.load(f):
                        _ekle_conn(conn, sip, yeni_id=sip.get("id"))
            except (json.JSONDecodeError, OSError):
                pass
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    ayar = json.load(f)
                if "varsayilan_kapasiteler" in ayar:
                    conn.execute(
                        "UPDATE ayarlar SET deger=? WHERE anahtar=?",
                        (json.dumps(ayar["varsayilan_kapasiteler"], ensure_ascii=False), "varsayilan_kapasiteler"),
                    )
            except (json.JSONDecodeError, OSError):
                pass


# ── Siparişler ───────────────────────────────────────────────

def _satir_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["istasyon_kapasiteleri"] = json.loads(d.get("istasyon_kapasiteleri") or "{}")
    d["fire_oranlari"] = json.loads(d.get("fire_oranlari") or "{}")
    d["uretim_detay"] = json.loads(d.get("uretim_detay") or "{}") if d.get("uretim_detay") is not None else {}
    d["adet"] = str(d["adet"])
    d["hazir_adet"] = str(d["hazir_adet"])
    return d


def _ekle_conn(conn, veri: dict, yeni_id: Optional[str] = None) -> str:
    simdi = datetime.now().isoformat(timespec="seconds")
    sid = yeni_id or (datetime.now().strftime("%d%m%Y%H%M%S") + str(random.randint(100, 999)))
    kap = veri.get("istasyon_kapasiteleri", {})
    if isinstance(kap, str):
        kap = json.loads(kap or "{}")
    fire = veri.get("fire_oranlari", {})
    if isinstance(fire, str):
        fire = json.loads(fire or "{}")
    detay = veri.get("uretim_detay", {})
    if isinstance(detay, str):
        detay = json.loads(detay or "{}")
    kap = esle_kapasite_anahtarlari(kap if isinstance(kap, dict) else {})
    fire = esle_kapasite_anahtarlari(fire if isinstance(fire, dict) else {})
    rotalar = rota_metni(normalize_rota(veri.get("rotalar", "")))
    # Ölçü alanlarından olcu metnini senkronize et
    olcu = veri.get("olcu", "")
    if not olcu and (detay.get("boy") or detay.get("en")):
        parcalar = [str(detay.get("boy") or "").strip(), str(detay.get("en") or "").strip()]
        if detay.get("kalinlik"):
            parcalar.append(str(detay.get("kalinlik")).strip())
        olcu = "x".join(p for p in parcalar if p)
    conn.execute(
        """INSERT OR REPLACE INTO siparisler
        (id,musteri,urun,olcu,adet,hazir_adet,bitis,durum,oncelik,rotalar,
         istasyon_kapasiteleri,fire_oranlari,uretim_detay,olusturma,guncelleme)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sid, veri.get("musteri",""), str(veri.get("urun","")).upper(), olcu,
         int(veri.get("adet",0)), int(veri.get("hazir_adet",0)),
         veri.get("bitis", datetime.now().strftime("%d.%m.%Y")),
         veri.get("durum","Beklemede"), veri.get("oncelik","Normal"),
         rotalar,
         json.dumps(kap, ensure_ascii=False),
         json.dumps(fire, ensure_ascii=False),
         json.dumps(detay, ensure_ascii=False),
         veri.get("olusturma", simdi), simdi),
    )
    return sid


def tum_siparisler() -> list[dict]:
    with baglanti() as conn:
        rows = conn.execute("SELECT * FROM siparisler ORDER BY guncelleme DESC").fetchall()
    return [_satir_to_dict(r) for r in rows]


def siparis_getir(siparis_id: str) -> Optional[dict]:
    with baglanti() as conn:
        row = conn.execute("SELECT * FROM siparisler WHERE id=?", (siparis_id,)).fetchone()
    return _satir_to_dict(row) if row else None


def siparis_ekle(veri: dict) -> dict:
    with baglanti() as conn:
        sid = _ekle_conn(conn, veri)
        row = conn.execute("SELECT * FROM siparisler WHERE id=?", (sid,)).fetchone()
    return _satir_to_dict(row)


def siparis_guncelle(siparis_id: str, veri: dict) -> Optional[dict]:
    mevcut = siparis_getir(siparis_id)
    if not mevcut:
        return None
    veri["olusturma"] = mevcut.get("olusturma", datetime.now().isoformat(timespec="seconds"))
    with baglanti() as conn:
        _ekle_conn(conn, veri, yeni_id=siparis_id)
        row = conn.execute("SELECT * FROM siparisler WHERE id=?", (siparis_id,)).fetchone()
    return _satir_to_dict(row)


def siparis_sil(siparis_id: str) -> bool:
    with baglanti() as conn:
        conn.execute("DELETE FROM asama_hareket WHERE siparis_id=?", (siparis_id,))
        cur = conn.execute("DELETE FROM siparisler WHERE id=?", (siparis_id,))
    return cur.rowcount > 0


def tumunu_sil() -> None:
    with baglanti() as conn:
        conn.execute("DELETE FROM asama_hareket")
        conn.execute("DELETE FROM siparisler")


def parcali_sevk(siparis_id: str, adet: int) -> Optional[dict]:
    sip = siparis_getir(siparis_id)
    if not sip:
        return None
    toplam = int(sip["adet"])
    mevcut = int(sip["hazir_adet"])
    kalan = max(0, toplam - mevcut)
    if adet <= 0 or adet > kalan:
        raise ValueError(f"En fazla {kalan} adet sevk edilebilir.")
    yeni = mevcut + adet
    sip["hazir_adet"] = str(yeni)
    sip["durum"] = "Tamamlandı" if yeni >= toplam else "Üretimde"
    return siparis_guncelle(siparis_id, sip)


def _rota_listesi(sip: dict) -> list[str]:
    """Rota tokenleri; eski 'Rodaj' okuma anında Rodaj 1+2'ye genişler."""
    return normalize_rota(sip.get("rotalar") or "")


def asama_ozet(siparis_id: str, hareket_limit: int = 15) -> Optional[dict]:
    """Siparişin her istasyon için gelen/çıkan/fire/stok + son hareketler."""
    sip = siparis_getir(siparis_id)
    if not sip:
        return None
    rotalar = _rota_listesi(sip)
    with baglanti() as conn:
        rows = conn.execute(
            """SELECT istasyon, tur, SUM(adet) AS toplam
               FROM asama_hareket WHERE siparis_id=?
               GROUP BY istasyon, tur""",
            (siparis_id,),
        ).fetchall()
        hareketler = conn.execute(
            """SELECT id, istasyon, tur, adet, neden, not_metin, kullanici, zaman
               FROM asama_hareket WHERE siparis_id=?
               ORDER BY id DESC LIMIT ?""",
            (siparis_id, max(0, int(hareket_limit))),
        ).fetchall() if hareket_limit else []

    return _asama_ozet_hesapla(sip, rotalar, rows, hareketler)


def _asama_ozet_hesapla(sip: dict, rotalar: list[str], rows, hareketler=None) -> dict:
    agg: dict[str, dict] = {}
    for r in rows:
        st = agg.setdefault(r["istasyon"], {"gelen": 0, "cikan": 0, "fire": 0})
        if r["tur"] == "giris":
            st["gelen"] = int(r["toplam"] or 0)
        elif r["tur"] == "cikis":
            st["cikan"] = int(r["toplam"] or 0)
        elif r["tur"] == "fire":
            st["fire"] = int(r["toplam"] or 0)

    asamalar = []
    aktif_idx = None
    for i, ist in enumerate(rotalar):
        st = agg.get(ist, {"gelen": 0, "cikan": 0, "fire": 0})
        gelen = int(st["gelen"])
        cikan = int(st["cikan"])
        fire = int(st["fire"])
        stok = max(0, gelen - cikan - fire)
        item = {
            "istasyon": ist,
            "sira": i + 1,
            "gelen": gelen,
            "cikan": cikan,
            "fire": fire,
            "stok": stok,
        }
        asamalar.append(item)
        if stok > 0 and aktif_idx is None:
            aktif_idx = i

    if aktif_idx is None:
        if not any(a["gelen"] > 0 for a in asamalar):
            aktif_istasyon = "Başlamadı"
            aktif_stok = 0
        else:
            aktif_istasyon = "Sevk bekliyor" if asamalar else "Başlamadı"
            aktif_stok = 0
            for a in reversed(asamalar):
                if a["cikan"] > 0 or a["gelen"] > 0:
                    if a["stok"] == 0 and a["sira"] == len(asamalar):
                        aktif_istasyon = "Sevk bekliyor"
                    elif a["stok"] == 0:
                        nxt = asamalar[a["sira"]] if a["sira"] < len(asamalar) else None
                        if nxt and nxt["gelen"] > 0:
                            aktif_istasyon = nxt["istasyon"]
                            aktif_stok = nxt["stok"]
                        else:
                            aktif_istasyon = a["istasyon"]
                            aktif_stok = 0
                    break
    else:
        aktif_istasyon = asamalar[aktif_idx]["istasyon"]
        aktif_stok = asamalar[aktif_idx]["stok"]

    return {
        "siparis_id": str(sip.get("id", "")),
        "musteri": sip.get("musteri", ""),
        "urun": sip.get("urun", ""),
        "adet": int(sip.get("adet") or 0),
        "hazir_adet": int(sip.get("hazir_adet") or 0),
        "durum": sip.get("durum", ""),
        "rotalar": rotalar,
        "asamalar": asamalar,
        "aktif_istasyon": aktif_istasyon,
        "aktif_stok": aktif_stok,
        "hareketler": [dict(h) for h in (hareketler or [])],
    }


def asama_hareket_ekle(
    siparis_id: str,
    istasyon: str,
    tur: str,
    adet: int,
    neden: str = "",
    not_metin: str = "",
    kullanici: str = "",
    sonraki_aktar: bool = True,
) -> dict:
    """giris / cikis / fire kaydı. cikis'ta sonraki_aktar=True ise sonraki istasyona giriş yazar."""
    if tur not in ("giris", "cikis", "fire"):
        raise ValueError("Tür giris, cikis veya fire olmalı.")
    adet = int(adet)
    if adet <= 0:
        raise ValueError("Adet 1 veya daha büyük olmalı.")

    sip = siparis_getir(siparis_id)
    if not sip:
        raise ValueError("Sipariş bulunamadı.")

    rotalar = _rota_listesi(sip)
    if istasyon not in rotalar:
        raise ValueError(f"'{istasyon}' bu siparişin rotasında yok.")

    ozet = asama_ozet(siparis_id)
    ist_map = {a["istasyon"]: a for a in (ozet or {}).get("asamalar", [])}
    mevcut = ist_map.get(istasyon, {"gelen": 0, "cikan": 0, "fire": 0, "stok": 0})

    if tur in ("cikis", "fire"):
        if adet > mevcut["stok"]:
            raise ValueError(
                f"{istasyon} stokunda {mevcut['stok']} adet var; {adet} adet {tur} yapılamaz."
            )
    if tur == "fire" and not (neden or "").strip():
        raise ValueError("Fire için neden seçilmeli.")

    uyari = asama_sira_uyarisi(ozet, istasyon, tur)

    simdi = datetime.now().isoformat(timespec="seconds")
    with baglanti() as conn:
        conn.execute(
            """INSERT INTO asama_hareket
               (siparis_id, istasyon, tur, adet, neden, not_metin, kullanici, zaman)
               VALUES (?,?,?,?,?,?,?,?)""",
            (siparis_id, istasyon, tur, adet, neden.strip(), not_metin.strip(), kullanici, simdi),
        )
        if tur == "cikis" and sonraki_aktar:
            # Paralel Rodaj 1/2: kardeşe aktarma; gruba girişte adedi böl
            hedefler = paralel_giris_hedefleri(rotalar, istasyon)
            if len(hedefler) > 1:
                paylar = kapasiteyi_bol(adet, [1] * len(hedefler))
                for hedef, pay in zip(hedefler, paylar):
                    if pay <= 0:
                        continue
                    conn.execute(
                        """INSERT INTO asama_hareket
                           (siparis_id, istasyon, tur, adet, neden, not_metin, kullanici, zaman)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            siparis_id,
                            hedef,
                            "giris",
                            pay,
                            "",
                            f"Otomatik aktarım ← {istasyon} (paralel)",
                            kullanici,
                            simdi,
                        ),
                    )
            elif len(hedefler) == 1:
                conn.execute(
                    """INSERT INTO asama_hareket
                       (siparis_id, istasyon, tur, adet, neden, not_metin, kullanici, zaman)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        siparis_id,
                        hedefler[0],
                        "giris",
                        adet,
                        "",
                        f"Otomatik aktarım ← {istasyon}",
                        kullanici,
                        simdi,
                    ),
                )

        # Durumu Üretimde yap (sevk tamamlanmış değilse)
        if sip.get("durum") in ("Beklemede",):
            conn.execute(
                "UPDATE siparisler SET durum=?, guncelleme=? WHERE id=?",
                ("Üretimde", simdi, siparis_id),
            )

    sonuc = asama_ozet(siparis_id)
    if sonuc is not None:
        sonuc["uyari"] = uyari
    return sonuc


def asama_sira_uyarisi(ozet: Optional[dict], istasyon: str, tur: str) -> str:
    """Sıra bozulursa uyarı metni (işlemi engellemez)."""
    if not ozet:
        return ""
    rotalar = ozet.get("rotalar") or []
    asamalar = ozet.get("asamalar") or []
    if istasyon not in rotalar:
        return ""
    idx = rotalar.index(istasyon)
    grup = paralel_grubu(istasyon) or frozenset()
    uyarilar = []
    for a in asamalar[:idx]:
        # Paralel kardeş (Rodaj 1 ↔ Rodaj 2) sıra uyarısı üretmesin
        if a["istasyon"] in grup:
            continue
        if a["gelen"] == 0:
            uyarilar.append(f"Önceki '{a['istasyon']}' henüz başlamadı")
        elif a["stok"] > 0:
            uyarilar.append(f"'{a['istasyon']}' içinde hâlâ {a['stok']} adet stok var")
    if tur == "giris" and idx == 0 and ozet.get("aktif_istasyon") not in ("Başlamadı", istasyon):
        pass
    return " · ".join(uyarilar)


def istasyon_siparisleri(makine: str) -> list[dict]:
    """Bu makine rotasında olan, tamamlanmamış siparişler + aşama özeti (toplu sorgu)."""
    makine = (makine or "").strip()
    siparisler = [s for s in tum_siparisler() if s.get("durum") != "Tamamlandı"]
    if makine:
        siparisler = [s for s in siparisler if makine in _rota_listesi(s)]
    ozler = asama_ozetleri_toplu([s["id"] for s in siparisler])
    sonuc = []
    for s in siparisler:
        o = ozler.get(s["id"]) or {}
        ist = next((a for a in o.get("asamalar", []) if a["istasyon"] == makine), None)
        sonuc.append({
            "id": s["id"],
            "musteri": s.get("musteri", ""),
            "urun": s.get("urun", ""),
            "olcu": s.get("olcu", ""),
            "adet": s.get("adet"),
            "hazir_adet": s.get("hazir_adet"),
            "durum": s.get("durum"),
            "rotalar": s.get("rotalar", ""),
            "aktif_istasyon": o.get("aktif_istasyon", "Başlamadı"),
            "aktif_stok": o.get("aktif_stok", 0),
            "istasyon_stok": (ist or {}).get("stok", 0),
            "istasyon_gelen": (ist or {}).get("gelen", 0),
            "istasyon_cikan": (ist or {}).get("cikan", 0),
            "istasyon_fire": (ist or {}).get("fire", 0),
        })
    return sonuc


def asama_ozetleri_toplu(siparis_ids: list[str]) -> dict[str, dict]:
    """Liste için hızlı özet — tek sorguda tüm hareketler."""
    if not siparis_ids:
        return {}
    ids = [str(x) for x in siparis_ids]
    placeholders = ",".join("?" * len(ids))
    with baglanti() as conn:
        sip_rows = conn.execute(
            f"SELECT * FROM siparisler WHERE id IN ({placeholders})", ids
        ).fetchall()
        mov_rows = conn.execute(
            f"""SELECT siparis_id, istasyon, tur, SUM(adet) AS toplam
                FROM asama_hareket WHERE siparis_id IN ({placeholders})
                GROUP BY siparis_id, istasyon, tur""",
            ids,
        ).fetchall()

    by_sip: dict[str, list] = {i: [] for i in ids}
    for r in mov_rows:
        by_sip.setdefault(str(r["siparis_id"]), []).append(r)

    out: dict[str, dict] = {}
    for row in sip_rows:
        sip = _satir_to_dict(row)
        sid = str(sip["id"])
        o = _asama_ozet_hesapla(sip, _rota_listesi(sip), by_sip.get(sid, []), [])
        out[sid] = {
            "aktif_istasyon": o["aktif_istasyon"],
            "aktif_stok": o["aktif_stok"],
            "asamalar": o["asamalar"],
        }
    # ID listesinde olup DB'de bulunamayanlar
    for sid in ids:
        out.setdefault(sid, {"aktif_istasyon": "Başlamadı", "aktif_stok": 0, "asamalar": []})
    return out


# ── Çizelge (son plan sonucu) ────────────────────────────────

def cizelge_kaydet(veri: dict) -> None:
    """Başarılı çizelgeleme sonucunu saklar; son 10 kaydı tutar."""
    simdi = datetime.now().isoformat(timespec="seconds")
    with baglanti() as conn:
        conn.execute(
            "INSERT INTO cizelgeler (zaman, veri) VALUES (?, ?)",
            (simdi, json.dumps(veri, ensure_ascii=False)),
        )
        keep = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM cizelgeler ORDER BY id DESC LIMIT 10"
            ).fetchall()
        ]
        if keep:
            placeholders = ",".join("?" * len(keep))
            conn.execute(
                f"DELETE FROM cizelgeler WHERE id NOT IN ({placeholders})",
                keep,
            )


def cizelge_son_getir() -> Optional[dict]:
    """En son çizelge JSON'unu döndürür; yoksa None."""
    with baglanti() as conn:
        row = conn.execute(
            "SELECT veri FROM cizelgeler ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["veri"])
    except (json.JSONDecodeError, TypeError):
        return None


# ── Ayarlar ──────────────────────────────────────────────────

def ayarlari_getir() -> dict:
    with baglanti() as conn:
        row = conn.execute("SELECT deger FROM ayarlar WHERE anahtar='varsayilan_kapasiteler'").fetchone()
        row_b = conn.execute("SELECT deger FROM ayarlar WHERE anahtar='bolum_kapasiteleri'").fetchone()
        row_f = conn.execute("SELECT deger FROM ayarlar WHERE anahtar='fire_oranlari'").fetchone()
    kap = json.loads(row["deger"]) if row else dict(VARSAYILAN_KAPASITELER)
    bolum = json.loads(row_b["deger"]) if row_b else dict(BOLUM_KAPASITELERI)
    fire = json.loads(row_f["deger"]) if row_f else dict(VARSAYILAN_FIRE_ORANLARI)
    kap = esle_kapasite_anahtarlari(kap if isinstance(kap, dict) else {})
    fire = esle_kapasite_anahtarlari(fire if isinstance(fire, dict) else {})
    for m in TUM_MAKINELER:
        if m not in kap:
            kap[m] = VARSAYILAN_KAPASITELER.get(m, 500)
        if m not in fire:
            fire[m] = VARSAYILAN_FIRE_ORANLARI.get(m, 0)
    return {
        "varsayilan_kapasiteler": kap,
        "bolum_kapasiteleri": bolum,
        "fire_oranlari": fire,
    }


def ayarlari_kaydet(ayarlar: dict) -> dict:
    with baglanti() as conn:
        if "varsayilan_kapasiteler" in ayarlar:
            conn.execute(
                "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                ("varsayilan_kapasiteler", json.dumps(ayarlar["varsayilan_kapasiteler"], ensure_ascii=False)),
            )
        if "bolum_kapasiteleri" in ayarlar:
            conn.execute(
                "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                ("bolum_kapasiteleri", json.dumps(ayarlar["bolum_kapasiteleri"], ensure_ascii=False)),
            )
        if "fire_oranlari" in ayarlar:
            conn.execute(
                "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                ("fire_oranlari", json.dumps(ayarlar["fire_oranlari"], ensure_ascii=False)),
            )
    return ayarlari_getir()


def kpi_ozet() -> dict:
    siparisler = tum_siparisler()
    kalan = sum(max(0, int(s["adet"]) - int(s["hazir_adet"])) for s in siparisler if s.get("durum") != "Tamamlandı")
    po = plaka_ozet()
    return {
        "toplam": len(siparisler),
        "uretimde": sum(1 for s in siparisler if s.get("durum") == "Üretimde"),
        "tamamlanan": sum(1 for s in siparisler if s.get("durum") == "Tamamlandı"),
        "acil": sum(1 for s in siparisler if s.get("oncelik") == "Acil" and s.get("durum") != "Tamamlandı"),
        "kalan_adet": kalan,
        "aktif": sum(1 for s in siparisler if s.get("durum") in ("Beklemede", "Üretimde")),
        "plaka_toplam": po.get("toplam_adet", 0),
        "plaka_dusuk_adet": po.get("dusuk_adet", 0),
        "plaka_dusuk": po.get("dusuk_stok", []),
        "plaka_uyari_esik": po.get("uyari_esik", 10),
    }


# ── Kullanıcılar ─────────────────────────────────────────────

def kullanici_getir(uid: int) -> Optional[dict]:
    with baglanti() as conn:
        row = conn.execute("SELECT id,kullanici_adi,ad,rol,olusturma FROM kullanicilar WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def kullanici_kullanici_adi_ile(ka: str) -> Optional[dict]:
    with baglanti() as conn:
        row = conn.execute("SELECT * FROM kullanicilar WHERE kullanici_adi=?", (ka,)).fetchone()
    return dict(row) if row else None


def tum_kullanicilar() -> list[dict]:
    with baglanti() as conn:
        rows = conn.execute("SELECT id,kullanici_adi,ad,rol,olusturma FROM kullanicilar ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def kullanici_sifre_degistir(uid: int, yeni_sifre: str) -> None:
    with baglanti() as conn:
        conn.execute("UPDATE kullanicilar SET sifre_hash=? WHERE id=?", (generate_password_hash(yeni_sifre), uid))


# ── Aktivite log ─────────────────────────────────────────────

def log_ekle(kullanici: str, islem: str, detay: str = "", hedef_id: str = "") -> None:
    with baglanti() as conn:
        conn.execute(
            "INSERT INTO aktivite_log (kullanici,islem,detay,hedef_id,zaman) VALUES (?,?,?,?,?)",
            (kullanici, islem, detay, hedef_id, datetime.now().isoformat(timespec="seconds")),
        )


def log_listele(limit: int = 100) -> list[dict]:
    with baglanti() as conn:
        rows = conn.execute(
            "SELECT * FROM aktivite_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Bildirimler ──────────────────────────────────────────────

def bildirim_ekle(tur: str, baslik: str, mesaj: str) -> None:
    with baglanti() as conn:
        conn.execute(
            "INSERT INTO bildirimler (tur,baslik,mesaj,okundu,olusturma) VALUES (?,?,?,0,?)",
            (tur, baslik, mesaj, datetime.now().isoformat(timespec="seconds")),
        )


def bildirimler_listele(okunmamis_only: bool = False) -> list[dict]:
    with baglanti() as conn:
        if okunmamis_only:
            rows = conn.execute("SELECT * FROM bildirimler WHERE okundu=0 ORDER BY id DESC LIMIT 50").fetchall()
        else:
            rows = conn.execute("SELECT * FROM bildirimler ORDER BY id DESC LIMIT 50").fetchall()
    return [dict(r) for r in rows]


def bildirim_okundu(bid: int) -> None:
    with baglanti() as conn:
        conn.execute("UPDATE bildirimler SET okundu=1 WHERE id=?", (bid,))


def bildirim_tumunu_oku() -> None:
    with baglanti() as conn:
        conn.execute("UPDATE bildirimler SET okundu=1")


# ── Plaka stok ───────────────────────────────────────────────

def plaka_listele() -> list[dict]:
    with baglanti() as conn:
        rows = conn.execute(
            """SELECT * FROM plaka_stok
               ORDER BY cam_turu COLLATE NOCASE, kalinlik, boy, en"""
        ).fetchall()
    return [dict(r) for r in rows]


def plaka_ekle(veri: dict) -> dict:
    simdi = datetime.now().isoformat(timespec="seconds")
    cam = (veri.get("cam_turu") or "Düzcam").strip() or "Düzcam"
    try:
        kalinlik = float(str(veri.get("kalinlik", 4)).replace(",", "."))
        boy = float(str(veri.get("boy", 3210)).replace(",", ".") or 3210)
        en = float(str(veri.get("en", 2250)).replace(",", ".") or 2250)
        adet = int(veri.get("adet", 0) or 0)
    except (TypeError, ValueError) as e:
        raise ValueError("Kalınlık / ölçü / adet sayısal olmalı.") from e
    if kalinlik <= 0 or boy <= 0 or en <= 0:
        raise ValueError("Ölçüler 0'dan büyük olmalı.")
    if adet < 0:
        raise ValueError("Adet negatif olamaz.")
    with baglanti() as conn:
        # Aynı tür+kalınlık+ölçü varsa birleştir
        row = conn.execute(
            """SELECT id, adet FROM plaka_stok
               WHERE cam_turu=? AND kalinlik=? AND boy=? AND en=?""",
            (cam, kalinlik, boy, en),
        ).fetchone()
        if row:
            yeni = int(row["adet"]) + adet
            conn.execute(
                "UPDATE plaka_stok SET adet=?, not_metin=?, guncelleme=? WHERE id=?",
                (yeni, (veri.get("not_metin") or "").strip(), simdi, row["id"]),
            )
            rid = row["id"]
        else:
            cur = conn.execute(
                """INSERT INTO plaka_stok (cam_turu,kalinlik,boy,en,adet,not_metin,guncelleme)
                   VALUES (?,?,?,?,?,?,?)""",
                (cam, kalinlik, boy, en, adet, (veri.get("not_metin") or "").strip(), simdi),
            )
            rid = cur.lastrowid
        out = conn.execute("SELECT * FROM plaka_stok WHERE id=?", (rid,)).fetchone()
    return dict(out)


def plaka_guncelle(pid: int, veri: dict) -> Optional[dict]:
    simdi = datetime.now().isoformat(timespec="seconds")
    mevcut = None
    with baglanti() as conn:
        mevcut = conn.execute("SELECT * FROM plaka_stok WHERE id=?", (pid,)).fetchone()
        if not mevcut:
            return None
        cam = (veri.get("cam_turu") if "cam_turu" in veri else mevcut["cam_turu"]) or "Düzcam"
        cam = str(cam).strip() or "Düzcam"
        try:
            kalinlik = float(str(veri.get("kalinlik", mevcut["kalinlik"])).replace(",", "."))
            boy = float(str(veri.get("boy", mevcut["boy"])).replace(",", "."))
            en = float(str(veri.get("en", mevcut["en"])).replace(",", "."))
            adet = int(veri.get("adet", mevcut["adet"]))
        except (TypeError, ValueError) as e:
            raise ValueError("Kalınlık / ölçü / adet sayısal olmalı.") from e
        if kalinlik <= 0 or boy <= 0 or en <= 0:
            raise ValueError("Ölçüler 0'dan büyük olmalı.")
        if adet < 0:
            raise ValueError("Adet negatif olamaz.")
        not_metin = veri.get("not_metin", mevcut["not_metin"]) or ""
        conn.execute(
            """UPDATE plaka_stok
               SET cam_turu=?, kalinlik=?, boy=?, en=?, adet=?, not_metin=?, guncelleme=?
               WHERE id=?""",
            (cam, kalinlik, boy, en, adet, str(not_metin).strip(), simdi, pid),
        )
        out = conn.execute("SELECT * FROM plaka_stok WHERE id=?", (pid,)).fetchone()
    return dict(out)


def plaka_sil(pid: int) -> bool:
    with baglanti() as conn:
        cur = conn.execute("DELETE FROM plaka_stok WHERE id=?", (pid,))
    return cur.rowcount > 0


def plaka_ozet() -> dict:
    from config import PLAKA_UYARI_ESIK
    liste = plaka_listele()
    dusuk = [r for r in liste if int(r.get("adet") or 0) <= PLAKA_UYARI_ESIK]
    return {
        "satir": len(liste),
        "toplam_adet": sum(int(r.get("adet") or 0) for r in liste),
        "m2": round(sum(
            (float(r["boy"]) / 1000) * (float(r["en"]) / 1000) * int(r.get("adet") or 0)
            for r in liste
        ), 1),
        "uyari_esik": PLAKA_UYARI_ESIK,
        "dusuk_stok": [
            {
                "id": r["id"],
                "cam_turu": r["cam_turu"],
                "kalinlik": r["kalinlik"],
                "boy": r["boy"],
                "en": r["en"],
                "adet": r["adet"],
            }
            for r in dusuk
        ],
        "dusuk_adet": len(dusuk),
    }


def plaka_hareket_ekle(
    *,
    stok_id: Optional[int],
    tur: str,
    adet: int,
    cam_turu: str = "",
    kalinlik: float = 0,
    boy: float = 0,
    en: float = 0,
    siparis_id: str = "",
    kullanici: str = "",
    neden: str = "",
) -> dict:
    simdi = datetime.now().isoformat(timespec="seconds")
    with baglanti() as conn:
        cur = conn.execute(
            """INSERT INTO plaka_hareket
               (stok_id,tur,adet,cam_turu,kalinlik,boy,en,siparis_id,kullanici,neden,geri_alindi,zaman)
               VALUES (?,?,?,?,?,?,?,?,?,?,0,?)""",
            (
                stok_id, tur, int(adet), cam_turu, float(kalinlik or 0),
                float(boy or 0), float(en or 0), siparis_id or "",
                kullanici or "", neden or "", simdi,
            ),
        )
        rid = cur.lastrowid
        row = conn.execute("SELECT * FROM plaka_hareket WHERE id=?", (rid,)).fetchone()
    return dict(row)


def plaka_hareket_listele(limit: int = 100) -> list[dict]:
    with baglanti() as conn:
        rows = conn.execute(
            """SELECT * FROM plaka_hareket
               ORDER BY id DESC LIMIT ?""",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(r) for r in rows]


def plaka_stok_dus(
    cam_turu: str,
    kalinlik: float,
    dusulecek: int,
    boy: float = 3210,
    en: float = 2250,
    *,
    siparis_id: str = "",
    kullanici: str = "",
    neden: str = "",
) -> dict:
    """Stoktan plaka düşer ve hareket kaydı açar. Yetersizse ValueError."""
    if dusulecek <= 0:
        return {"dusulen": 0, "kalan": None, "hareket_id": None}
    stok = plaka_uygun_stok(cam_turu, kalinlik, boy, en)
    if not stok:
        raise ValueError(
            f"Stokta {cam_turu} / {kalinlik} mm plaka bulunamadı "
            f"({int(boy)}×{int(en)})."
        )
    # Tam ölçü eşleşmezse stok satırının gerçek boy/en'ini kullan
    mevcut = int(stok["adet"] or 0)
    if mevcut < dusulecek:
        raise ValueError(
            f"Yetersiz stok: {cam_turu} / {kalinlik} mm — "
            f"gerekli {dusulecek}, stokta {mevcut}."
        )
    yeni = mevcut - dusulecek
    guncel = plaka_guncelle(int(stok["id"]), {"adet": yeni})
    hareket = plaka_hareket_ekle(
        stok_id=int(stok["id"]),
        tur="dusum",
        adet=dusulecek,
        cam_turu=stok["cam_turu"],
        kalinlik=stok["kalinlik"],
        boy=stok["boy"],
        en=stok["en"],
        siparis_id=siparis_id,
        kullanici=kullanici,
        neden=neden or "AI kesim stok düşümü",
    )
    return {
        "dusulen": dusulecek,
        "kalan": yeni,
        "stok_id": stok["id"],
        "cam_turu": stok["cam_turu"],
        "kalinlik": stok["kalinlik"],
        "boy": stok["boy"],
        "en": stok["en"],
        "kayit": guncel,
        "hareket_id": hareket["id"],
    }


def plaka_hareket_geri_al(hareket_id: int, kullanici: str = "") -> dict:
    """Düşüm hareketini geri alır (stoka iade)."""
    with baglanti() as conn:
        h = conn.execute("SELECT * FROM plaka_hareket WHERE id=?", (hareket_id,)).fetchone()
        if not h:
            raise ValueError("Hareket bulunamadı.")
        h = dict(h)
        if h.get("geri_alindi"):
            raise ValueError("Bu hareket zaten geri alınmış.")
        if h.get("tur") != "dusum":
            raise ValueError("Sadece düşüm hareketleri geri alınabilir.")
        adet = int(h["adet"] or 0)
        stok_id = h.get("stok_id")
        if stok_id:
            stok = conn.execute("SELECT * FROM plaka_stok WHERE id=?", (stok_id,)).fetchone()
        else:
            stok = None
        if not stok:
            # Stok satırı silinmişse yeniden oluştur / birleştir
            raise ValueError("İlgili stok satırı bulunamadı — manuel ekleyin.")
        yeni = int(stok["adet"] or 0) + adet
        simdi = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE plaka_stok SET adet=?, guncelleme=? WHERE id=?",
            (yeni, simdi, stok["id"]),
        )
        conn.execute(
            "UPDATE plaka_hareket SET geri_alindi=1 WHERE id=?",
            (hareket_id,),
        )
    # İade hareketi
    iade = plaka_hareket_ekle(
        stok_id=int(stok["id"]),
        tur="iade",
        adet=adet,
        cam_turu=h["cam_turu"],
        kalinlik=h["kalinlik"],
        boy=h["boy"],
        en=h["en"],
        siparis_id=h.get("siparis_id") or "",
        kullanici=kullanici,
        neden=f"Geri al (hareket #{hareket_id})",
    )
    # Siparişteki plaka_dusum bilgisini güncelle
    sip_id = h.get("siparis_id") or ""
    if sip_id:
        sip = siparis_getir(sip_id)
        if sip:
            dusum = dict((sip.get("uretim_detay") or {}).get("plaka_dusum") or {})
            once = int(dusum.get("dusulen_plaka") or 0)
            dusum["dusulen_plaka"] = max(0, once - adet)
            dusum["geri_alinan"] = int(dusum.get("geri_alinan") or 0) + adet
            dusum["son_geri_al"] = datetime.now().isoformat(timespec="seconds")
            hareketler = list(dusum.get("hareket_idler") or [])
            if hareket_id in hareketler:
                hareketler = [x for x in hareketler if x != hareket_id]
            dusum["hareket_idler"] = hareketler
            siparis_plaka_dusum_kaydet(sip_id, dusum)
    return {"mesaj": f"{adet} plaka stoğa iade edildi.", "iade": iade, "hareket_id": hareket_id}


def plaka_uygun_stok(cam_turu: str, kalinlik: float, boy: float = 3210, en: float = 2250) -> Optional[dict]:
    """Tür + kalınlık (+ ölçü) eşleşen stok satırı. Önce tam ölçü."""
    cam = (cam_turu or "Düzcam").strip() or "Düzcam"
    try:
        kal = float(kalinlik)
        pb = float(boy)
        pe = float(en)
    except (TypeError, ValueError):
        return None
    with baglanti() as conn:
        row = conn.execute(
            """SELECT * FROM plaka_stok
               WHERE cam_turu=? AND ABS(kalinlik-?)<0.001 AND ABS(boy-?)<0.1 AND ABS(en-?)<0.1""",
            (cam, kal, pb, pe),
        ).fetchone()
        if row:
            return dict(row)
        row = conn.execute(
            """SELECT * FROM plaka_stok
               WHERE cam_turu=? AND ABS(kalinlik-?)<0.001
               ORDER BY adet DESC""",
            (cam, kal),
        ).fetchone()
    return dict(row) if row else None


def siparis_plaka_dusum_kaydet(
    siparis_id: str,
    dusum: dict,
    son_kesim: dict | None = None,
) -> Optional[dict]:
    """uretim_detay.plaka_dusum alanını günceller; isteğe bağlı son_kesim özeti."""
    sip = siparis_getir(siparis_id)
    if not sip:
        return None
    detay = dict(sip.get("uretim_detay") or {})
    detay["plaka_dusum"] = dusum
    if son_kesim is not None:
        detay["son_kesim"] = son_kesim
    veri = {
        "musteri": sip["musteri"],
        "urun": sip["urun"],
        "olcu": sip.get("olcu", ""),
        "adet": sip["adet"],
        "hazir_adet": sip["hazir_adet"],
        "bitis": sip["bitis"],
        "durum": sip.get("durum", "Beklemede"),
        "oncelik": sip.get("oncelik", "Normal"),
        "rotalar": sip.get("rotalar", ""),
        "istasyon_kapasiteleri": sip.get("istasyon_kapasiteleri", {}),
        "fire_oranlari": sip.get("fire_oranlari", {}),
        "uretim_detay": detay,
        "olusturma": sip.get("olusturma"),
    }
    return siparis_guncelle(siparis_id, veri)
