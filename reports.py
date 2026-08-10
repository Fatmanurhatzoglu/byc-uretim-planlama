"""PDF rapor üretimi."""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _stil():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="Baslik", fontSize=16, spaceAfter=12, textColor=colors.HexColor("#0F172A")))
    s.add(ParagraphStyle(name="Alt", fontSize=10, textColor=colors.HexColor("#64748B")))
    return s


def haftalik_pdf(siparisler: list, cizelge: dict | None, kpi: dict, asama_map: dict | None = None) -> bytes:
    """Günlük/haftalık özet — aktif aşama + fire oranı özeti dahil."""
    asama_map = asama_map or {}
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=1.2 * cm, leftMargin=1.2 * cm)
    stil = _stil()
    el = []

    bugun = datetime.now()
    el.append(Paragraph("BYC Gunluk / Haftalik Uretim Raporu", stil["Baslik"]))
    el.append(Paragraph(
        f"Donem: {bugun.strftime('%d.%m.%Y')} — Olusturma: {bugun.strftime('%d.%m.%Y %H:%M')}",
        stil["Alt"],
    ))
    el.append(Spacer(1, 12))

    kpi_data = [
        ["Toplam", "Uretimde", "Tamamlanan", "Acil", "Kalan Adet", "Dar Bogaz"],
        [
            str(kpi.get("toplam", 0)), str(kpi.get("uretimde", 0)),
            str(kpi.get("tamamlanan", 0)), str(kpi.get("acil", 0)),
            str(kpi.get("kalan_adet", 0)),
            str(cizelge.get("dar_bogaz_sayisi", 0) if cizelge else 0),
        ],
    ]
    t = Table(kpi_data, colWidths=[3.5 * cm] * 6)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    el.append(t)
    el.append(Spacer(1, 16))

    el.append(Paragraph("Aktif Siparisler (Asama + Fire)", stil["Heading2"]))
    sip_data = [["Musteri", "Urun", "Adet", "Kalan", "Asama", "Stok", "Fire %", "Durum", "Hedef"]]
    for s in siparisler:
        if s.get("durum") == "Tamamlandı":
            continue
        kalan = max(0, int(s["adet"]) - int(s.get("hazir_adet", 0)))
        oz = asama_map.get(str(s.get("id")), {}) or asama_map.get(s.get("id"), {})
        fire = s.get("fire_oranlari") or {}
        if isinstance(fire, str):
            import json
            fire = json.loads(fire or "{}")
        fire_txt = ", ".join(f"{k}:{v}" for k, v in list(fire.items())[:3]) if fire else "-"
        if len(fire) > 3:
            fire_txt += "…"
        sip_data.append([
            (s.get("musteri", "") or "")[:18],
            (s.get("urun", "") or "")[:14],
            str(s.get("adet", "")),
            str(kalan),
            (oz.get("aktif_istasyon") or s.get("aktif_istasyon") or "-")[:16],
            str(oz.get("aktif_stok", s.get("aktif_stok", 0))),
            fire_txt[:28],
            s.get("durum", ""),
            s.get("bitis", ""),
        ])
    if len(sip_data) == 1:
        sip_data.append(["—"] * 9)

    t2 = Table(sip_data, colWidths=[3.2*cm, 2.6*cm, 1.4*cm, 1.4*cm, 2.4*cm, 1.3*cm, 3.2*cm, 2.2*cm, 2.2*cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    el.append(t2)

    if cizelge and cizelge.get("uyarilar"):
        el.append(Spacer(1, 12))
        el.append(Paragraph("Uyarilar", stil["Heading2"]))
        for u in cizelge["uyarilar"][:10]:
            el.append(Paragraph(f"• {u}", stil["Normal"]))

    doc.build(el)
    buf.seek(0)
    return buf.read()


def siparis_detay_pdf(sip: dict, asama: dict | None = None) -> bytes:
    """Tek sipariş PDF — rota, fire %, aşama tablosu."""
    asama = asama or {}
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm)
    stil = _stil()
    el = []
    bugun = datetime.now()

    el.append(Paragraph("BYC Siparis Detay / Is Emri", stil["Baslik"]))
    el.append(Paragraph(f"Olusturma: {bugun.strftime('%d.%m.%Y %H:%M')}", stil["Alt"]))
    el.append(Spacer(1, 10))

    kalan = max(0, int(sip.get("adet", 0)) - int(sip.get("hazir_adet", 0)))
    fire = sip.get("fire_oranlari") or {}
    if isinstance(fire, str):
        import json
        fire = json.loads(fire or "{}")

    ust = [
        ["Musteri", sip.get("musteri", "")],
        ["Urun", sip.get("urun", "")],
        ["Olcu", sip.get("olcu", "") or "-"],
        ["Adet / Sevk / Kalan", f"{sip.get('adet')} / {sip.get('hazir_adet', 0)} / {kalan}"],
        ["Oncelik / Durum", f"{sip.get('oncelik', '')} / {sip.get('durum', '')}"],
        ["Sevk Hedefi", sip.get("bitis", "")],
        ["Rota", sip.get("rotalar", "")],
        ["Aktif Asama", f"{asama.get('aktif_istasyon', '-')} (stok {asama.get('aktif_stok', 0)})"],
        ["Siparis No", str(sip.get("id", ""))],
    ]
    t = Table(ust, colWidths=[4.5 * cm, 11 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    el.append(t)
    el.append(Spacer(1, 14))

    el.append(Paragraph("Fire Oranlari (%)", stil["Heading2"]))
    if fire:
        fire_rows = [["Istasyon", "Fire %"]] + [[k, str(v)] for k, v in fire.items()]
    else:
        fire_rows = [["Istasyon", "Fire %"], ["-", "Siparise ozel fire yok"]]
    tf = Table(fire_rows, colWidths=[8 * cm, 4 * cm])
    tf.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    el.append(tf)
    el.append(Spacer(1, 14))

    el.append(Paragraph("Uretim Asamalari", stil["Heading2"]))
    as_rows = [["#", "Istasyon", "Gelen", "Cikan", "Fire", "Stok"]]
    for a in asama.get("asamalar") or []:
        as_rows.append([
            str(a.get("sira", "")),
            a.get("istasyon", ""),
            str(a.get("gelen", 0)),
            str(a.get("cikan", 0)),
            str(a.get("fire", 0)),
            str(a.get("stok", 0)),
        ])
    if len(as_rows) == 1:
        as_rows.append(["-", "Hareket yok", "0", "0", "0", "0"])
    ta = Table(as_rows, colWidths=[1.2*cm, 5*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.2*cm])
    ta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EFF6FF")]),
    ]))
    el.append(ta)

    doc.build(el)
    buf.seek(0)
    return buf.read()
