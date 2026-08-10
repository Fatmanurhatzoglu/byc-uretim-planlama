"""
Kesim için AI planlama önerisi motoru.

- cam_gunluk_hiz: Her camın kendi günlük kesim limiti
- bolum_kapasite: Kesim bölümü toplam kapasitesi (örn. 1500)
- fire: Sonraki işlem fire oranları → net siparişten FAZLA kesilir
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from config import BOLUM_KAPASITELERI, ONCELIK_SIRASI, VARSAYILAN_FIRE_ORANLARI
from fire import siparis_kesim_ihtiyaci
from scheduler import sonraki_uygun_gun, tarih_etiketi


@dataclass
class CamOneri:
    siparis_id: str
    musteri: str
    urun: str
    olcu: str
    net_kalan: int          # sevk edilecek net kalan
    kesilmesi_gereken: int  # fire dahil kesim hedefi
    fire_adet: int
    fire_carpan: float
    fire_ozet: str
    cam_gunluk_hiz: int
    oncelik: str
    sevk_hedef: str
    sira: int
    neden: str
    tahmini_gun: int
    fire_adimlar: list = field(default_factory=list)
    fire_pct_ozet: str = ""
    fire_kaynak: str = ""


@dataclass
class GunlukKesim:
    tarih: str
    bolum_kapasite: int
    kullanilan: int
    kalan_kapasite: int
    satirlar: list = field(default_factory=list)


def _net_kalan(sip: dict) -> int:
    return max(0, int(sip.get("adet", 0)) - int(sip.get("hazir_adet", 0)))


def _cam_hiz(sip: dict) -> int:
    kap = sip.get("istasyon_kapasiteleri") or {}
    hiz = kap.get("Kesim")
    if hiz is None:
        return max(50, BOLUM_KAPASITELERI.get("Kesim", 1500) // 5)
    return max(1, int(hiz))


def _oncelik_skoru(sip: dict, bugun: datetime, kesim_hedef: int) -> tuple:
    oncelik = ONCELIK_SIRASI.get(sip.get("oncelik", "Normal"), 1)
    try:
        sevk = datetime.strptime(sip.get("bitis", ""), "%d.%m.%Y")
        kalan_gun = (sevk.date() - bugun.date()).days
    except ValueError:
        kalan_gun = 9999
    return (oncelik, kalan_gun, -kesim_hedef, sip.get("musteri", ""))


def _kesimde_mi(sip: dict) -> bool:
    if sip.get("durum") == "Tamamlandı":
        return False
    if _net_kalan(sip) <= 0:
        return False
    rotalar = [x.strip() for x in (sip.get("rotalar") or "").split(",") if x.strip()]
    return "Kesim" in rotalar or not rotalar


def camlari_sirala(
    siparisler: list,
    fire_oranlari: Optional[dict] = None,
    bugun: Optional[datetime] = None,
) -> list[CamOneri]:
    bugun = bugun or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # Global fire sadece siparişte fire YOKSA yedek olarak kullanılır (fire.py içinde)
    fire_yedek = fire_oranlari  # None olabilir

    hazir = []
    for sip in siparisler:
        if not _kesimde_mi(sip):
            continue
        ihtiyac = siparis_kesim_ihtiyaci(sip, fire_yedek)
        hazir.append((sip, ihtiyac))

    hazir.sort(key=lambda x: _oncelik_skoru(x[0], bugun, x[1]["kesilmesi_gereken"]))

    sonuc = []
    for i, (sip, ihtiyac) in enumerate(hazir, start=1):
        hiz = _cam_hiz(sip)
        hedef = ihtiyac["kesilmesi_gereken"]
        tahmini = (hedef + hiz - 1) // hiz if hiz else 0
        try:
            sevk = datetime.strptime(sip.get("bitis", ""), "%d.%m.%Y")
            kalan_gun = (sevk.date() - bugun.date()).days
        except ValueError:
            kalan_gun = 9999

        neden = []
        if sip.get("oncelik") == "Acil":
            neden.append("Acil öncelik")
        if kalan_gun <= 7:
            neden.append(f"Sevk {kalan_gun} gün içinde")
        if ihtiyac["fire_adet"] > 0:
            neden.append(f"Fire dahil +{ihtiyac['fire_adet']} adet")
        if not neden:
            neden.append("Normal sırada")

        fire_pct_ozet = " · ".join(
            f"{a['istasyon']} %{a['fire_yuzde']}" for a in (ihtiyac.get("adimlar") or [])
        )

        sonuc.append(CamOneri(
            siparis_id=str(sip.get("id", "")),
            musteri=sip.get("musteri", ""),
            urun=sip.get("urun", ""),
            olcu=sip.get("olcu", ""),
            net_kalan=ihtiyac["net_adet"],
            kesilmesi_gereken=hedef,
            fire_adet=ihtiyac["fire_adet"],
            fire_carpan=ihtiyac["fire_carpan"],
            fire_ozet=ihtiyac["ozet"],
            cam_gunluk_hiz=hiz,
            oncelik=sip.get("oncelik", "Normal"),
            sevk_hedef=sip.get("bitis", ""),
            sira=i,
            neden=" · ".join(neden),
            tahmini_gun=tahmini,
            fire_adimlar=ihtiyac.get("adimlar", []),
            fire_pct_ozet=fire_pct_ozet,
            fire_kaynak=ihtiyac.get("kaynak", ""),
        ))
    return sonuc


def gunluk_kesim_plani(
    siparisler: list,
    bolum_kapasite: Optional[int] = None,
    fire_oranlari: Optional[dict] = None,
    gun_sayisi: int = 15,
    bugun: Optional[datetime] = None,
) -> dict:
    bugun = bugun or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    bolum = int(bolum_kapasite or BOLUM_KAPASITELERI.get("Kesim", 1500))

    sirali = camlari_sirala(siparisler, fire_oranlari, bugun)
    # Planlanan hedef = fire dahil kesim adedi
    kalan_map = {c.siparis_id: c.kesilmesi_gereken for c in sirali}
    hiz_map = {c.siparis_id: c.cam_gunluk_hiz for c in sirali}
    meta = {c.siparis_id: c for c in sirali}

    gunler: list[GunlukKesim] = []
    ofset = 1
    while ofset <= gun_sayisi and any(v > 0 for v in kalan_map.values()):
        hedef_gun = sonraki_uygun_gun(bugun, ofset, "Kesim")
        gun_str = tarih_etiketi(hedef_gun)
        kalan_kap = bolum
        satirlar = []

        for cam in sirali:
            if kalan_kap <= 0:
                break
            sid = cam.siparis_id
            if kalan_map.get(sid, 0) <= 0:
                continue
            plan = min(kalan_map[sid], hiz_map[sid], kalan_kap)
            if plan <= 0:
                continue
            kalan_map[sid] -= plan
            kalan_kap -= plan
            satirlar.append({
                "siparis_id": sid,
                "musteri": meta[sid].musteri,
                "urun": meta[sid].urun,
                "olcu": meta[sid].olcu,
                "sira": meta[sid].sira,
                "adet": plan,
                "cam_gunluk_hiz": hiz_map[sid],
                "net_kalan": meta[sid].net_kalan,
                "fire_adet": meta[sid].fire_adet,
                "kalan_sonra": kalan_map[sid],
                "not": (
                    f"Fire dahil hedef; cam hızı {hiz_map[sid]}/gün"
                ),
            })

        if satirlar:
            gunler.append(GunlukKesim(
                tarih=gun_str,
                bolum_kapasite=bolum,
                kullanilan=bolum - kalan_kap,
                kalan_kapasite=kalan_kap,
                satirlar=satirlar,
            ))
        ofset += 1

    tamamlanamayan = [
        {
            "siparis_id": sid,
            "musteri": meta[sid].musteri,
            "urun": meta[sid].urun,
            "kalan_kesim": kalan_map[sid],
            "net_kalan": meta[sid].net_kalan,
            "oneri": (
                f"Fire dahil {meta[sid].kesilmesi_gereken} kesilmeliydi "
                f"(net {meta[sid].net_kalan} + fire {meta[sid].fire_adet}). "
                f"Cam hızını veya bölüm kapasitesini artırın."
            ),
        }
        for sid, kalan in kalan_map.items() if kalan > 0
    ]

    toplam_net = sum(c.net_kalan for c in sirali)
    toplam_kesim = sum(c.kesilmesi_gereken for c in sirali)
    toplam_fire = sum(c.fire_adet for c in sirali)

    oneriler = [
        "Kesim adedi = sipariş (net) adedi değildir. Sonraki işlem fire oranları eklenir.",
        f"Toplam net sevk ihtiyacı: {toplam_net} · Fire dahil kesilecek: {toplam_kesim} (+{toplam_fire}).",
        f"Kesim bölümü kapasitesi: {bolum} adet/gün. Her cam ayrıca kendi günlük hızıyla sınırlıdır.",
    ]
    if sirali:
        oneriler.append(
            f"İlk sırada: {sirali[0].musteri} / {sirali[0].urun} — "
            f"net {sirali[0].net_kalan} → kesim {sirali[0].kesilmesi_gereken} ({sirali[0].neden})."
        )
        if sirali[0].fire_adimlar:
            zincir = " → ".join(
                f"{a['istasyon']} %{a['fire_yuzde']}" for a in sirali[0].fire_adimlar
            )
            oneriler.append(f"Örnek fire zinciri (1. sipariş): {zincir}")

    if tamamlanamayan:
        oneriler.append(
            f"🚨 {len(tamamlanamayan)} cam {gun_sayisi} günde fire-dahil hedefe ulaşamıyor."
        )

    return {
        "bolum": "Kesim",
        "bolum_kapasite": bolum,
        "fire_oranlari": "siparis_bazli",
        "aciklama": {
            "net_adet": "Müşteriye sevk edilecek sipariş kalanı",
            "kesilmesi_gereken": "Sonraki işlem fire'leri eklendikten sonra kesilmesi gereken adet",
            "cam_gunluk_hiz": "Bu camın günlük kesim limiti",
            "bolum_kapasite": "Kesim bölümünün toplam günlük kapasitesi",
        },
        "sira": [asdict(c) for c in sirali],
        "gunler": [asdict(g) for g in gunler],
        "tamamlanamayan": tamamlanamayan,
        "ai_oneriler": oneriler,
        "ozet": {
            "cam_sayisi": len(sirali),
            "planlanan_gun": len(gunler),
            "toplam_net": toplam_net,
            "toplam_kesim_hedef": toplam_kesim,
            "toplam_fire": toplam_fire,
            "ort_cam_hizi": round(sum(c.cam_gunluk_hiz for c in sirali) / len(sirali), 1) if sirali else 0,
        },
    }
