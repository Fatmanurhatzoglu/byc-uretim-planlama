"""Uygulama sabitleri ve tema ayarları."""

APP_TITLE = "BYC Endüstriyel Üretim Çizelgeleme ve Dar Boğaz Yönetimi"
PLAKA_UYARI_ESIK = 10  # Bu adet ve altı → düşük stok uyarısı
APP_VERSION = "8.2.1"
DATA_FILE = "planlanan_isler.json"
SETTINGS_FILE = "ayarlar.json"
DB_FILE = "uretim.db"
BACKUP_DIR = "yedekler"
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
SECRET_KEY = "byc-uretim-gizli-anahtar-degistirin"  # Üretimde değiştirin

# Kullanıcı rolleri
ROLLER = {
    "admin": "Yönetici — tam yetki",
    "ofis": "Ofis — sipariş ve çizelgeleme",
    "saha": "Saha — sadece sevk girişi",
}

# Otomatik yedekleme aralığı (saat)
YEDEK_ARALIK_SAAT = 24

TUM_MAKINELER = [
    "Kesim",
    "Rodaj 1",
    "Rodaj 2",
    "Çin Rodajı",
    "Su Jeti",
    "Lazer Kesim",
    "Kimyasal Temper",
    "Büyük Temper",
    "Isıl Temper",
    "Vakum AR Kaplama",
    "Daldırma",
    "Serigrafi Baskı",
    "Laminasyon",
]

# Aynı süreç adımında paralel çalışan makineler (scheduler tek adım sayar).
# Rota'da ardışık seçilen üyeler kapasiteye göre bölünür; ayrı gün beklenmez.
PARALEL_GRUPLAR = [
    ("Rodaj 1", "Rodaj 2"),
]

VARSAYILAN_KAPASITELER = {makine: 500 for makine in TUM_MAKINELER}
VARSAYILAN_KAPASITELER["Rodaj 1"] = 1000
VARSAYILAN_KAPASITELER["Rodaj 2"] = 1000
# Siparişe özel varsayılan hızlar (adet/gün) — cam bazlı
# Bölüm toplam kapasitesi ayrıdır:
BOLUM_KAPASITELERI = {
    "Kesim": 1500,  # Kesim bölümü TOPLAM adet/gün
}

# İstasyon bazlı fire oranı (%) — sonraki işlemlerde kayıp
# Kesim planlamasında %10–20 bandı kullanılır (Ayarlar'dan değiştirilebilir).
VARSAYILAN_FIRE_ORANLARI = {
    "Kesim": 15.0,
    "Rodaj 1": 12.0,
    "Rodaj 2": 12.0,
    "Çin Rodajı": 12.0,
    "Su Jeti": 10.0,
    "Lazer Kesim": 10.0,
    "Kimyasal Temper": 18.0,
    "Büyük Temper": 16.0,
    "Isıl Temper": 16.0,
    "Vakum AR Kaplama": 14.0,
    "Daldırma": 12.0,
    "Serigrafi Baskı": 14.0,
    "Laminasyon": 18.0,
}

# Makineye özel çalışma günleri (0=Pazartesi ... 6=Pazar)
MAKINE_OZEL_GUNLER = {
    "Kimyasal Temper": {0, 1, 3},  # Pazartesi, Salı, Perşembe
}

ONCELIK_SIRASI = {"Acil": 0, "Normal": 1, "Düşük": 2}

DURUMLAR = ["Beklemede", "Üretimde", "Durduruldu", "Tamamlandı"]

# Üretim fire / ayrılma nedenleri (hazır liste)
FIRE_NEDENLERI = [
    "Çatlak",
    "Çizik",
    "Ölçü hatası",
    "Kenar hatası",
    "Köpük / kalite",
    "Kırık",
    "Temper hatası",
    "Kaplama hatası",
    "Baskı hatası",
    "Lamine hatası",
    "Diğer",
]

# Renk paleti
COLORS = {
    "bg": "#F1F5F9",
    "card": "#FFFFFF",
    "header": "#0F172A",
    "header_sub": "#94A3B8",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "success": "#10B981",
    "success_bg": "#D1FAE5",
    "success_fg": "#065F46",
    "warning": "#F59E0B",
    "warning_bg": "#FEF3C7",
    "warning_fg": "#92400E",
    "danger": "#EF4444",
    "danger_bg": "#FEE2E2",
    "danger_fg": "#991B1B",
    "muted": "#64748B",
    "text": "#0F172A",
    "text_secondary": "#475569",
    "border": "#E2E8F0",
    "tab_inactive": "#CBD5E1",
    "accent_orange": "#D97706",
}

GUN_ADLARI_TR = {
    "Monday": "Pazartesi",
    "Tuesday": "Salı",
    "Wednesday": "Çarşamba",
    "Thursday": "Perşembe",
    "Friday": "Cuma",
    "Saturday": "Cumartesi",
    "Sunday": "Pazar",
}

HAFTA_SONU = {"Saturday", "Sunday"}
