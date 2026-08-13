# BYC Web — Vercel + Firebase

Next.js uygulaması: mobil sevk, istasyon takibi, sipariş listesi.  
**Mevcut Flask fabrika uygulamasına dokunulmaz** — veri Firestore üzerinden senkronlanır.

## Kurulum

### 1. Firebase Web App (config nerede?)

1. https://console.firebase.google.com açın → proje **byc-uretim**
2. Sol üstte dişli **⚙️ Project settings** (Proje ayarları)
3. Üstteki sekmelerden **General** (Genel)
4. Sayfayı **aşağı kaydırın** → **Your apps** / **Uygulamalarınız**
5. Web uygulaması yoksa:
   - `</>` (Web) ikonuna tıklayın
   - App nickname: `byc-web`
   - **Register app** / **Uygulamayı kaydet**
6. Ekranda şu blok çıkar (**Firebase SDK snippet** → **Config** seçili olsun):

```js
const firebaseConfig = {
  apiKey: "AIza...",
  authDomain: "byc-uretim.firebaseapp.com",
  projectId: "byc-uretim",
  storageBucket: "byc-uretim.firebasestorage.app",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abcdef"
};
```

Bu 6 değeri kopyalayacaksınız.  
Zaten web app varsa: aynı **Your apps** listesinde web uygulamasına tıklayın → **Config** görünür.

> Not: Bu config **gizli service account JSON değil**. Web `apiKey` istemci tarafında normaldir.

### 2. Ortam değişkenleri

```bash
cd web
cp .env.example .env.local
```

`.env.local` dosyasını Firebase config ile doldurun.

### 3. Authentication

Firebase Console → Authentication → Sign-in method → **Email/Password** açın.

Kullanıcılar (örnek):

| Kullanıcı adı (giriş) | E-posta (Firebase) | Rol |
|----------------------|-------------------|-----|
| admin | admin@byc.net.tr | admin |
| ofis | ofis@byc.net.tr | ofis |
| saha | saha@byc.net.tr | saha |

### 4. Kullanıcı profilleri (Firestore)

Her Firebase Auth kullanıcısı için belge oluşturun:

**Yol:** `byc/v1/kullanicilar/{Firebase UID}`

```json
{
  "kullanici_adi": "saha",
  "ad": "Saha Operatör",
  "rol": "saha"
}
```

`rol`: `admin` | `ofis` | `saha`

### 5. Firestore kuralları

Firebase Console → Firestore → Rules → `web/firestore.rules` içeriğini yapıştırın → Publish.

### 6. Veri aktarımı

Fabrika PC'de mevcut uygulama çalışıyorsa:

**Ayarlar → Firebase'e temiz aktar (byc/v1)**  
veya `POST /api/sync/seed`

### 7. Yerel geliştirme

```bash
cd web
npm install
npm run dev
```

http://localhost:3000

### 8. Vercel deploy

1. https://vercel.com → New Project → bu repo
2. **Root Directory:** `web`
3. Environment Variables: `.env.example` içindeki `NEXT_PUBLIC_*` değerleri
4. Deploy

### 9. Domain (byc.net.tr)

**Cloudflare DNS:**

| Tip | Ad | Hedef |
|-----|-----|-------|
| CNAME | `@` veya `www` | `cname.vercel-dns.com` (Vercel'in verdiği adres) |

Vercel → Project → Settings → Domains → `byc.net.tr` ekleyin.

---

## Sayfalar

| URL | Açıklama |
|-----|----------|
| `/login` | Giriş |
| `/mobile` | Saha — sipariş listesi, KPI |
| `/sevk/[id]` | Sevk girişi |
| `/istasyon` | Makine bazlı giriş/çıkış/fire |

---

## Fabrika + Web birlikte

- Fabrika Flask uygulaması **aynen çalışmaya devam eder**
- Firestore ortak veri katmanıdır
- Web'den yapılan sevk/hareket fabrikaya senkronla gelir
- Ofis paneli (Gantt, Excel, plaka) şimdilik fabrika PC'de kalır
