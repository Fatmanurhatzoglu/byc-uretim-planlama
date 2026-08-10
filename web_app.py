"""Flask web sunucusu — API + arayüz (v7.0)."""

from __future__ import annotations

import io
import math
import os
from datetime import datetime, timedelta
from functools import wraps

import pandas as pd
import qrcode
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from ai_planner import camlari_sirala, gunluk_kesim_plani
from auth import login_required, oturum_ac, oturum_kullanicisi, role_required
from backup import otomatik_yedek_baslat, yedek_al, yedekleri_listele, yedekten_geri_yukle
from config import APP_TITLE, APP_VERSION, BOLUM_KAPASITELERI, FIRE_NEDENLERI, SECRET_KEY, TUM_MAKINELER, WEB_HOST, WEB_PORT
from database import (
    asama_hareket_ekle,
    asama_ozet,
    asama_ozetleri_toplu,
    asama_sira_uyarisi,
    ayarlari_getir,
    ayarlari_kaydet,
    bildirim_ekle,
    bildirim_okundu,
    bildirim_tumunu_oku,
    bildirimler_listele,
    cizelge_kaydet,
    cizelge_son_getir,
    init_db,
    istasyon_siparisleri,
    kpi_ozet,
    kullanici_sifre_degistir,
    log_ekle,
    log_listele,
    parcali_sevk,
    plaka_ekle,
    plaka_guncelle,
    plaka_hareket_ekle,
    plaka_hareket_geri_al,
    plaka_hareket_listele,
    plaka_listele,
    plaka_ozet,
    plaka_sil,
    plaka_stok_dus,
    plaka_uygun_stok,
    siparis_ekle,
    siparis_getir,
    siparis_guncelle,
    siparis_plaka_dusum_kaydet,
    siparis_sil,
    tum_kullanicilar,
    tum_siparisler,
    tumunu_sil,
)
from plaka_hesap import KENAR_BOSLUK_MM, STANDART_PLAKA_BOY, STANDART_PLAKA_EN, siparis_plaka_ozet
from is_emri_assets import LOGO_BYC_B64, LOGO_UNITED_B64, OLCU_SEMA_B64
from reports import haftalik_pdf, siparis_detay_pdf
from scheduler import UretimCizelgeleyici

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.secret_key = SECRET_KEY

_son_cizelge: dict | None = None


def _kullanici_log(islem: str, detay: str = "", hedef_id: str = ""):
    k = oturum_kullanicisi()
    if k:
        log_ekle(k["kullanici_adi"], islem, detay, hedef_id)


def _plan_to_dict(kayit) -> dict:
    doluluk = kayit.doluluk.replace("%", "")
    return {
        "makine": kayit.makine, "musteri": kayit.musteri, "urun": kayit.urun,
        "adet": kayit.adet, "hiz": kayit.hiz, "yuk": kayit.yuk,
        "doluluk": kayit.doluluk, "doluluk_pct": float(doluluk) if doluluk else 0,
        "tag": kayit.tag, "siparis_id": kayit.siparis_id, "oncelik": kayit.oncelik,
        "islem_sira": kayit.islem_sira, "rota_toplam": kayit.rota_toplam,
        "tarih": kayit.tarih, "sevk_hedef": kayit.sevk_hedef,
    }


_SORUN_TAGS = frozenset({"sevk_gecikti", "kapasite", "DarBogaz"})
_YOGUN_TAGS = frozenset({"yogun", "Kritik"})
_GANTT_RENK = {
    "normal": "gantt-green",
    "Normal": "gantt-green",
    "yogun": "gantt-yellow",
    "Kritik": "gantt-yellow",
    "sevk_gecikti": "gantt-red",
    "kapasite": "gantt-orange",
    "DarBogaz": "gantt-red",
}


def _tag_oncelik(tag: str) -> int:
    """Adım özetinde daha ağır etiketi koru (yüksek = daha kritik)."""
    if tag in _SORUN_TAGS:
        return 3 if tag == "kapasite" else 2
    if tag in _YOGUN_TAGS:
        return 1
    return 0


def _gantt_verisi(sonuc) -> list[dict]:
    gorevler, idx = [], 0

    for gun_str, kayitlar in sorted(sonuc.gunluk_takvim.items(), key=lambda x: UretimCizelgeleyici.gun_sirala(x[0])):
        try:
            baslangic = datetime.strptime(gun_str.split()[0], "%d.%m.%Y")
        except ValueError:
            continue
        bitis = baslangic + timedelta(days=1)
        for k in kayitlar:
            idx += 1
            gorevler.append({
                "id": f"g{idx}",
                "name": f"{k.islem_sira}. {k.makine} | {k.musteri} — {k.urun}",
                "start": baslangic.strftime("%Y-%m-%d"),
                "end": bitis.strftime("%Y-%m-%d"),
                "progress": 100,
                "custom_class": _GANTT_RENK.get(k.tag, "gantt-green"),
                "makine": k.makine,
                "adet": k.adet,
                "siparis_id": k.siparis_id,
                "durum": k.yuk,
                "oncelik": k.oncelik,
                "islem_sira": k.islem_sira,
                "rota_toplam": k.rota_toplam,
                "musteri": k.musteri,
                "urun": k.urun,
                "tag": k.tag,
                "tarih": k.tarih,
            })
    return gorevler


def _islem_sirasi_ozet(sonuc) -> list[dict]:
    """Her sipariş için işlem sırasını (Kesim → Rodaj 1/2 → ...) tarihleriyle özetler."""
    siparisler: dict[str, dict] = {}
    for gun_str, kayitlar in sorted(
        sonuc.gunluk_takvim.items(), key=lambda x: UretimCizelgeleyici.gun_sirala(x[0])
    ):
        for k in kayitlar:
            sid = k.siparis_id or f"{k.musteri}|{k.urun}"
            if sid not in siparisler:
                siparisler[sid] = {
                    "siparis_id": k.siparis_id,
                    "musteri": k.musteri,
                    "urun": k.urun,
                    "oncelik": k.oncelik,
                    "sevk_hedef": k.sevk_hedef,
                    "adimlar": {},
                }
            adim = siparisler[sid]["adimlar"].setdefault(
                k.islem_sira,
                {
                    "sira": k.islem_sira,
                    "makine": k.makine,
                    "tarihler": [],
                    "adet": 0,
                    "tag": k.tag,
                },
            )
            if k.tarih and k.tarih not in adim["tarihler"]:
                adim["tarihler"].append(k.tarih)
            adim["adet"] += k.adet
            if _tag_oncelik(k.tag) > _tag_oncelik(adim["tag"]):
                adim["tag"] = k.tag

    sonuc_list = []
    for sip in siparisler.values():
        adimlar = [sip["adimlar"][s] for s in sorted(sip["adimlar"].keys())]
        rota_metin = " → ".join(
            f"{a['sira']}. {a['makine']} ({', '.join(a['tarihler'])})" for a in adimlar
        )
        sonuc_list.append({**sip, "adimlar": adimlar, "rota_metin": rota_metin})
    return sonuc_list


def _gantt_makine_gruplu(gorevler: list) -> dict:
    gruplar = {}
    for g in gorevler:
        m = g.get("makine", "Diğer")
        gruplar.setdefault(m, []).append(g)
    return gruplar


