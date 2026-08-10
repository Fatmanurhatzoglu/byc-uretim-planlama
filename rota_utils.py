"""Rota yardımcıları — paralel istasyon grupları (ör. Rodaj 1 / Rodaj 2).

Planner notu
------------
Rota metni hâlâ virgülle ayrılmış makine listesidir (sıralı görünür).
Ama aynı paralel gruba ait ardışık makineler (Rodaj 1, Rodaj 2) tek
işlem adımı sayılır: kalan adet günlük hızlara orantılı bölünür ve aynı
takvim günlerinde paralel planlanır. Yalnızca biri seçilirse sadece o
makine kullanılır. Eski tekil "Rodaj" adı her iki makineye genişletilir.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from config import PARALEL_GRUPLAR, TUM_MAKINELER

# Eski sipariş / ayar anahtarı → yeni paralel makineler
ESKI_RODAJ = "Rodaj"
YENI_RODAJLAR = ["Rodaj 1", "Rodaj 2"]

_PARALEL_UYELIK: dict[str, frozenset[str]] = {}
for _g in PARALEL_GRUPLAR:
    fs = frozenset(_g)
    for _m in fs:
        _PARALEL_UYELIK[_m] = fs


def paralel_grubu(makine: str) -> Optional[frozenset[str]]:
    """Makinenin ait olduğu paralel grubu (yoksa None)."""
    return _PARALEL_UYELIK.get(makine)


def rota_tokenleri(rotalar) -> list[str]:
    if isinstance(rotalar, (list, tuple)):
        return [str(x).strip() for x in rotalar if str(x).strip()]
    return [x.strip() for x in str(rotalar or "").split(",") if x.strip()]


def genislet_eski_rodaj(tokens: Sequence[str]) -> list[str]:
    """Tekil 'Rodaj' → Rodaj 1 + Rodaj 2 (zaten varsa tekrar ekleme)."""
    out: list[str] = []
    for t in tokens:
        if t == ESKI_RODAJ:
            for y in YENI_RODAJLAR:
                if y not in out:
                    out.append(y)
        else:
            out.append(t)
    return out


def normalize_rota(rotalar) -> list[str]:
    """Token listesi + eski Rodaj genişletme."""
    return genislet_eski_rodaj(rota_tokenleri(rotalar))


def rota_metni(tokens: Sequence[str]) -> str:
    return ", ".join(tokens)


def paralel_adimlar(rotalar) -> list[list[str]]:
    """Rotayı işlem adımlarına ayırır; her adım 1+ makine (paralel ise >1).

    Ardışık Rodaj 1 / Rodaj 2 tek adım olur. Çin Rodajı ayrı istasyondur.
    """
    tokens = normalize_rota(rotalar)
    adimlar: list[list[str]] = []
    i = 0
    while i < len(tokens):
        m = tokens[i]
        grup = paralel_grubu(m)
        if grup:
            uye: list[str] = []
            while i < len(tokens) and tokens[i] in grup:
                if tokens[i] not in uye:
                    uye.append(tokens[i])
                i += 1
            adimlar.append(uye)
        else:
            adimlar.append([m])
            i += 1
    return adimlar


def fire_adimlari(rotalar) -> list[str]:
    """Fire hesabında paralel grup tek istasyon gibi (etiket birleşik)."""
    out = []
    for adim in paralel_adimlar(rotalar):
        if len(adim) == 1:
            out.append(adim[0])
        else:
            out.append("+".join(adim))
    return out


def fire_orani_adim(adim_adi: str, oranlar: dict) -> float:
    """Birleşik 'Rodaj 1+Rodaj 2' için gruptaki oranların max'ı."""
    if "+" in adim_adi and adim_adi not in oranlar:
        parcalar = adim_adi.split("+")
        degerler = []
        for p in parcalar:
            try:
                degerler.append(float(oranlar.get(p, 0) or 0))
            except (TypeError, ValueError):
                degerler.append(0.0)
        # Eski tekil Rodaj oranı varsa onu da dene
        if ESKI_RODAJ in oranlar:
            try:
                degerler.append(float(oranlar.get(ESKI_RODAJ) or 0))
            except (TypeError, ValueError):
                pass
        return max(degerler) if degerler else 0.0
    try:
        return float(oranlar.get(adim_adi, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def kapasiteyi_bol(adet: int, agirliklar: Sequence[int]) -> list[int]:
    """Adedi ağırlıklara orantılı böler; toplam tam adet olur."""
    n = len(agirliklar)
    if n == 0:
        return []
    if adet <= 0:
        return [0] * n
    w = [max(0, int(x)) for x in agirliklar]
    if sum(w) <= 0:
        w = [1] * n
    toplam_w = sum(w)
    paylar = [int(adet * wi / toplam_w) for wi in w]
    fark = adet - sum(paylar)
    # Kalanı en yüksek ağırlıklıya ver
    sira = sorted(range(n), key=lambda i: w[i], reverse=True)
    i = 0
    while fark > 0 and sira:
        paylar[sira[i % n]] += 1
        fark -= 1
        i += 1
    return paylar


def sonraki_istasyon(rotalar: Sequence[str], istasyon: str) -> Optional[str]:
    """Çıkış sonrası otomatik aktarım hedefi — paralel kardeşleri atlar."""
    tokens = list(rotalar)
    if istasyon not in tokens:
        return None
    idx = tokens.index(istasyon)
    grup = paralel_grubu(istasyon)
    j = idx + 1
    if grup:
        while j < len(tokens) and tokens[j] in grup:
            j += 1
    if j >= len(tokens):
        return None
    return tokens[j]


def paralel_giris_hedefleri(rotalar: Sequence[str], istasyon: str) -> list[str]:
    """Bu istasyondan çıkışta girilecek makineler (paralel grup veya tek sonraki)."""
    tokens = list(rotalar)
    if istasyon not in tokens:
        return []
    idx = tokens.index(istasyon)
    j = idx + 1
    if j >= len(tokens):
        return []
    sonraki = tokens[j]
    grup = paralel_grubu(sonraki)
    if not grup:
        return [sonraki]
    hedefler: list[str] = []
    while j < len(tokens) and tokens[j] in grup:
        if tokens[j] not in hedefler:
            hedefler.append(tokens[j])
        j += 1
    return hedefler


def esle_kapasite_anahtarlari(kap: dict) -> dict:
    """'Rodaj' kapasite/fire anahtarını Rodaj 1 ve 2'ye kopyala."""
    if not isinstance(kap, dict):
        return {}
    out = dict(kap)
    if ESKI_RODAJ in out:
        eski_deger = out[ESKI_RODAJ]
        for y in YENI_RODAJLAR:
            if y not in out:
                out[y] = eski_deger
        del out[ESKI_RODAJ]
    # Eksik makineler için varsayılan ekleme çağıran tarafta yapılır
    return out


def makine_sirasi_ref() -> list[str]:
    return list(TUM_MAKINELER)


def sirali_secim(secilen: Iterable[str]) -> list[str]:
    """Seçili makineleri TUM_MAKINELER sırasına göre diz."""
    sec = set(genislet_eski_rodaj(list(secilen)))
    return [m for m in TUM_MAKINELER if m in sec]
