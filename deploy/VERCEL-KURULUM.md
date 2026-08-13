# Vercel’de ne yapılır? (Adım adım — PC kapalı da site açılsın)

Bu rehber: web uygulamasını Vercel’e yükleyip `byc.net.tr` adresinden **bilgisayar kapalıyken** açmak içindir.

> Önkoşul: Firebase config (`.env.local`), Auth kullanıcıları ve mümkünse Firestore kuralları hazır olsun.

---

## A) Vercel hesabı

1. Bilgisayarda tarayıcıyı açın: **https://vercel.com**
2. **Sign Up** / **Log In**
3. **Continue with GitHub** seçin (önerilen)
4. GitHub hesabınız (`Fatmanurhatzoglu`) ile izin verin

---

## B) Yeni proje oluştur

1. Vercel ana sayfada **Add New…** → **Project**
2. **Import Git Repository** listesinde `byc-uretim-planlama` görünmeli  
   - Yoksa **Adjust GitHub App Permissions** / repo’yu seçip yetki verin  
   - Hâlâ yoksa: önce GitHub’a `web` klasörünün push edildiğinden emin olun
3. Repo’nun yanındaki **Import** butonuna tıklayın

---

## C) Proje ayarları (çok önemli)

Import ekranında:

### 1) Project Name
Örn. `byc-web` (istediğiniz isim)

### 2) Framework Preset
**Next.js** otomatik seçili olmalı.

### 3) Root Directory ← kritik
1. **Edit** / **Root Directory** yanındaki düğme
2. Klasör seçin: **`web`**
3. **Continue** / onaylayın

> Yanlış bırakırsanız (kök klasör) build patlar. Mutlaka `web` olsun.

### 4) Build and Output
Varsayılan kalsın:
- Build Command: `npm run build` (veya boş = vercel.json)
- Install: `npm install`
- Output: Next.js varsayılan

---

## D) Environment Variables (ortam değişkenleri)

Aynı ekranda **Environment Variables** bölümünü açın.

Her satır için **Key** ve **Value** girip **Add** deyin.  
Hepsi için ortam: **Production**, **Preview**, **Development** işaretli olsun.

| Key (ad) | Value (değer) — `.env.local` ile aynı |
|----------|----------------------------------------|
| `NEXT_PUBLIC_FIREBASE_API_KEY` | `AIzaSy...` (sizin apiKey) |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | `byc-uretim.firebaseapp.com` |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | `byc-uretim` |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | `byc-uretim.firebasestorage.app` |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | `281979773339` |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | `1:281979773339:web:2c9ca5c0cd9b5d87ba413e` |

Değerleri kopyalamak için Cursor’da şu dosyayı açın:

`C:\Users\ongun\Projects\byc-uretim-planlama\web\.env.local`

`KEY=değer` satırında **eşittirden sonrası** Value kutusu.

---

## E) Deploy (yayınla)

1. **Deploy** butonuna basın
2. 1–3 dakika bekleyin (Building… → Ready)
3. Yeşil **Congratulations** / Success olunca size bir adres verir:

```
https://byc-web-xxxx.vercel.app
```

4. Bu linke tıklayın → **giriş sayfası** açılmalı  
   - Kullanıcı: `admin`  
   - Şifre: Firebase’de yazdığınız şifre  

Bu adres PC kapalıyken de çalışır (Vercel bulutta).

Build kırmızı hata verirse ekran görüntüsünü / log’un sonunu gönderin.

---

## F) byc.net.tr adresini Vercel’e bağlama

### F1 — Vercel’de domain ekle
1. Vercel proje sayfası → **Settings** → **Domains**
2. **Add** → yazın: `byc.net.tr`
3. İsterseniz `www.byc.net.tr` da ekleyin
4. Vercel size DNS kaydı söyler (genelde CNAME hedefi, örn. `cname.vercel-dns.com`)

### F2 — Cloudflare DNS (byc.net.tr Cloudflare’deyse)
1. https://dash.cloudflare.com → domain **byc.net.tr**
2. Sol menü **DNS** → **Records**
3. Eski tünel / yanlış kayıtları bulun:
   - `byc.net.tr` için **CNAME** veya **A** (Cloudflare Tunnel’a giden)
4. Vercel’in istediği kaydı ekleyin / güncelleyin. Tipik:

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `@` veya `byc.net.tr` | `cname.vercel-dns.com` (Vercel’in yazdığı) | Proxied veya DNS only — Vercel talimatına uyun |

5. Kaydedin. Yayılması **birkaç dakika – birkaç saat** sürebilir.

### F3 — Kontrol
- Vercel Domains’te `byc.net.tr` → **Valid** olsun  
- Telefonda: **https://byc.net.tr**  
- PC’yi kapatıp tekrar deneyin — açılmalı  

---

## G) Tünel ne olacak?

PC kapalı site için **Cloudflare Tunnel artık gerekmez**.

- `9-TUNEL-AC.bat` çalıştırmanız şart değil  
- Eski tünel DNS’i durursa site yine 530 verebilir → DNS’i Vercel’e çevirdiğinizden emin olun  

Fabrika içi Flask (`4-WEB-AC.bat`) isteğe bağlı kalır (Gantt, Excel, plaka).

---

## H) Veri görünmüyorsa

Web Firestore’dan okur. Fabrika PC açıkken bir kez:

**Ayarlar → Firebase’e temiz aktar (byc/v1)**

Auth kullanıcıları için de Firestore’da olmalı:

`byc / v1 / kullanicilar / {UID}`

```json
{ "kullanici_adi": "admin", "ad": "Yönetici", "rol": "admin" }
```

---

## Kısa kontrol listesi

- [ ] Vercel + GitHub bağlandı  
- [ ] Import → Root Directory = **`web`**  
- [ ] 6 adet `NEXT_PUBLIC_FIREBASE_*` eklendi  
- [ ] Deploy yeşil / `.vercel.app` açılıyor  
- [ ] Domain `byc.net.tr` Vercel’de + DNS doğru  
- [ ] Telefonda giriş çalışıyor  
- [ ] PC kapalı denemesi OK  

Takıldığınız ekranı (Import / Env / Deploy / Domains) yazın; o adımdan devam ederiz.