def _cizelgele(siparisler: list) -> dict:
    ayar = ayarlari_getir()
    kap = ayar.get("varsayilan_kapasiteler", {})
    cizelgeleyici = UretimCizelgeleyici(kap)
    sonuc = cizelgeleyici.calistir(siparisler)

    gunler = []
    for gun_str in sorted(sonuc.gunluk_takvim.keys(), key=UretimCizelgeleyici.gun_sirala):
        kayitlar = [_plan_to_dict(k) for k in sonuc.gunluk_takvim[gun_str]]
        kayitlar.sort(key=lambda x: (x.get("islem_sira", 99), x.get("musteri", "")))
        ozet = cizelgeleyici.gun_ozeti(gun_str)
        dar = sum(1 for k in kayitlar if k["tag"] in _SORUN_TAGS)
        gunler.append({"gun": gun_str, "is_sayisi": len(kayitlar), "dar_bogaz": dar,
                        "kayitlar": kayitlar, "doluluk_ozet": ozet})

    gantt = _gantt_verisi(sonuc)
    # Etiket dağılımı — Pano / özet için
    etiket_sayilari = {"sevk_gecikti": 0, "kapasite": 0, "yogun": 0}
    for kayitlar in sonuc.gunluk_takvim.values():
        for k in kayitlar:
            if k.tag == "sevk_gecikti":
                etiket_sayilari["sevk_gecikti"] += 1
            elif k.tag == "kapasite":
                etiket_sayilari["kapasite"] += 1
            elif k.tag in _YOGUN_TAGS:
                etiket_sayilari["yogun"] += 1
            elif k.tag == "DarBogaz":
                etiket_sayilari["sevk_gecikti"] += 1

    return {
        "dar_bogaz_sayisi": sonuc.dar_bogaz_sayisi,
        "etiket_sayilari": etiket_sayilari,
        "uyarilar": sonuc.uyarilar,
        "gunler": gunler,
        "gantt": gantt,
        "gantt_gruplu": _gantt_makine_gruplu(gantt),
        "islem_sirasi": _islem_sirasi_ozet(sonuc),
    }


# ── Auth sayfaları ───────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login_sayfa():
    if oturum_kullanicisi():
        return redirect(url_for("ana_sayfa"))
    if request.method == "POST":
        veri = request.get_json(force=True) if request.is_json else request.form
        k = oturum_ac(veri.get("kullanici_adi", ""), veri.get("sifre", ""))
        if k:
            session["kullanici_id"] = k["id"]
            log_ekle(k["kullanici_adi"], "Giriş", "Oturum açıldı")
            if request.is_json:
                return jsonify({"mesaj": "OK", "kullanici": k})
            if k["rol"] == "saha":
                return redirect(url_for("mobil_sayfa"))
            return redirect(url_for("ana_sayfa"))
        if request.is_json:
            return jsonify({"hata": "Kullanıcı adı veya şifre hatalı."}), 401
        return render_template("login.html", hata="Kullanıcı adı veya şifre hatalı.", app_title=APP_TITLE)
    return render_template("login.html", hata=None, app_title=APP_TITLE)


@app.route("/logout")
def logout():
    k = oturum_kullanicisi()
    if k:
        log_ekle(k["kullanici_adi"], "Çıkış", "Oturum kapatıldı")
    session.clear()
    return redirect(url_for("login_sayfa"))


@app.route("/api/oturum")
def api_oturum():
    k = oturum_kullanicisi()
    if not k:
        return jsonify({"giris": False}), 401
    return jsonify({"giris": True, "kullanici": k})


# ── Ana sayfalar ─────────────────────────────────────────────

@app.route("/")
@login_required
def ana_sayfa():
    k = oturum_kullanicisi()
    if k and k["rol"] == "saha":
        return redirect(url_for("mobil_sayfa"))
    return render_template("index.html", app_title=APP_TITLE, app_version=APP_VERSION,
                           makineler=TUM_MAKINELER, fire_nedenleri=FIRE_NEDENLERI, kullanici=k)


@app.route("/mobile")
@login_required
def mobil_sayfa():
    return render_template("mobile.html", app_title=APP_TITLE, kullanici=oturum_kullanicisi())


@app.route("/istasyon")
@login_required
def istasyon_sayfa():
    return render_template(
        "istasyon.html",
        app_title=APP_TITLE,
        app_version=APP_VERSION,
        makineler=TUM_MAKINELER,
        fire_nedenleri=FIRE_NEDENLERI,
        kullanici=oturum_kullanicisi(),
    )


@app.route("/sevk/<siparis_id>")
@login_required
def sevk_sayfa(siparis_id):
    sip = siparis_getir(siparis_id)
    if not sip:
        return "Sipariş bulunamadı", 404
    return render_template("sevk.html", siparis=sip, kullanici=oturum_kullanicisi())


@app.route("/api/istasyon/<path:makine>/siparisler")
@login_required
def api_istasyon_siparisler(makine):
    return jsonify(istasyon_siparisleri(makine))


@app.route("/api/siparisler/<siparis_id>/asama/uyari", methods=["POST"])
@login_required
def api_asama_uyari(siparis_id):
    """Kayıt öncesi sıra uyarısı (işlemi engellemez)."""
    veri = request.get_json(force=True) or {}
    ozet = asama_ozet(siparis_id)
    if not ozet:
        return jsonify({"hata": "Sipariş bulunamadı."}), 404
    uyari = asama_sira_uyarisi(
        ozet,
        (veri.get("istasyon") or "").strip(),
        (veri.get("tur") or "").strip(),
    )
    return jsonify({"uyari": uyari, "ozet": ozet})


# ── KPI & Sipariş API ────────────────────────────────────────

@app.route("/api/kpi")
@login_required
def api_kpi():
    return jsonify(kpi_ozet())


@app.route("/api/siparisler", methods=["GET"])
@login_required
def api_siparis_liste():
    liste = tum_siparisler()
    ozler = asama_ozetleri_toplu([s["id"] for s in liste])
    for s in liste:
        o = ozler.get(s["id"]) or {}
        s["aktif_istasyon"] = o.get("aktif_istasyon", "Başlamadı")
        s["aktif_stok"] = o.get("aktif_stok", 0)
    return jsonify(liste)


def _siparis_olcu_metin(sip: dict | None, oz: dict | None = None) -> str:
    """Sipariş ölçü metni: boy×en×kalınlık (sipariş ölçüsü, kesim payı değil)."""
    if not sip:
        return ""
    detay = sip.get("uretim_detay") or {}
    if isinstance(detay, str):
        import json
        detay = json.loads(detay or "{}")
    oz = oz or {}
    boy = detay.get("boy")
    en = detay.get("en")
    kal = detay.get("kalinlik") or oz.get("kalinlik")
    if (boy in (None, "", 0, 0.0) or en in (None, "", 0, 0.0)) and sip.get("olcu"):
        parts = [
            p.strip()
            for p in str(sip["olcu"]).replace("×", "x").replace("*", "x").replace("X", "x").split("x")
            if p.strip()
        ]
        if len(parts) >= 2:
            if boy in (None, "", 0, 0.0):
                boy = parts[0]
            if en in (None, "", 0, 0.0):
                en = parts[1]
        if len(parts) >= 3 and kal in (None, "", 0, 0.0):
            kal = parts[2]
    try:
        boy_f = float(str(boy).replace(",", ".")) if boy not in (None, "") else 0
        en_f = float(str(en).replace(",", ".")) if en not in (None, "") else 0
    except (TypeError, ValueError):
        boy_f, en_f = 0, 0
    if boy_f <= 0 or en_f <= 0:
        return (sip.get("olcu") or "").strip()
    try:
        kal_f = float(str(kal).replace(",", ".")) if kal not in (None, "", 0, 0.0) else 0
    except (TypeError, ValueError):
        kal_f = 0
    if kal_f > 0:
        return f"{_olcu_sayi(boy_f)}×{_olcu_sayi(en_f)}×{_olcu_sayi(kal_f)}"
    return f"{_olcu_sayi(boy_f)}×{_olcu_sayi(en_f)}"


def _olcu_sayi(v: float) -> str:
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:g}"


def _kesim_kalan_ihtiyac(sip: dict, ozet_asama: dict | None = None) -> dict:
    """Kalan kesilecek parça: aşama Kesim giriş/çıkış ile fire dahil hedeften.

    Hedef = siparis_kesim_ihtiyaci (fire dahil, net kalan sipariş).
    Kesilmiş = max(gelen, çıkan+fire) — aşamada izlenen kesim ilerlemesi.
    Aşama yoksa hedef doğrudan kalan ihtiyaçtır.
    """
    from fire import siparis_kesim_ihtiyaci

    ihtiyac = siparis_kesim_ihtiyaci(sip)
    hedef = int(ihtiyac.get("kesilmesi_gereken") or 0)
    oz = ozet_asama if ozet_asama is not None else asama_ozet(sip["id"])
    kesim = next(
        (a for a in (oz or {}).get("asamalar", []) if a.get("istasyon") == "Kesim"),
        None,
    )
    kesilmis = 0
    if kesim:
        gelen = int(kesim.get("gelen") or 0)
        cikan = int(kesim.get("cikan") or 0)
        fire = int(kesim.get("fire") or 0)
        if gelen or cikan or fire:
            kesilmis = max(gelen, cikan + fire)
    kalan = max(0, hedef - kesilmis)
    return {
        "hedef_kesim": hedef,
        "kesilmis": kesilmis,
        "kalan_kesilecek": kalan,
        "net_adet": int(ihtiyac.get("net_adet") or 0),
        "fire_ozet": ihtiyac.get("ozet") or "",
    }


