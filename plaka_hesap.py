"""
Cam plaka verim + kesim yerleşim şeması.

Kurallar:
- Plaka kenarlarından kenar_bosluk mm (varsayılan 20) boş bırakılır.
- Parça ölçüsü = bitmiş ölçü + (2 × rodaj) her eksende.
- Parçalar arası boşluk yok.
- İki yön + kenar fire şeridine döndürülmüş ek yerleştirme denenir; en çok adet seçilir.
"""

from __future__ import annotations

import math
from typing import Optional

STANDART_PLAKA_BOY = 3210.0
STANDART_PLAKA_EN = 2250.0
KENAR_BOSLUK_MM = 20.0


def _sayi(v, default: float = 0.0) -> float:
    if v is None or v == "":
        return default
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


def kesim_olculeri(boy: float, en: float, rodaj_mm: float) -> tuple[float, float]:
    """Bitmiş ölçü + her kenara rodaj → kesilecek boyut."""
    r = max(0.0, _sayi(rodaj_mm))
    return boy + 2.0 * r, en + 2.0 * r


def _grid(uw: float, uh: float, pw: float, ph: float) -> tuple[int, int, int]:
    if pw <= 0 or ph <= 0 or uw < pw or uh < ph:
        return 0, 0, 0
    sx = int(uw // pw)
    sy = int(uh // ph)
    return sx * sy, sx, sy


def _yerlesim_adetleri(
    uw: float,
    uh: float,
    pw: float,
    ph: float,
    ox: float,
    oy: float,
) -> dict:
    """
    Ana ızgara + sağ/alt fire şeridine döndürülmüş parça.

    ox, oy = kullanılabilir alanın sol-üst köşesi (plaka koordinatı).
    """
    adet_ana, sx, sy = _grid(uw, uh, pw, ph)
    parcalar: list[dict] = []
    for iy in range(sy):
        for ix in range(sx):
            parcalar.append({
                "x": round(ox + ix * pw, 2),
                "y": round(oy + iy * ph, 2),
                "w": round(pw, 2),
                "h": round(ph, 2),
                "donuk": False,
            })

    # Sağ şerit (tam yükseklik) — döndürülmüş
    rem_w = uw - sx * pw
    ekstra = 0
    if rem_w >= ph and uh >= pw:
        rx = int(rem_w // ph)
        ry = int(uh // pw)
        ekstra += rx * ry
        for iy in range(ry):
            for ix in range(rx):
                parcalar.append({
                    "x": round(ox + sx * pw + ix * ph, 2),
                    "y": round(oy + iy * pw, 2),
                    "w": round(ph, 2),
                    "h": round(pw, 2),
                    "donuk": True,
                })

    # Alt şerit — sadece ana ızgara genişliği (sağ köşe çift sayılmasın)
    rem_h = uh - sy * ph
    ana_w = sx * pw
    if rem_h >= pw and ana_w >= ph:
        bx = int(ana_w // ph)
        by = int(rem_h // pw)
        ekstra += bx * by
        for iy in range(by):
            for ix in range(bx):
                parcalar.append({
                    "x": round(ox + ix * ph, 2),
                    "y": round(oy + sy * ph + iy * pw, 2),
                    "w": round(ph, 2),
                    "h": round(pw, 2),
                    "donuk": True,
                })

    return {
        "adet": adet_ana + ekstra,
        "sutun": sx,
        "satir": sy,
        "ekstra_serit": ekstra,
        "parcalar": parcalar,
        "pw": pw,
        "ph": ph,
    }


def plakadan_kac_adet(
    plaka_boy: float,
    plaka_en: float,
    parca_boy: float,
    parca_en: float,
    rodaj_mm: float = 0.0,
    kenar_bosluk: float = KENAR_BOSLUK_MM,
) -> dict:
    """
    Kenar boşluklu, optimize ızgara + fire şeridi yerleşimi.
    """
    pb, pe = _sayi(plaka_boy), _sayi(plaka_en)
    boy, en = _sayi(parca_boy), _sayi(parca_en)
    rodaj = round(max(0.0, _sayi(rodaj_mm)), 2)
    kenar = max(0.0, _sayi(kenar_bosluk, KENAR_BOSLUK_MM))

    bos = {
        "adet": 0,
        "yon": "-",
        "kesim_boy": 0,
        "kesim_en": 0,
        "bitmis_boy": boy,
        "bitmis_en": en,
        "rodaj_mm": rodaj,
        "kenar_bosluk": kenar,
        "kullanilabilir_boy": 0,
        "kullanilabilir_en": 0,
        "satir": 0,
        "sutun": 0,
        "ekstra_serit": 0,
        "parcalar": [],
        "plaka_boy": pb,
        "plaka_en": pe,
        "hata": "Ölçüler eksik veya geçersiz",
        "verim_yuzde": 0.0,
    }

    if pb <= 0 or pe <= 0 or boy <= 0 or en <= 0:
        return bos

    uw = pb - 2.0 * kenar
    uh = pe - 2.0 * kenar
    if uw <= 0 or uh <= 0:
        bos["hata"] = "Kenar boşluğu plakadan büyük"
        bos["kullanilabilir_boy"] = round(uw, 2)
        bos["kullanilabilir_en"] = round(uh, 2)
        return bos

    kw, kh = kesim_olculeri(boy, en, rodaj)
    ox, oy = kenar, kenar

    # A: düz (kw×kh), B: döndürülmüş (kh×kw) — her ikisinde fire şeridi dene
    a = _yerlesim_adetleri(uw, uh, kw, kh, ox, oy)
    b = _yerlesim_adetleri(uw, uh, kh, kw, ox, oy)

    # Saf ızgara (şerit yok) yedek — bazen şerit 0 ekler ama yön seçimi için
    if b["adet"] > a["adet"]:
        best, yon = b, "döndürülmüş"
        kullanilan = (kh, kw)
    else:
        best, yon = a, "düz"
        kullanilan = (kw, kh)

    plaka_alan = pb * pe
    parca_alan = (best["pw"] * best["ph"]) * best["adet"]
    verim = round(100.0 * parca_alan / plaka_alan, 1) if plaka_alan > 0 else 0.0

    hata = None
    if best["adet"] <= 0:
        hata = (
            f"Rodajlı ölçü {round(kw,1)}×{round(kh,1)} "
            f"kullanılabilir alan {round(uw,1)}×{round(uh,1)} içine sığmıyor "
            f"(kenar boşluk {kenar:g} mm)"
        )

    return {
        "adet": int(best["adet"]),
        "yon": yon if best["adet"] else "-",
        "kesim_boy": round(kullanilan[0], 2),
        "kesim_en": round(kullanilan[1], 2),
        "bitmis_boy": boy,
        "bitmis_en": en,
        "rodaj_mm": rodaj,
        "kenar_bosluk": kenar,
        "kullanilabilir_boy": round(uw, 2),
        "kullanilabilir_en": round(uh, 2),
        "satir": best["satir"],
        "sutun": best["sutun"],
        "ekstra_serit": best["ekstra_serit"],
        "parcalar": best["parcalar"],
        "plaka_boy": pb,
        "plaka_en": pe,
        "hata": hata,
        "verim_yuzde": verim,
    }


def nesting_svg(yer: dict, genislik_px: int = 640, yazdir: bool = False) -> str:
    """Yerleşim şemasını SVG olarak üretir (mm koordinat)."""
    pb = float(yer.get("plaka_boy") or STANDART_PLAKA_BOY)
    pe = float(yer.get("plaka_en") or STANDART_PLAKA_EN)
    kenar = float(yer.get("kenar_bosluk") or KENAR_BOSLUK_MM)
    if pb <= 0 or pe <= 0:
        return ""
    scale = genislik_px / pb
    yuk = pe * scale
    parcalar = yer.get("parcalar") or []
    kw = float(yer.get("kesim_boy") or 0)
    kh = float(yer.get("kesim_en") or 0)
    adet = int(yer.get("adet") or len(parcalar))
    rodaj = yer.get("rodaj_mm", 0)
    yon = yer.get("yon") or "-"
    verim = yer.get("verim_yuzde", 0)

    rects = []
    for i, p in enumerate(parcalar):
        fill = "#bfdbfe" if not p.get("donuk") else "#bbf7d0"
        stroke = "#1e40af" if not p.get("donuk") else "#166534"
        rects.append(
            f'<rect x="{p["x"] * scale:.2f}" y="{p["y"] * scale:.2f}" '
            f'width="{p["w"] * scale:.2f}" height="{p["h"] * scale:.2f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        )
        if len(parcalar) <= 100:
            cx = (p["x"] + p["w"] / 2) * scale
            cy = (p["y"] + p["h"] / 2) * scale
            fs = max(8, min(12, min(p["w"], p["h"]) * scale * 0.32))
            rects.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-size="{fs:.0f}" '
                f'font-family="Segoe UI,Arial" fill="#0f172a" font-weight="600">{i + 1}</text>'
            )

    legend_y = yuk + 8
    total_h = yuk + 52 if not yazdir else yuk + 58
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {genislik_px} {total_h:.1f}"
      width="100%" style="max-width:{genislik_px}px;background:#fff;border:1px solid #94a3b8;border-radius:8px">
  <rect x="0" y="0" width="{genislik_px}" height="{yuk:.1f}" fill="#f1f5f9" stroke="#0f172a" stroke-width="2"/>
  <rect x="{kenar * scale:.2f}" y="{kenar * scale:.2f}"
        width="{(pb - 2 * kenar) * scale:.2f}" height="{(pe - 2 * kenar) * scale:.2f}"
        fill="#fffbeb" stroke="#d97706" stroke-width="1.5" stroke-dasharray="5 4"/>
  {"".join(rects)}
  <text x="8" y="16" font-size="12" font-family="Segoe UI,Arial" font-weight="700" fill="#0f172a">
    Plaka {int(pb)}×{int(pe)} mm
  </text>
  <g transform="translate(0,{legend_y:.1f})">
    <rect x="8" y="0" width="14" height="14" fill="#bfdbfe" stroke="#1e40af"/>
    <text x="26" y="12" font-size="11" font-family="Segoe UI,Arial" fill="#334155">Düz</text>
    <rect x="70" y="0" width="14" height="14" fill="#bbf7d0" stroke="#166534"/>
    <text x="88" y="12" font-size="11" font-family="Segoe UI,Arial" fill="#334155">Döndürülmüş</text>
    <line x1="200" y1="7" x2="230" y2="7" stroke="#d97706" stroke-width="2" stroke-dasharray="4 3"/>
    <text x="236" y="12" font-size="11" font-family="Segoe UI,Arial" fill="#334155">Kenar boşluk {kenar:g} mm</text>
    <text x="8" y="32" font-size="12" font-family="Segoe UI,Arial" fill="#0f172a">
      Kesim {kw:g}×{kh:g} (rodaj {rodaj}) · {adet} adet · yön {yon} · verim %{verim}
    </text>
  </g>
</svg>'''


def plaka_ihtiyaci(kesilecek_adet: int, plaka_basi_adet: int) -> int:
    if plaka_basi_adet <= 0 or kesilecek_adet <= 0:
        return 0
    return int(math.ceil(kesilecek_adet / plaka_basi_adet))


def siparis_plaka_ozet(
    sip: dict,
    kesim_adet: Optional[int] = None,
    plaka_boy: float = STANDART_PLAKA_BOY,
    plaka_en: float = STANDART_PLAKA_EN,
    kenar_bosluk: Optional[float] = None,
    svg: bool = False,
) -> dict:
    """Sipariş için plaka verim + ihtiyaç özeti (+ opsiyonel SVG)."""
    detay = sip.get("uretim_detay") or {}
    if isinstance(detay, str):
        import json
        detay = json.loads(detay or "{}")

    boy = _sayi(detay.get("boy"))
    en = _sayi(detay.get("en"))
    if (boy <= 0 or en <= 0) and sip.get("olcu"):
        parts = [
            p.strip()
            for p in str(sip["olcu"]).replace("×", "x").replace("*", "x").replace("X", "x").split("x")
            if p.strip()
        ]
        if len(parts) >= 2:
            if boy <= 0:
                boy = _sayi(parts[0])
            if en <= 0:
                en = _sayi(parts[1])

    rodaj = _sayi(detay.get("rodaj_pay_mm"), 0.0)
    if kenar_bosluk is None:
        kenar_bosluk = _sayi(detay.get("kenar_bosluk_mm"), KENAR_BOSLUK_MM)
    cam_turu = (detay.get("cam_turu") or "").strip() or "Düzcam"
    kalinlik = _sayi(detay.get("kalinlik"), 0.0)
    # Siparişte seçilen plaka ölçüsü (stoktan)
    if detay.get("plaka_boy") not in (None, ""):
        plaka_boy = _sayi(detay.get("plaka_boy"), plaka_boy)
    if detay.get("plaka_en") not in (None, ""):
        plaka_en = _sayi(detay.get("plaka_en"), plaka_en)
    if kalinlik <= 0 and sip.get("olcu"):
        parts = [
            p.strip()
            for p in str(sip["olcu"]).replace("×", "x").replace("*", "x").replace("X", "x").split("x")
            if p.strip()
        ]
        if len(parts) >= 3:
            kalinlik = _sayi(parts[2])

    if kesim_adet is None:
        kesim_adet = max(0, int(sip.get("adet", 0) or 0) - int(sip.get("hazir_adet", 0) or 0))
    else:
        kesim_adet = max(0, int(kesim_adet))

    yer = plakadan_kac_adet(plaka_boy, plaka_en, boy, en, rodaj, kenar_bosluk)
    ihtiyac = plaka_ihtiyaci(kesim_adet, yer.get("adet") or 0) if yer.get("adet") else 0

    out = {
        "cam_turu": cam_turu,
        "kalinlik": kalinlik,
        "plaka_boy": plaka_boy,
        "plaka_en": plaka_en,
        "rodaj_mm": yer.get("rodaj_mm", rodaj),
        "kenar_bosluk": yer.get("kenar_bosluk", kenar_bosluk),
        "kullanilabilir_boy": yer.get("kullanilabilir_boy", 0),
        "kullanilabilir_en": yer.get("kullanilabilir_en", 0),
        "kesim_boy": yer.get("kesim_boy", 0),
        "kesim_en": yer.get("kesim_en", 0),
        "plaka_basi": yer.get("adet", 0),
        "yon": yer.get("yon", "-"),
        "satir": yer.get("satir", 0),
        "sutun": yer.get("sutun", 0),
        "ekstra_serit": yer.get("ekstra_serit", 0),
        "verim_yuzde": yer.get("verim_yuzde", 0),
        "kesilecek_adet": kesim_adet,
        "plaka_ihtiyac": ihtiyac,
        "hata": yer.get("hata"),
        "olcu_var": boy > 0 and en > 0,
        "kesim_plani_dosya": detay.get("kesim_plani_dosya") or "",
    }
    if svg and yer.get("adet"):
        out["svg"] = nesting_svg(yer)
        out["parca_sayisi_sema"] = len(yer.get("parcalar") or [])
    return out
