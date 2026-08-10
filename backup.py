"""Otomatik ve manuel veritabanı yedekleme."""

from __future__ import annotations

import os
import shutil
import threading
import time
from datetime import datetime

from config import BACKUP_DIR, DB_FILE, YEDEK_ARALIK_SAAT


def yedek_al() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError("Veritabanı dosyası bulunamadı.")
    ad = f"uretim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    hedef = os.path.join(BACKUP_DIR, ad)
    shutil.copy2(DB_FILE, hedef)
    _eski_yedekleri_temizle(max_adet=30)
    return hedef


def _eski_yedekleri_temizle(max_adet: int = 30) -> None:
    if not os.path.isdir(BACKUP_DIR):
        return
    dosyalar = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".db")],
        key=os.path.getmtime,
        reverse=True,
    )
    for eski in dosyalar[max_adet:]:
        try:
            os.remove(eski)
        except OSError:
            pass


def yedekleri_listele() -> list[dict]:
    if not os.path.isdir(BACKUP_DIR):
        return []
    sonuc = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith(".db"):
            yol = os.path.join(BACKUP_DIR, f)
            sonuc.append({
                "dosya": f,
                "boyut_kb": round(os.path.getsize(yol) / 1024, 1),
                "tarih": datetime.fromtimestamp(os.path.getmtime(yol)).strftime("%d.%m.%Y %H:%M"),
            })
    return sonuc


def yedekten_geri_yukle(dosya_adi: str) -> None:
    kaynak = os.path.join(BACKUP_DIR, dosya_adi)
    if not os.path.exists(kaynak):
        raise FileNotFoundError("Yedek dosyası bulunamadı.")
    yedek_al()
    shutil.copy2(kaynak, DB_FILE)


def otomatik_yedek_baslat() -> None:
    def _dongu():
        while True:
            time.sleep(YEDEK_ARALIK_SAAT * 3600)
            try:
                yedek_al()
            except Exception:
                pass

    t = threading.Thread(target=_dongu, daemon=True)
    t.start()