def _siparis_plaka_baglam(sip: dict | None) -> dict | None:
    """İstasyon Kesim kartı için plaka özeti + stok + kalan ihtiyaç."""
    if not sip:
        return None
    ozet_asama = asama_ozet(sip["id"])
    kalan_info = _kesim_kalan_ihtiyac(sip, ozet_asama)
    kalan = int(kalan_info["kalan_kesilecek"])
    oz = siparis_plaka_ozet(sip, kesim_adet=kalan if kalan > 0 else kalan_info["hedef_kesim"])
    stok_adet = None
    if oz.get("olcu_var") and (oz.get("kalinlik") not in (None, "", 0, 0.0)):
        stok = plaka_uygun_stok(
            oz["cam_turu"], oz["kalinlik"], oz["plaka_boy"], oz["plaka_en"]
        )
        stok_adet = int(stok["adet"]) if stok else 0
    elif oz.get("olcu_var"):
        stok_adet = None
    once = (sip.get("uretim_detay") or {}).get("plaka_dusum") or {}
    son_kesim = (sip.get("uretim_detay") or {}).get("son_kesim") or None
    plaka_basi = int(oz.get("plaka_basi") or 0)
    gerekli = int(math.ceil(kalan / plaka_basi)) if plaka_basi > 0 and kalan > 0 else 0
    olcu_metin = _siparis_olcu_metin(sip, oz)
    oz["stok_adet"] = stok_adet
    oz["once_dusulen"] = int(once.get("dusulen_plaka") or 0)
    oz["kalan_kesilecek"] = kalan
    oz["hedef_kesim"] = kalan_info["hedef_kesim"]
    oz["kesilmis"] = kalan_info["kesilmis"]
    oz["gerekli_plaka"] = gerekli
    oz["siparis_olcu"] = olcu_metin
    oz["son_kesim"] = son_kesim
    # plaka_ihtiyac = kalan için gerekli (eski alan, UI/uyumluluk)
    oz["plaka_ihtiyac"] = gerekli
    oz["kesilecek_adet"] = kalan
    return oz


def _kesim_plaka_parca_kaydet(siparis_id: str, veri: dict) -> dict:
    """Kesim: ihtiyaç kadar parça + tüketilen plaka düşümü; fazla tam plaka stoğa iade."""
    try:
        alinan_plaka = int(veri.get("plaka_adet") or veri.get("alinan_plaka") or 0)
    except (TypeError, ValueError):
        alinan_plaka = 0
    try:
        parca_adet = int(veri.get("parca_adet") or veri.get("adet") or 0)
    except (TypeError, ValueError):
        parca_adet = 0
    if alinan_plaka <= 0:
        raise ValueError("Raftan alınan plaka adedi en az 1 olmalı.")
    if parca_adet <= 0:
        raise ValueError("Çıkan / kesilen parça adedi en az 1 olmalı.")

    sip = siparis_getir(siparis_id)
    if not sip:
        raise ValueError("Sipariş bulunamadı.")

    kalan_info = _kesim_kalan_ihtiyac(sip)
    kalan = int(kalan_info["kalan_kesilecek"])
    if kalan <= 0:
        raise ValueError(
            "Bu siparişte kesilecek kalan parça yok "
            f"(hedef {kalan_info['hedef_kesim']}, kesilmiş {kalan_info['kesilmis']})."
        )
    if parca_adet > kalan:
        raise ValueError(
            f"Kalan ihtiyaç {kalan} parça; {parca_adet} kesilemez. "
            "Fire dahil kalan ihtiyacı aşmayın."
        )

    oz = siparis_plaka_ozet(sip, kesim_adet=parca_adet)
    if not oz.get("olcu_var"):
        raise ValueError(
            "Bu siparişte boy/en yok — plaka stok düşümü yapılamaz. "
            "Önce ofisten ölçü / üretim detayını girin."
        )
    if not oz.get("kalinlik"):
        raise ValueError("Siparişte kalınlık yok — plaka stok eşleştirilemedi.")

    plaka_basi = int(oz.get("plaka_basi") or 0)
    if plaka_basi <= 0:
        raise ValueError(
            "Bu ölçüyle plakadan parça çıkmıyor — kesim kaydı yapılamaz. "
            "Ölçü / plaka boyutunu kontrol edin."
        )

    tuketilen = int(math.ceil(parca_adet / plaka_basi))
    if alinan_plaka < tuketilen:
        raise ValueError(
            f"{parca_adet} parça için en az {tuketilen} plaka gerekir "
            f"(1 plakadan {plaka_basi}). Raftan alınan: {alinan_plaka}."
        )
    iade_adet = max(0, alinan_plaka - tuketilen)
    olcu_metin = _siparis_olcu_metin(sip, oz)

    kullanici = (oturum_kullanicisi() or {}).get("kullanici_adi", "")
    ekstra_not = (veri.get("not") or veri.get("not_metin") or "").strip()
    baglam = (
        f"Kesim: {parca_adet} adet cam kesildi (ölçü {olcu_metin or '?'}). "
        f"Raftan {alinan_plaka} plaka · tüketilen {tuketilen}"
        + (f" · stoğa iade {iade_adet}" if iade_adet else "")
        + f" ({oz['cam_turu']} {oz['kalinlik']:g} mm, "
        f"~{plaka_basi} adet/plaka)"
    )
    if ekstra_not:
        baglam = f"{baglam} | {ekstra_not}"

    # Stok: raftan alınanı düş, kullanılmayan tam plakayı iade et (net = tüketilen)
    sonuc_dus = plaka_stok_dus(
        oz["cam_turu"],
        oz["kalinlik"],
        alinan_plaka,
        oz["plaka_boy"],
        oz["plaka_en"],
        siparis_id=str(siparis_id),
        kullanici=kullanici,
        neden=f"İstasyon Kesim · {sip.get('musteri')}/{sip.get('urun')}",
    )
    sonuc_iade = None
    kalan_stok = sonuc_dus.get("kalan")
    if iade_adet > 0:
        try:
            # İade, düşüm yapılan stok satırının gerçek ölçüleriyle
            iade_boy = float(sonuc_dus.get("boy") or oz["plaka_boy"])
            iade_en = float(sonuc_dus.get("en") or oz["plaka_en"])
            iade_cam = sonuc_dus.get("cam_turu") or oz["cam_turu"]
            iade_kal = float(sonuc_dus.get("kalinlik") or oz["kalinlik"])
            kayit = plaka_ekle({
                "cam_turu": iade_cam,
                "kalinlik": iade_kal,
                "boy": iade_boy,
                "en": iade_en,
                "adet": iade_adet,
                "not_metin": f"Kesim iade · sipariş {siparis_id}",
            })
            iade_hareket = plaka_hareket_ekle(
                stok_id=int(kayit["id"]),
                tur="iade",
                adet=iade_adet,
                cam_turu=iade_cam,
                kalinlik=iade_kal,
                boy=iade_boy,
                en=iade_en,
                siparis_id=str(siparis_id),
                kullanici=kullanici,
                neden=(
                    f"Kesim kullanılmayan plaka iadesi · "
                    f"{sip.get('musteri')}/{sip.get('urun')}"
                ),
            )
            kalan_stok = int(kayit.get("adet") or 0)
            sonuc_iade = {
                "adet": iade_adet,
                "hareket_id": iade_hareket.get("id"),
                "kalan_stok": kalan_stok,
            }
        except Exception:
            hid = sonuc_dus.get("hareket_id")
            if hid:
                try:
                    plaka_hareket_geri_al(int(hid), kullanici=kullanici)
                except Exception:
                    pass
            raise

    sonraki_aktar = bool(veri.get("sonraki_aktar", True))
    try:
        asama_hareket_ekle(
            siparis_id=siparis_id,
            istasyon="Kesim",
            tur="giris",
            adet=parca_adet,
            neden="",
            not_metin=f"{baglam} [alınan={alinan_plaka}, tüketilen={tuketilen}, iade={iade_adet}]",
            kullanici=kullanici,
            sonraki_aktar=False,
        )
        ozet = asama_hareket_ekle(
            siparis_id=siparis_id,
            istasyon="Kesim",
            tur="cikis",
            adet=parca_adet,
            neden="",
            not_metin=baglam,
            kullanici=kullanici,
            sonraki_aktar=sonraki_aktar,
        )
    except Exception:
        # Aşama başarısızsa stok düşümünü (ve varsa iadeyi tersine) geri al
        if iade_adet > 0:
            try:
                plaka_stok_dus(
                    sonuc_dus.get("cam_turu") or oz["cam_turu"],
                    float(sonuc_dus.get("kalinlik") or oz["kalinlik"]),
                    iade_adet,
                    float(sonuc_dus.get("boy") or oz["plaka_boy"]),
                    float(sonuc_dus.get("en") or oz["plaka_en"]),
                    siparis_id=str(siparis_id),
                    kullanici=kullanici,
                    neden="Kesim aşama hatası — iade geri alındı",
                )
            except Exception:
                pass
        hid = sonuc_dus.get("hareket_id")
        if hid:
            try:
                plaka_hareket_geri_al(int(hid), kullanici=kullanici)
            except Exception:
                pass
        raise

    once = (sip.get("uretim_detay") or {}).get("plaka_dusum") or {}
    once_adet = int(once.get("dusulen_plaka") or 0)
    hareket_idler = list(once.get("hareket_idler") or [])
    if sonuc_dus.get("hareket_id"):
        hareket_idler.append(sonuc_dus["hareket_id"])
    if sonuc_iade and sonuc_iade.get("hareket_id"):
        hareket_idler.append(sonuc_iade["hareket_id"])

    son_kesim = {
        "parca_adet": parca_adet,
        "olcu": olcu_metin,
        "alinan_plaka": alinan_plaka,
        "tuketilen_plaka": tuketilen,
        "iade_plaka": iade_adet,
        "plaka_basi": plaka_basi,
        "mesaj": (
            f"{parca_adet} adet cam kesildi (ölçü {olcu_metin or '?'}). "
            f"{tuketilen} plaka stoktan düşüldü."
            + (f" {iade_adet} plaka stoğa iade." if iade_adet else "")
        ),
        "zaman": datetime.now().isoformat(timespec="seconds"),
        "kullanici": kullanici,
    }

    siparis_plaka_dusum_kaydet(
        siparis_id,
        {
            "dusulen_plaka": once_adet + tuketilen,
            "bu_islem": tuketilen,
            "alinan_plaka": alinan_plaka,
            "iade_plaka": iade_adet,
            "plaka_basi": plaka_basi,
            "kesilecek_adet": oz.get("kesilecek_adet"),
            "parca_adet": parca_adet,
            "olcu": olcu_metin,
            "cam_turu": oz["cam_turu"],
            "kalinlik": oz["kalinlik"],
            "plaka_boy": oz["plaka_boy"],
            "plaka_en": oz["plaka_en"],
            "kaynak": "istasyon",
            "hareket_idler": hareket_idler,
            "zaman": datetime.now().isoformat(timespec="seconds"),
        },
        son_kesim=son_kesim,
    )

    ozet = ozet or asama_ozet(siparis_id) or {}
    ozet["plaka"] = _siparis_plaka_baglam(siparis_getir(siparis_id))
    ozet["plaka_dusum"] = {
        "dusulen": tuketilen,
        "alinan": alinan_plaka,
        "iade": iade_adet,
        "kalan_stok": kalan_stok,
        "parca_adet": parca_adet,
        "olcu": olcu_metin,
        "mesaj": son_kesim["mesaj"],
    }
    ozet["son_kesim"] = son_kesim
    return ozet


