"""
Fire (hurda/kayıp) hesabı.

Sipariş adedi = sevk edilecek NET adet.
Kesimde daha fazla kesilir çünkü sonraki istasyonlarda fire vardır.

Örnek: Net 1000, Rodaj %2.5, Temper %3
  Temper girişi = 1000 / 0.97
  Rodaj girişi  = ... / 0.975
  → Kesilmesi gereken ≈ 1057

Not: Rodaj 1 + Rodaj 2 paralel aynı süreç adımıdır; fire bir kez uygulanır.
"""

from __future__ import annotations

import math
from typing import Optional

from config import VARSAYILAN_FIRE_ORANLARI
from rota_utils import fire_adimlari, fire_orani_adim, normalize_rota


def rota_listesi(sip: dict) -> list[str]:
    return normalize_rota(sip.get("rotalar") or "")


def sonraki_istasyonlar(rotalar: list[str], baslangic: str = "Kesim") -> list[str]:
    """Kesim'den sonra gelen istasyonlar (fire bunlar için uygulanır).

    Paralel gruplar (Rodaj 1+Rodaj 2) tek fire adımıdır.
    """
    adimlar = fire_adimlari(rotalar)
    if baslangic in adimlar:
        i = adimlar.index(baslangic)
        return adimlar[i + 1 :]
    # "Kesim" yoksa tüm (normalize edilmiş) adımlar
    return adimlar[:]


def fire_ile_gerekli_adet(
    net_adet: int,
    rotalar: list[str],
    fire_oranlari: Optional[dict] = None,
    baslangic: str = "Kesim",
    kesim_fire_dahil: bool = True,
) -> dict:
    """
    Net sevk ihtiyacından geriye doğru çalışarak kesim (veya başlangıç) adedini bulur.

    Dönüş:
      net_adet, kesilmesi_gereken, fire_adet, carpim, adimlar[{istasyon, fire_%, once, sonra}]
    """
    net = max(0, int(net_adet))
    oranlar = fire_oranlari or dict(VARSAYILAN_FIRE_ORANLARI)

    # Kesim'den sonraki istasyonlar (+ isteğe bağlı Kesim fire'si)
    sonrasi = sonraki_istasyonlar(rotalar, baslangic)
    uygulanacak = []
    adimlar_norm = fire_adimlari(rotalar)
    if kesim_fire_dahil and baslangic in adimlar_norm:
        uygulanacak.append(baslangic)
    uygulanacak.extend(sonrasi)

    # Geriye doğru: sondan başa
    mevcut = float(net)
    adimlar_ters = []
    for istasyon in reversed(uygulanacak):
        fire_pct = fire_orani_adim(istasyon, oranlar)
        fire_pct = max(0.0, min(fire_pct, 80.0))  # güvenlik üst sınır
        verim = max(0.01, 1.0 - fire_pct / 100.0)
        once = mevcut / verim
        adimlar_ters.append({
            "istasyon": istasyon,
            "fire_yuzde": round(fire_pct, 2),
            "verim": round(verim * 100, 2),
            "cikis_adet": math.ceil(mevcut),
            "giris_adet": math.ceil(once),
        })
        mevcut = once

    adimlar = list(reversed(adimlar_ters))
    kesilmesi = math.ceil(mevcut) if net > 0 else 0
    fire_adet = max(0, kesilmesi - net)
    carpim = (kesilmesi / net) if net > 0 else 1.0

    return {
        "net_adet": net,
        "kesilmesi_gereken": kesilmesi,
        "fire_adet": fire_adet,
        "fire_carpan": round(carpim, 4),
        "uygulanan_istasyonlar": uygulanacak,
        "adimlar": adimlar,
        "ozet": (
            f"Net {net} → fire dahil {kesilmesi} kesilmeli "
            f"(+{fire_adet} adet, ×{carpim:.3f})"
            if net > 0 else "Net adet yok"
        ),
    }


def siparis_kesim_ihtiyaci(
    sip: dict,
    fire_oranlari: Optional[dict] = None,
) -> dict:
    """Siparişteki fire oranları kullanılır; yoksa varsayılan/global."""
    net = max(0, int(sip.get("adet", 0)) - int(sip.get("hazir_adet", 0)))
    rotalar = rota_listesi(sip)

    sip_fire = sip.get("fire_oranlari") or {}
    if isinstance(sip_fire, str):
        import json
        sip_fire = json.loads(sip_fire or "{}")

    oranlar = dict(VARSAYILAN_FIRE_ORANLARI)
    if fire_oranlari:
        oranlar.update({k: float(v) for k, v in fire_oranlari.items() if v is not None})

    # Sipariş fire oranları Varsa rota boyunca SADECE onlar geçerli (eksik istasyon = 0)
    if sip_fire:
        oranlar = {}
        for ist in rotalar:
            try:
                oranlar[ist] = float(sip_fire.get(ist, sip_fire.get("Rodaj", 0)) or 0)
            except (TypeError, ValueError):
                oranlar[ist] = 0.0
        kaynak = "siparis"
    else:
        kaynak = "global"

    hesap = fire_ile_gerekli_adet(net, rotalar, oranlar)
    hesap["musteri"] = sip.get("musteri", "")
    hesap["urun"] = sip.get("urun", "")
    hesap["siparis_id"] = str(sip.get("id", ""))
    hesap["rotalar"] = rotalar
    hesap["kaynak"] = kaynak
    hesap["uygulanan_fire"] = {
        ist: fire_orani_adim(ist, oranlar) for ist in fire_adimlari(rotalar)
    }
    return hesap
