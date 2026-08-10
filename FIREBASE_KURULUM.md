# Firebase / Firestore kurulum (offline-first senkron)

Bu uygulama **önce yerel SQLite’a yazar** (internetsiz çalışır). Değişiklikler bir kuyruğa (outbox) düşer; internet gelince arka planda **Firestore’a yazar** ve diğer cihazlardan **çeker**.

Kapsam (ilk aşama): **siparişler + aşama hareketleri**. Plaka stok / çizelge henüz senkron değil.

Çakışma kuralı: siparişte **son yazan kazanır** (`guncelleme`); aşama hareketleri **eklenir** (silinmez / üzerine yazılmaz), `client_uid` ile tekrarlanmaz.

---

## 0) Önemli: Spark yetmez → Blaze (faturalandırma) açın

Hata mesajı:

> This API method requires billing to be enabled…

**Spark (ücretsiz plan) Firestore yazmayı açmaz.**  
**Blaze (pay as you go)** açmanız gerekir. Kart eklenir ama fabrika seviyesinde kullanım genelde **ücretsiz kotanın içinde** kalır (ayda onlarca bin okuma/yazma ücretsiz).

### Blaze’e geçiş (byc-uretim)

1. Tarayıcıda açın:  
   https://console.developers.google.com/billing/enable?project=byc-uretim  
   veya Firebase Console → proje **byc-uretim** → sol alt **Upgrade** / **Blaze planına yükselt**
2. Google Cloud faturalandırma hesabı oluşturun / seçin  
3. Kredi kartı ekleyin (doğrulama için; küçük tutar authorize edilebilir, sonra geri çekilir)  
4. Proje faturalandırmaya bağlansın → **Blaze** aktif olsun  
5. **2–5 dakika bekleyin** (sistemlere yayılması)  
6. Uygulamada **Ayarlar → Şimdi Senkronla** veya üst bardaki Senkron’a tıklayın

Kontrol:  
https://console.firebase.google.com/project/byc-uretim/usage/details  
→ plan **Blaze** görünmeli.

İsterseniz harcama tavanı koyun (Cloud Console → Billing → Budgets): örn. aylık 5–10 USD uyarı — sürpriz fatura olmasın.

---

## 1) Firebase proje oluştur

1. https://console.firebase.google.com → **Add project**
2. Project name örn. `byc-uretim`
3. Google Analytics isteğe bağlı (gerekmez)

## 2) Firestore aç

1. Sol menü **Build → Firestore Database**
2. **Create database**
3. Başlangıçta **production mode** veya test mode; üretimde kurallar şart
4. Konum: `europe-west1` (veya size yakın)

Geçici test kuralları (geliştirme):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false; // Admin SDK yine de yazar (sunucu anahtarı)
    }
  }
}
```

> Not: Bu program **Admin SDK** ile yazar; istemci (tarayıcı) kuralları Admin SDK’yı engellemez. Anahtar dosyasını gizli tutun.

## 3) Service account JSON indir

1. Project settings (dişli) → **Service accounts**
2. **Generate new private key** → JSON indir
3. Dosyayı projenin köküne koyun ve **şu isimle kaydedin:**

```
C:\Users\ongun\Projects\byc-uretim-planlama\firebase-service-account.json
```

Bu dosya `.gitignore`’da — GitHub’a **gönderilmez**.

Örnek yapı: `firebase-service-account.example.json`

## 4) Python paketi

```bat
3-WEB-KURULUM.bat
```

veya:

```bat
pip install -r requirements.txt
```

## 5) Çalıştır

```bat
4-WEB-AC.bat
```

Üst barda **Senkron** chip’i görünür:

| Renk | Anlam |
|------|--------|
| Yeşil | Online, bekleyen yok |
| Mavi | Online, bekleyen kayıt var |
| Turuncu | Çevrimdışı (kayıtlar yerelde duruyor) |
| Kırmızı | Anahtar yok / hata |

**Ayarlar → Firebase Senkron** panelinden:

- **Şimdi Senkronla** — manuel push + pull
- **Yerel siparişleri kuyruğa al** — ilk kurulumda tüm siparişleri Firestore’a gönder

**Otomatik tetik:** Sürekli arka plan yok. İstasyonda **Kaydet / Onayla** basılınca ~2 sn debounce ile bir kez senkronlanır (internetsiz kayıtlar outbox’ta kalır, sonraki Kaydet’te gider).

## 6) Birden fazla PC / tablet

Her makinede:

1. Aynı `firebase-service-account.json` (güvenli kopyala)
2. Aynı uygulama sürümü
3. İnternet olmasa da sipariş/aşama girilir; net gelince birleşir

## 7) Kapatmak

`config.py`:

```python
FIREBASE_ENABLED = False
```

---

## Mimari (kısa)

```
UI / API  →  SQLite (anında)
               ↓
            Outbox kuyruk
               ↓ (İstasyon Kaydet/Onayla veya manuel buton)
            Firestore  siparisler/{id}
                       └─ asama_hareketler/{client_uid}
               ↓ pull
            SQLite (LWW sipariş / eklemeli hareket)
```

Sorun olursa Ayarlar panelindeki **Mesaj / Son hata** satırına bakın.

Mobil/web alan sözlüğü: **[FIREBASE_SCHEMA.md](FIREBASE_SCHEMA.md)** (`byc/v1/siparisler/...`).