@app.route("/api/siparisler/<siparis_id>/asama", methods=["GET"])
@login_required
def api_asama_getir(siparis_id):
    ozet = asama_ozet(siparis_id)
    if not ozet:
        return jsonify({"hata": "Sipariş bulunamadı."}), 404
    sip = siparis_getir(siparis_id)
    ozet["plaka"] = _siparis_plaka_baglam(sip)
    return jsonify(ozet)


@app.route("/api/siparisler/<siparis_id>/asama", methods=["POST"])
@login_required
@role_required("admin", "ofis", "saha")
def api_asama_hareket(siparis_id):
    veri = request.get_json(force=True) or {}
    istasyon = (veri.get("istasyon") or "").strip()
    tur = (veri.get("tur") or "").strip()
    try:
        # Kesim plaka→parça kaydı (fire hariç)
        if istasyon == "Kesim" and tur in ("kesim", "giris", "cikis") and (
            veri.get("plaka_adet") is not None and str(veri.get("plaka_adet")).strip() != ""
        ):
            ozet = _kesim_plaka_parca_kaydet(siparis_id, veri)
            pd = ozet.get("plaka_dusum") or {}
            _kullanici_log(
                "Aşama",
                (
                    f"kesim {pd.get('parca_adet')} parça (ölçü {pd.get('olcu') or '?'}) · "
                    f"tüketilen {pd.get('dusulen')} plaka"
                    + (f" · iade {pd.get('iade')}" if pd.get("iade") else "")
                    + " @ Kesim"
                )
                + (f" | UYARI: {ozet.get('uyari')}" if ozet.get("uyari") else ""),
                siparis_id,
            )
            return jsonify(ozet)

        ozet = asama_hareket_ekle(
            siparis_id=siparis_id,
            istasyon=istasyon,
            tur=tur,
            adet=int(veri.get("adet") or 0),
            neden=(veri.get("neden") or "").strip(),
            not_metin=(veri.get("not") or veri.get("not_metin") or "").strip(),
            kullanici=(oturum_kullanicisi() or {}).get("kullanici_adi", ""),
            sonraki_aktar=bool(veri.get("sonraki_aktar", True)),
        )
        _kullanici_log(
            "Aşama",
            f"{veri.get('tur')} {veri.get('adet')} @ {veri.get('istasyon')}"
            + (f" ({veri.get('neden')})" if veri.get("neden") else "")
            + (f" | UYARI: {ozet.get('uyari')}" if ozet.get("uyari") else ""),
            siparis_id,
        )
        sip = siparis_getir(siparis_id)
        ozet["plaka"] = _siparis_plaka_baglam(sip)
        return jsonify(ozet)
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400
    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@app.route("/api/fire-nedenleri", methods=["GET"])
@login_required
def api_fire_nedenleri():
    return jsonify(FIRE_NEDENLERI)


def _siparis_dogrula(veri: dict) -> str | None:
    if not (veri.get("musteri") or "").strip():
        return "Müşteri adı zorunludur."
    if not (veri.get("urun") or "").strip():
        return "Ürün kodu zorunludur."
    try:
        adet = int(veri.get("adet", 0))
        hazir = int(veri.get("hazir_adet", 0) or 0)
    except (TypeError, ValueError):
        return "Adet alanları sayısal olmalıdır."
    if adet <= 0:
        return "Toplam adet 0'dan büyük olmalıdır."
    if hazir < 0 or hazir > adet:
        return "Sevk edilen adet geçersiz."
    bitis = (veri.get("bitis") or "").strip()
    try:
        datetime.strptime(bitis, "%d.%m.%Y")
    except ValueError:
        return "Sevk tarihi GG.AA.YYYY formatında olmalıdır."
    rotalar = [x.strip() for x in (veri.get("rotalar") or "").split(",") if x.strip()]
    if not rotalar:
        return "En az bir proses istasyonu seçin."
    return None


