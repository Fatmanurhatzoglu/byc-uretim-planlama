# BYC Üretim Planlama v5.0

Endüstriyel üretim çizelgeleme, sipariş yönetimi ve dar boğaz analizi uygulaması.

## Kurulum

1. [Python 3.10+](https://www.python.org/downloads/) yükleyin (kurulumda **"Add Python to PATH"** seçeneğini işaretleyin).
2. Proje klasöründe terminal açın ve bağımlılıkları yükleyin:

```bash
pip install -r requirements.txt
```

## Çalıştırma

```bash
python main.py
```

## Özellikler

- **Sipariş yönetimi** — müşteri, ürün, ölçü, adet, sevk tarihi, öncelik (Acil/Normal/Düşük)
- **Proses rotası** — 13 istasyon, siparişe özel günlük hız (adet/gün)
- **Parçalı sevk** — kısmi sevkiyat takibi
- **Akıllı çizelgeleme** — sevk tarihine göre öncelik, kapasiteyi aşan işler otomatik günlere bölünür
- **Dar boğaz analizi** — doluluk çubukları ve renk kodlu uyarılar
- **Excel** — sipariş içe/dışa aktarma, günlük çizelge raporu
- **Pano & Ayarlar** — fabrika özeti, varsayılan istasyon kapasiteleri

## Veri Dosyaları

| Dosya | Açıklama |
|-------|----------|
| `planlanan_isler.json` | Sipariş havuzu |
| `ayarlar.json` | Varsayılan kapasiteler |

## Excel İçe Aktarma Sütunları

| Sütun | Zorunlu |
|-------|---------|
| Müşteri | Evet |
| Ürün Kodu | Evet |
| Adet | Evet |
| Ölçü | Hayır |
| Sevk Edilen | Hayır |
| Sevk Hedefi | Hayır |
| Durum | Hayır |
| Öncelik | Hayır |
| Rota | Hayır |

## v5.0 Yenilikleri

- Modüler kod yapısı (bakımı kolay)
- Türkçe gün isimleri
- Öncelik sıralaması (Acil siparişler önce planlanır)
- Kapasite aşımında işleri günlere bölme
- Doluluk progress bar'ları
- Fabrika özet panosu
- Ayarlanabilir varsayılan kapasiteler
