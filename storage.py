"""Veri kalıcılığı (JSON dosya işlemleri)."""

import json
import os
from typing import Any

from config import DATA_FILE, SETTINGS_FILE, VARSAYILAN_KAPASITELER


def _oku(path: str, varsayilan: Any) -> Any:
    if not os.path.exists(path):
        return varsayilan
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return varsayilan


def _yaz(path: str, veri: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=4)


def siparisleri_yukle() -> list:
    return _oku(DATA_FILE, [])


def siparisleri_kaydet(siparisler: list) -> None:
    _yaz(DATA_FILE, siparisler)


def ayarlari_yukle() -> dict:
    return _oku(
        SETTINGS_FILE,
        {"varsayilan_kapasiteler": dict(VARSAYILAN_KAPASITELER)},
    )


def ayarlari_kaydet(ayarlar: dict) -> None:
    _yaz(SETTINGS_FILE, ayarlar)