@app.route("/api/siparisler", methods=["POST"])
@login_required
@role_required("admin", "ofis")
def api_siparis_olustur():
    veri = request.get_json(force=True) or {}
    hata = _siparis_dogrula(veri)
    if hata:
        return jsonify({"hata": hata}), 400
    try:
        sip = siparis_ekle(veri)
    except Exception as e:
        return jsonify({"hata": f"Kayıt hatası: {e}"}), 400
    _kullanici_log("Sipariş Ekle", f"{sip['musteri']} / {sip['urun']}", sip["id"])
    return jsonify(sip), 201


@app.route("/api/siparisler/<siparis_id>", methods=["GET"])
@login_required
def api_siparis_detay(siparis_id):
    sip = siparis_getir(siparis_id)
    if not sip:
        return jsonify({"hata": "Sipariş bulunamadı."}), 404
    return jsonify(sip)


@app.route("/api/siparisler/<siparis_id>", methods=["PUT"])
@login_required
@role_required("admin", "ofis")
def api_siparis_duzenle(siparis_id):
    veri = request.get_json(force=True) or {}
    hata = _siparis_dogrula(veri)
    if hata:
        return jsonify({"hata": hata}), 400
    sip = siparis_guncelle(siparis_id, veri)
    if not sip:
        return jsonify({"hata": "Sipariş bulunamadı."}), 404
    _kullanici_log("Sipariş Güncelle", f"{sip['musteri']} / {sip['urun']}", siparis_id)
    return jsonify(sip)


@app.route("/api/siparisler/<siparis_id>", methods=["DELETE"])
@login_required
@role_required("admin", "ofis")
def api_siparis_kaldir(siparis_id):
    if siparis_sil(siparis_id):
        _kullanici_log("Sipariş Sil", "", siparis_id)
        return jsonify({"mesaj": "Silindi."})
    return jsonify({"hata": "Sipariş bulunamadı."}), 404


@app.route("/api/siparisler/tumunu-sil", methods=["DELETE"])
@login_required
@role_required("admin")
def api_tumunu_sil():
    tumunu_sil()
    _kullanici_log("Tümünü Sil", "Sipariş havuzu temizlendi")
    return jsonify({"mesaj": "Tüm siparişler silindi."})


@app.route("/api/siparisler/<siparis_id>/sevk", methods=["POST"])
@login_required
def api_sevk(siparis_id):
    adet = int(request.get_json(force=True).get("adet", 0))
    try:
        sip = parcali_sevk(siparis_id, adet)
        _kullanici_log("Sevk", f"{adet} adet", siparis_id)
        return jsonify(sip)
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400


@app.route("/api/siparisler/<siparis_id>/qr")
@login_required
def api_qr(siparis_id):
    sip = siparis_getir(siparis_id)
    if not sip:
        return jsonify({"hata": "Bulunamadı."}), 404
    url = request.host_url.rstrip("/") + url_for("sevk_sayfa", siparis_id=siparis_id)
    cache_dir = os.path.join("yedekler", "qr_cache")
    os.makedirs(cache_dir, exist_ok=True)
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(siparis_id))[:80]
    cache_path = os.path.join(cache_dir, f"{safe}.png")
    # Basit URL değişiminde yeniden üret
    meta_path = cache_path + ".url"
    if os.path.exists(cache_path) and os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                if f.read().strip() == url:
                    return send_file(cache_path, mimetype="image/png")
        except OSError:
            pass
    img = qrcode.make(url)
    img.save(cache_path, format="PNG")
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(url)
    except OSError:
        pass
    return send_file(cache_path, mimetype="image/png")


# ── Plaka stok ───────────────────────────────────────────────

@app.route("/api/plaka-stok", methods=["GET"])
@login_required
def api_plaka_liste():
    return jsonify({"liste": plaka_listele(), "ozet": plaka_ozet()})


@app.route("/api/plaka-stok", methods=["POST"])
@login_required
@role_required("admin", "ofis")
def api_plaka_ekle():
    try:
        kayit = plaka_ekle(request.get_json(force=True) or {})
        _kullanici_log("Plaka Stok", f"+{kayit.get('adet')} {kayit.get('cam_turu')} {kayit.get('kalinlik')}mm")
        return jsonify(kayit), 201
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400


@app.route("/api/plaka-stok/<int:pid>", methods=["PUT"])
@login_required
@role_required("admin", "ofis")
def api_plaka_guncelle(pid):
    try:
        kayit = plaka_guncelle(pid, request.get_json(force=True) or {})
        if not kayit:
            return jsonify({"hata": "Kayıt yok."}), 404
        _kullanici_log("Plaka Stok", f"Güncelle #{pid} adet={kayit.get('adet')}")
        return jsonify(kayit)
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400


@app.route("/api/plaka-stok/<int:pid>", methods=["DELETE"])
@login_required
@role_required("admin", "ofis")
def api_plaka_sil(pid):
    if plaka_sil(pid):
        _kullanici_log("Plaka Stok", f"Silindi #{pid}")
        return jsonify({"mesaj": "Silindi."})
    return jsonify({"hata": "Kayıt yok."}), 404


@app.route("/api/plaka-hareket", methods=["GET"])
@login_required
def api_plaka_hareket():
    limit = request.args.get("limit", 100, type=int)
    return jsonify({"liste": plaka_hareket_listele(limit), "ozet": plaka_ozet()})


@app.route("/api/plaka-hareket/<int:hid>/geri-al", methods=["POST"])
@login_required
@role_required("admin", "ofis")
def api_plaka_geri_al(hid):
    try:
        kull = oturum_kullanicisi() or {}
        sonuc = plaka_hareket_geri_al(
            hid,
            kullanici=kull.get("kullanici_adi") or kull.get("ad") or "",
        )
        _kullanici_log("Plaka Geri Al", f"hareket #{hid}")
        return jsonify(sonuc)
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400


# ── Ayarlar ──────────────────────────────────────────────────

@app.route("/api/ayarlar", methods=["GET"])
@login_required
def api_ayarlar_getir():
    return jsonify(ayarlari_getir())


@app.route("/api/ayarlar", methods=["PUT"])
@login_required
@role_required("admin")
def api_ayarlar_kaydet():
    veri = ayarlari_kaydet(request.get_json(force=True))
    _kullanici_log("Ayar Güncelle", "Kapasiteler")
    return jsonify(veri)


# ── Çizelgeleme & Simülasyon ─────────────────────────────────

@app.route("/api/cizelgeleme", methods=["POST"])
@login_required
@role_required("admin", "ofis")
def api_cizelgeleme():
    global _son_cizelge
    _son_cizelge = _cizelgele(tum_siparisler())
    try:
        cizelge_kaydet(_son_cizelge)
    except Exception:
        pass
    if _son_cizelge["dar_bogaz_sayisi"] > 0:
        es = _son_cizelge.get("etiket_sayilari") or {}
        parcalar = []
        if es.get("sevk_gecikti"):
            parcalar.append(f"{es['sevk_gecikti']} sevk gecikti")
        if es.get("kapasite"):
            parcalar.append(f"{es['kapasite']} kapasite yetersiz")
        ozet = ", ".join(parcalar) if parcalar else "gecikme veya kapasite sorunu"
        bildirim_ekle(
            "dar_bogaz",
            "Çizelge Uyarısı",
            f"{_son_cizelge['dar_bogaz_sayisi']} işlemde sorun: {ozet}.",
        )
    _kullanici_log("Çizelgeleme", f"Sorun: {_son_cizelge['dar_bogaz_sayisi']}")
    return jsonify(_son_cizelge)


@app.route("/api/cizelgeleme/son", methods=["GET"])
@login_required
def api_son_cizelge():
    global _son_cizelge
    if _son_cizelge is None:
        _son_cizelge = cizelge_son_getir()
    if _son_cizelge is None:
        return jsonify({
            "gunler": [], "gantt": [], "gantt_gruplu": {}, "islem_sirasi": [],
            "dar_bogaz_sayisi": 0, "etiket_sayilari": {}, "uyarilar": [],
        })
    return jsonify(_son_cizelge)


