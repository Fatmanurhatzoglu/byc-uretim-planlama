"""Offline-first Firebase senkron katmanı.

Yerel SQLite anında yazar (internetsiz çalışır). Değişiklikler outbox'a düşer;
istasyon Kaydet/Onayla (veya manuel buton) sonrası asenkron push + pull yapılır.
Sürekli arka plan döngüsü yoktur.
"""

from sync.hooks import (
    hareket_eklendi,
    siparis_degisti,
    siparis_silindi,
    skip_sync,
)
from sync.service import durum as sync_durum
from sync.service import sync_now
from sync.seed import seed_tum_veriler
from sync.worker import baslat as sync_worker_baslat
from sync.worker import durdur as sync_worker_durdur
from sync.worker import trigger_async as sync_trigger_async

__all__ = [
    "hareket_eklendi",
    "siparis_degisti",
    "siparis_silindi",
    "skip_sync",
    "seed_tum_veriler",
    "sync_durum",
    "sync_now",
    "sync_trigger_async",
    "sync_worker_baslat",
    "sync_worker_durdur",
]