@app.route("/api/simulasyon", methods=["POST"])
@login_required
@role_required("admin", "ofis")
def api_simulasyon():
    veri = request.get_json(force=True)
    mevcut = tum_siparisler()
    ek = veri.get("ek_siparisler", [])
    if veri.get("hizli_test"):
        ek.append({
            "musteri": veri.get("musteri", "Simülasyon"),
            "urun": veri.get("urun", "TEST"),
            "adet": str(veri.get("adet", 1000)),
            "hazir_adet": "0",
            "bitis": veri.get("bitis", datetime.now().strftime("%d.%m.%Y")),
            "durum": "Beklemede",
            "oncelik": veri.get("oncelik", "Normal"),
            "rotalar": veri.get("rotalar", "Kesim, Rodaj 1, Rodaj 2"),
            "istasyon_kapasiteleri": ayarlari_getir().get("varsayilan_kapasiteler", {}),
        })
    sonuc = _cizelgele(mevcut + ek)
    sonuc["simulasyon"] = True
    return jsonify(sonuc)


@app.route("/api/ai/kesim-oneri", methods=["POST", "GET"])
@login_required
@role_required("admin", "ofis")
def api_ai_kesim_oneri():
    """Yapay zeka kesim sıralama + günlük dağıtım önerisi (+ plaka verim)."""
    ayar = ayarlari_getir()
    bolum = (ayar.get("bolum_kapasiteleri") or {}).get("Kesim", 1500)
    veri = request.get_json(silent=True) or {}
    if request.method == "POST" and veri.get("bolum_kapasite"):
        bolum = int(veri["bolum_kapasite"])
    gun_sayisi = int(veri.get("gun_sayisi", 15)) if request.method == "POST" else 15
    siparisler = tum_siparisler()
    sip_map = {str(s["id"]): s for s in siparisler}
    plan = gunluk_kesim_plani(
        siparisler,
        bolum_kapasite=bolum,
        fire_oranlari=None,
        gun_sayisi=gun_sayisi,
    )

    toplam_plaka = 0
    eksik_olcu = 0
    for cam in plan.get("sira") or []:
        sip = sip_map.get(str(cam.get("siparis_id")))
        if not sip:
            cam["plaka"] = None
            continue
        try:
            oz = siparis_plaka_ozet(
                sip,
                kesim_adet=cam.get("kesilmesi_gereken"),
                plaka_boy=STANDART_PLAKA_BOY,
                plaka_en=STANDART_PLAKA_EN,
            )
            stok = None
            if oz.get("olcu_var") and oz.get("kalinlik"):
                stok = plaka_uygun_stok(
                    oz["cam_turu"], oz["kalinlik"], oz["plaka_boy"], oz["plaka_en"]
                )
            oz["stok_adet"] = int(stok["adet"]) if stok else 0
            oz["stok_yeterli"] = (
                oz["stok_adet"] >= oz["plaka_ihtiyac"] if oz["plaka_ihtiyac"] else True
            )
            once = (sip.get("uretim_detay") or {}).get("plaka_dusum") or {}
            oz["once_dusuldu"] = int(once.get("dusulen_plaka") or 0)
            cam["plaka"] = oz
            if oz.get("olcu_var") and oz.get("plaka_basi"):
                ekstra = max(0, oz["plaka_ihtiyac"] - oz["once_dusuldu"])
                toplam_plaka += ekstra
            elif not oz.get("olcu_var"):
                eksik_olcu += 1
        except Exception as e:
            cam["plaka"] = {
                "olcu_var": False,
                "plaka_basi": 0,
                "plaka_ihtiyac": 0,
                "stok_adet": 0,
                "hata": str(e),
            }
            eksik_olcu += 1

    plan["plaka_ozet"] = {
        "toplam_plaka_ihtiyac": toplam_plaka,
        "eksik_olcu": eksik_olcu,
        "standart": f"{int(STANDART_PLAKA_BOY)}×{int(STANDART_PLAKA_EN)}",
    }
    plan["ai_oneriler"] = list(plan.get("ai_oneriler") or [])
    plan["ai_oneriler"].append(
        f"Plaka: standart {plan['plaka_ozet']['standart']} — kenar boşluk {KENAR_BOSLUK_MM:g} mm, "
        f"rodaj her kenara 2×. Bu plandan ~{toplam_plaka} plaka düşülecek "
        f"(daha önce düşülenler hariç). Satırdaki «Şema» ile yerleşimi görün."
    )
    if eksik_olcu:
        plan["ai_oneriler"].append(
            f"⚠ {eksik_olcu} siparişte boy/en yok — plaka hesabı yapılamadı."
        )

    _kullanici_log("AI Kesim Öneri", f"{plan['ozet']['cam_sayisi']} cam, fire dahil")
    return jsonify(plan)


@app.route("/api/ai/plaka-dus", methods=["POST"])
@login_required
@role_required("admin", "ofis")
def api_ai_plaka_dus():
    """AI kesim planındaki siparişler için stoktan plaka düşer."""
    veri = request.get_json(force=True) or {}
    zorla = bool(veri.get("zorla"))  # Daha önce düşülenleri yeniden hesapla / fark düş
    from ai_planner import _kesimde_mi
    from fire import siparis_kesim_ihtiyaci

    dusulenler = []
    atlananlar = []
    hatalar = []

    # Önce tüm ihtiyaçları hesapla (stok yoksa hiç düşme — atomik his)
    ihtiyaclar = []
    for sip in tum_siparisler():
        if not _kesimde_mi(sip):
            continue
        ihtiyac = siparis_kesim_ihtiyaci(sip)
        kes = int(ihtiyac.get("kesilmesi_gereken") or 0)
        if kes <= 0:
            continue
        oz = siparis_plaka_ozet(sip, kesim_adet=kes)
        if not oz.get("olcu_var") or not oz.get("plaka_basi"):
            atlananlar.append({
                "siparis_id": sip["id"],
                "neden": oz.get("hata") or "Boy/en veya plaka verimi yok",
            })
            continue
        once = (sip.get("uretim_detay") or {}).get("plaka_dusum") or {}
        once_adet = int(once.get("dusulen_plaka") or 0)
        hedef = oz["plaka_ihtiyac"]
        if not zorla and once_adet >= hedef:
            atlananlar.append({
                "siparis_id": sip["id"],
                "neden": f"Zaten {once_adet} plaka düşülmüş",
            })
            continue
        ekstra = hedef if zorla and not once_adet else max(0, hedef - once_adet)
        if ekstra <= 0:
            continue
        ihtiyaclar.append({
            "sip": sip,
            "oz": oz,
            "ekstra": ekstra,
            "hedef": hedef,
            "once_adet": once_adet,
            "kes": kes,
        })

    # Stok yeterliliğini ön kontrol
    for it in ihtiyaclar:
        oz = it["oz"]
        try:
            stok = plaka_uygun_stok(oz["cam_turu"], oz["kalinlik"], oz["plaka_boy"], oz["plaka_en"])
            mevcut = int(stok["adet"]) if stok else 0
            if mevcut < it["ekstra"]:
                hatalar.append(
                    f"{it['sip']['musteri']}/{it['sip']['urun']}: "
                    f"gerekli +{it['ekstra']}, stok {mevcut} "
                    f"({oz['cam_turu']} {oz['kalinlik']} mm)"
                )
        except Exception as e:
            hatalar.append(str(e))

    if hatalar:
        return jsonify({
            "hata": "Stok yetersiz — hiçbir plaka düşülmedi.",
            "detay": hatalar,
            "atlananlar": atlananlar,
        }), 400

    for it in ihtiyaclar:
        sip, oz = it["sip"], it["oz"]
        try:
            kull = oturum_kullanicisi() or {}
            sonuc = plaka_stok_dus(
                oz["cam_turu"], oz["kalinlik"], it["ekstra"],
                oz["plaka_boy"], oz["plaka_en"],
                siparis_id=str(sip["id"]),
                kullanici=kull.get("kullanici_adi") or kull.get("ad") or "",
                neden=f"AI kesim · {sip.get('musteri')}/{sip.get('urun')}",
            )
            once_hareket = list(
                ((sip.get("uretim_detay") or {}).get("plaka_dusum") or {}).get("hareket_idler") or []
            )
            if sonuc.get("hareket_id"):
                once_hareket.append(sonuc["hareket_id"])
            dusum = {
                "dusulen_plaka": it["once_adet"] + it["ekstra"],
                "bu_islem": it["ekstra"],
                "plaka_basi": oz["plaka_basi"],
                "kesilecek_adet": it["kes"],
                "rodaj_mm": oz["rodaj_mm"],
                "kesim_boy": oz["kesim_boy"],
                "kesim_en": oz["kesim_en"],
                "cam_turu": oz["cam_turu"],
                "kalinlik": oz["kalinlik"],
                "plaka_boy": oz["plaka_boy"],
                "plaka_en": oz["plaka_en"],
                "zaman": datetime.now().isoformat(timespec="seconds"),
                "stok_kalan": sonuc.get("kalan"),
                "hareket_id": sonuc.get("hareket_id"),
                "hareket_idler": once_hareket,
            }
            siparis_plaka_dusum_kaydet(sip["id"], dusum)
            dusulenler.append({
                "siparis_id": sip["id"],
                "musteri": sip["musteri"],
                "urun": sip["urun"],
                **dusum,
            })
        except ValueError as e:
            hatalar.append(str(e))

    if hatalar and not dusulenler:
        return jsonify({"hata": "Düşüm yapılamadı", "detay": hatalar}), 400

    _kullanici_log(
        "Plaka Stok Düşüm",
        f"{len(dusulenler)} sipariş · "
        f"{sum(d['bu_islem'] for d in dusulenler)} plaka",
    )
    return jsonify({
        "mesaj": f"{sum(d['bu_islem'] for d in dusulenler)} plaka stoktan düşüldü.",
        "dusulenler": dusulenler,
        "atlananlar": atlananlar,
        "hatalar": hatalar,
        "ozet": plaka_ozet(),
    })


@app.route("/api/plaka-hesap", methods=["POST"])
@login_required
def api_plaka_hesap():
    """Sipariş formu önizlemesi: rodaj + kenar boşluk + yerleşim SVG."""
    veri = request.get_json(force=True) or {}
    kenar = veri.get("kenar_bosluk_mm")
    if kenar is None or kenar == "":
        kenar = KENAR_BOSLUK_MM
    sip = {
        "adet": veri.get("adet", 0),
        "hazir_adet": veri.get("hazir_adet", 0),
        "olcu": veri.get("olcu", ""),
        "uretim_detay": {
            "boy": veri.get("boy"),
            "en": veri.get("en"),
            "kalinlik": veri.get("kalinlik"),
            "cam_turu": veri.get("cam_turu"),
            "rodaj_pay_mm": veri.get("rodaj_pay_mm", 0),
            "kenar_bosluk_mm": kenar,
            "plaka_boy": veri.get("plaka_boy"),
            "plaka_en": veri.get("plaka_en"),
            "kesim_plani_dosya": veri.get("kesim_plani_dosya") or "",
        },
    }
    oz = siparis_plaka_ozet(
        sip,
        kesim_adet=veri.get("kesim_adet"),
        plaka_boy=float(veri.get("plaka_boy") or STANDART_PLAKA_BOY),
        plaka_en=float(veri.get("plaka_en") or STANDART_PLAKA_EN),
        kenar_bosluk=float(kenar),
        svg=bool(veri.get("svg", True)),
    )
    if oz.get("olcu_var") and oz.get("kalinlik"):
        stok = plaka_uygun_stok(oz["cam_turu"], oz["kalinlik"], oz["plaka_boy"], oz["plaka_en"])
        oz["stok_adet"] = int(stok["adet"]) if stok else 0
    else:
        oz["stok_adet"] = 0
    return jsonify(oz)


@app.route("/api/siparisler/<siparis_id>/kesim-sema", methods=["GET"])
@login_required
def api_kesim_sema(siparis_id):
    """Sipariş için optimize kesim şeması (SVG)."""
    sip = siparis_getir(siparis_id)
    if not sip:
        return jsonify({"hata": "Sipariş bulunamadı."}), 404
    from fire import siparis_kesim_ihtiyaci
    kes = siparis_kesim_ihtiyaci(sip).get("kesilmesi_gereken")
    oz = siparis_plaka_ozet(sip, kesim_adet=kes, svg=True)
    return jsonify(oz)


ALLOWED_KESIM_EXT = {".dxf", ".dwg", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}


@app.route("/api/siparisler/<siparis_id>/kesim-plani", methods=["POST"])
@login_required
@role_required("admin", "ofis")
def api_kesim_plani_yukle(siparis_id):
    """AutoCAD (DXF/DWG) veya PDF/görsel kesim planı yükler."""
    sip = siparis_getir(siparis_id)
    if not sip:
        return jsonify({"hata": "Sipariş bulunamadı."}), 404
    f = request.files.get("dosya")
    if not f or not f.filename:
        return jsonify({"hata": "Dosya seçilmedi."}), 400
    from werkzeug.utils import secure_filename
    ad = secure_filename(f.filename)
    ext = os.path.splitext(ad)[1].lower()
    if ext not in ALLOWED_KESIM_EXT:
        return jsonify({
            "hata": f"İzin verilen: {', '.join(sorted(ALLOWED_KESIM_EXT))}",
        }), 400
    sid_safe = secure_filename(siparis_id) or "siparis"
    klasor = os.path.join("yedekler", "kesim_planlari", sid_safe)
    os.makedirs(klasor, exist_ok=True)
    for eski in os.listdir(klasor):
        try:
            os.remove(os.path.join(klasor, eski))
        except OSError:
            pass
    hedef_ad = f"kesim_plani{ext}"
    yol = os.path.join(klasor, hedef_ad)
    f.save(yol)
    detay = dict(sip.get("uretim_detay") or {})
    rel = f"yedekler/kesim_planlari/{sid_safe}/{hedef_ad}".replace("\\", "/")
    detay["kesim_plani_dosya"] = rel
    detay["kesim_plani_orijinal"] = ad
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
    guncel = siparis_guncelle(siparis_id, veri)
    _kullanici_log("Kesim Planı Yükle", ad, siparis_id)
    return jsonify({
        "mesaj": "Kesim planı yüklendi.",
        "dosya": rel,
        "orijinal": ad,
        "siparis": guncel,
    })


@app.route("/api/siparisler/<siparis_id>/kesim-plani", methods=["GET"])
@login_required
def api_kesim_plani_indir(siparis_id):
    sip = siparis_getir(siparis_id)
    if not sip:
        return jsonify({"hata": "Sipariş bulunamadı."}), 404
    rel = (sip.get("uretim_detay") or {}).get("kesim_plani_dosya") or ""
    if not rel or not os.path.isfile(rel):
        return jsonify({"hata": "Yüklenmiş kesim planı yok."}), 404
    orijinal = (sip.get("uretim_detay") or {}).get("kesim_plani_orijinal") or os.path.basename(rel)
    return send_file(rel, as_attachment=True, download_name=orijinal)


@app.route("/api/siparisler/<siparis_id>/kesim-plani", methods=["DELETE"])
@login_required
@role_required("admin", "ofis")
def api_kesim_plani_sil(siparis_id):
    sip = siparis_getir(siparis_id)
    if not sip:
        return jsonify({"hata": "Sipariş bulunamadı."}), 404
    rel = (sip.get("uretim_detay") or {}).get("kesim_plani_dosya") or ""
    if rel and os.path.isfile(rel):
        try:
            os.remove(rel)
        except OSError:
            pass
    detay = dict(sip.get("uretim_detay") or {})
    detay.pop("kesim_plani_dosya", None)
    detay.pop("kesim_plani_orijinal", None)
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
    siparis_guncelle(siparis_id, veri)
    return jsonify({"mesaj": "Kesim planı silindi."})


# ── Log & Bildirim ───────────────────────────────────────────

@app.route("/api/log")
@login_required
@role_required("admin", "ofis")
def api_log():
    return jsonify(log_listele())


@app.route("/api/bildirimler")
@login_required
def api_bildirimler():
    return jsonify(bildirimler_listele(okunmamis_only=request.args.get("okunmamis") == "1"))


@app.route("/api/bildirimler/<int:bid>/oku", methods=["POST"])
@login_required
def api_bildirim_oku(bid):
    bildirim_okundu(bid)
    return jsonify({"mesaj": "OK"})


@app.route("/api/bildirimler/oku-tumu", methods=["POST"])
@login_required
def api_bildirim_oku_tumu():
    bildirim_tumunu_oku()
    return jsonify({"mesaj": "OK"})


# ── Yedekleme ────────────────────────────────────────────────

@app.route("/api/yedek", methods=["POST"])
@login_required
@role_required("admin")
def api_yedek_al():
    yol = yedek_al()
    _kullanici_log("Yedek", os.path.basename(yol))
    return jsonify({"mesaj": "Yedek alındı.", "dosya": os.path.basename(yol)})


@app.route("/api/yedek", methods=["GET"])
@login_required
@role_required("admin")
def api_yedek_liste():
    return jsonify(yedekleri_listele())


@app.route("/api/yedek/geri-yukle", methods=["POST"])
@login_required
@role_required("admin")
def api_yedek_geri():
    dosya = request.get_json(force=True).get("dosya")
    yedekten_geri_yukle(dosya)
    _kullanici_log("Geri Yükle", dosya)
    return jsonify({"mesaj": "Geri yüklendi."})


# ── Raporlar ─────────────────────────────────────────────────

@app.route("/siparis/<siparis_id>/etiket")
@login_required
def etiket_sayfa(siparis_id):
    # Eski etiket linki Fr.44 iş emrine yönlendirilir
    q = "?print=1" if request.args.get("print") else ""
    return redirect(url_for("is_emri_sayfa", siparis_id=siparis_id) + q)


@app.route("/siparis/<siparis_id>/is-emri")
@login_required
def is_emri_sayfa(siparis_id):
    sip = siparis_getir(siparis_id)
    if not sip:
        return "Sipariş bulunamadı", 404
    detay = sip.get("uretim_detay") or {}
    # olcu'dan boy/en/kalinlik çıkar (boşsa)
    if not detay.get("boy") and sip.get("olcu"):
        import re
        m = re.split(r"[xX×*]", str(sip["olcu"]))
        if len(m) >= 2:
            detay.setdefault("boy", m[0].strip())
            detay.setdefault("en", m[1].strip())
            if len(m) >= 3:
                detay.setdefault("kalinlik", m[2].strip())
    return render_template(
        "is_emri.html",
        siparis=sip,
        detay=detay,
        bugun=datetime.now().strftime("%d.%m.%Y"),
        kullanici=oturum_kullanicisi(),
        logo_byc=LOGO_BYC_B64,
        logo_united=LOGO_UNITED_B64,
        olcu_sema=OLCU_SEMA_B64,
    )


@app.route("/api/rapor/pdf")
@login_required
@role_required("admin", "ofis")
def api_rapor_pdf():
    liste = tum_siparisler()
    asama_map = asama_ozetleri_toplu([s["id"] for s in liste])
    pdf = haftalik_pdf(liste, _son_cizelge, kpi_ozet(), asama_map=asama_map)
    buf = io.BytesIO(pdf)
    return send_file(buf, as_attachment=True,
                     download_name=f"BYC_Rapor_{datetime.now().strftime('%Y%m%d')}.pdf",
                     mimetype="application/pdf")


@app.route("/api/siparisler/<siparis_id>/pdf")
@login_required
@role_required("admin", "ofis")
def api_siparis_pdf(siparis_id):
    sip = siparis_getir(siparis_id)
    if not sip:
        return jsonify({"hata": "Bulunamadı."}), 404
    pdf = siparis_detay_pdf(sip, asama_ozet(siparis_id))
    buf = io.BytesIO(pdf)
    ad = f"siparis_{sip.get('urun','detay')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(buf, as_attachment=True, download_name=ad, mimetype="application/pdf")


# ── Excel ────────────────────────────────────────────────────

@app.route("/api/excel/disari", methods=["GET"])
@login_required
@role_required("admin", "ofis")
def api_excel_disari():
    siparisler = tum_siparisler()
    if not siparisler:
        return jsonify({"hata": "Aktarılacak sipariş yok."}), 400
    buf = io.BytesIO()
    pd.DataFrame(siparisler).to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"siparisler_{datetime.now().strftime('%Y%m%d')}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/excel/cizelge", methods=["GET"])
@login_required
def api_excel_cizelge():
    if not _son_cizelge or not _son_cizelge.get("gunler"):
        return jsonify({"hata": "Önce çizelgeleme çalıştırın."}), 400
    rows = [{"Tarih": g["gun"], **k} for g in _son_cizelge["gunler"] for k in g["kayitlar"]]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"cizelge_{datetime.now().strftime('%Y%m%d')}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/excel/iceri", methods=["POST"])
@login_required
@role_required("admin", "ofis")
def api_excel_iceri():
    if "dosya" not in request.files:
        return jsonify({"hata": "Dosya seçilmedi."}), 400
    df = pd.read_excel(request.files["dosya"])
    kap = ayarlari_getir().get("varsayilan_kapasiteler", {})
    for _, r in df.iterrows():
        siparis_ekle({
            "musteri": str(r.get("Müşteri", "Bilinmeyen")),
            "urun": str(r.get("Ürün Kodu", "GENEL")),
            "olcu": str(r.get("Ölçü", "-")),
            "adet": str(r.get("Adet", 100)),
            "istasyon_kapasiteleri": kap,
            "hazir_adet": str(r.get("Sevk Edilen", 0)),
            "bitis": str(r.get("Sevk Hedefi", datetime.now().strftime("%d.%m.%Y"))),
            "durum": str(r.get("Durum", "Beklemede")),
            "oncelik": str(r.get("Öncelik", "Normal")),
            "rotalar": str(r.get("Rota", "Kesim, Rodaj 1, Rodaj 2, Isıl Temper")),
        })
    _kullanici_log("Excel İçe Aktar", f"{len(df)} sipariş")
    return jsonify({"mesaj": f"{len(df)} sipariş aktarıldı."})


# ── Kullanıcı & Sürüm ────────────────────────────────────────

@app.route("/api/kullanicilar")
@login_required
@role_required("admin")
def api_kullanicilar():
    return jsonify(tum_kullanicilar())


@app.route("/api/sifre-degistir", methods=["POST"])
@login_required
def api_sifre_degistir():
    v = request.get_json(force=True)
    k = oturum_kullanicisi()
    kullanici_sifre_degistir(k["id"], v.get("yeni_sifre", ""))
    return jsonify({"mesaj": "Şifre değiştirildi."})


@app.route("/api/version")
def api_version():
    return jsonify({"version": APP_VERSION, "title": APP_TITLE})


# ── Başlat ───────────────────────────────────────────────────

def baslat():
    global _son_cizelge
    init_db()
    _son_cizelge = cizelge_son_getir()
    otomatik_yedek_baslat()
    try:
        yedek_al()
    except Exception:
        pass

    ssl_cert = os.path.join("ssl", "cert.pem")
    ssl_key = os.path.join("ssl", "key.pem")
    use_ssl = os.path.exists(ssl_cert) and os.path.exists(ssl_key)

    print(f"\n{'='*55}")
    print(f"  {APP_TITLE} v{APP_VERSION}")
    print(f"{'='*55}")
    proto = "https" if use_ssl else "http"
    print(f"  Bilgisayar:  {proto}://localhost:{WEB_PORT}")
    print(f"  Ağ/Tablet:   {proto}://[IP-ADRESINIZ]:{WEB_PORT}")
    print(f"  Mobil:       {proto}://[IP-ADRESINIZ]:{WEB_PORT}/mobile")
    print(f"{'='*55}")
    print("  Varsayılan giriş: admin / admin123")
    print(f"{'='*55}\n")

    if use_ssl:
        app.run(host=WEB_HOST, port=WEB_PORT, debug=False, threaded=True,
                ssl_context=(ssl_cert, ssl_key))
    else:
        try:
            from waitress import serve
            serve(app, host=WEB_HOST, port=WEB_PORT, threads=8)
        except ImportError:
            app.run(host=WEB_HOST, port=WEB_PORT, debug=False, threaded=True)


if __name__ == "__main__":
    baslat()
