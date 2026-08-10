# byc.net.tr — Domain Taşıma Rehberi

Bu rehber, BYC Üretim Planlama uygulamasını **byc.net.tr** adresinden yayınlamak için adım adım kurulumu anlatır.

## Genel mimari

```
İnternet → byc.net.tr (DNS) → Cloudflare Tunnel → Fabrika PC (localhost:5000)
```

Uygulama fabrika bilgisayarında çalışmaya devam eder; domain sadece dışarıdan erişim sağlar.

---

## Ön koşullar

- [ ] Domain **byc.net.tr** satın alındı
- [ ] Fabrika sunucu PC'sinde `4-WEB-AC.bat` ile uygulama çalışıyor
- [ ] `config.py` içinde `SITE_DOMAIN = "byc.net.tr"` ayarlı (zaten yapıldı)

---

## Yöntem 1: Cloudflare Tunnel (ÖNERİLEN)

**Avantajlar:** Ücretsiz SSL, sabit IP gerekmez, modem port açmaya gerek yok, DDoS koruması.

### Adım 1 — Cloudflare hesabı

1. https://dash.cloudflare.com adresine gidin, ücretsiz hesap açın
2. **Add a site** → `byc.net.tr` yazın
3. **Free** planı seçin

### Adım 2 — Nameserver değişikliği

Cloudflare size 2 nameserver verecek (örnek):

```
ada.ns.cloudflare.com
bob.ns.cloudflare.com
```

Domaini aldığınız panelde (Nic.tr, Natro, GoDaddy vb.):

1. Domain yönetimi → **DNS / Nameserver**
2. Mevcut nameserver'ları silin
3. Cloudflare'in verdiği 2 nameserver'ı girin
4. Kaydedin — yayılması **15 dakika – 48 saat** sürebilir

Cloudflare panelinde domain **Active** olunca devam edin.

### Adım 3 — cloudflared kurulumu (Windows)

PowerShell'i **Yönetici olarak** açın:

```powershell
winget install --id Cloudflare.cloudflared
```

Veya manuel: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

### Adım 4 — Tünel oluşturma

```powershell
cloudflared tunnel login
```

Tarayıcı açılır → byc.net.tr seçin → Authorize.

```powershell
cloudflared tunnel create byc-uretim
```

Çıktıdaki **Tunnel ID**'yi not alın (ör: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

### Adım 5 — Yapılandırma dosyası

`deploy\cloudflared-config.yml` dosyasını düzenleyin:

- `TUNNEL_ID` → kendi tunnel ID'niz
- `credentials-file` yolunu kontrol edin

Dosyayı şuraya kopyalayın:

```
C:\Users\KULLANICI\.cloudflared\config.yml
```

(`KULLANICI` yerine Windows kullanıcı adınız)

### Adım 6 — DNS kaydı

```powershell
cloudflared tunnel route dns byc-uretim byc.net.tr
cloudflared tunnel route dns byc-uretim www.byc.net.tr
```

### Adım 7 — Başlatma

1. Önce `4-WEB-AC.bat` ile uygulamayı başlatın
2. Sonra `8-DOMAIN-BASLAT.bat` ile tüneli başlatın

Tarayıcıda **https://byc.net.tr** açılmalı.

### Adım 8 — Otomatik başlatma (isteğe bağlı)

`7-OTOMATIK-BASLAT.bat` zaten web uygulamasını başlatır. Tünel için:

```powershell
cloudflared service install
```

Sonra Windows Hizmetleri'nde **Cloudflared** servisini başlatın.

---

## Yöntem 2: Kendi sunucunuz + sabit IP

Modemde port yönlendirme yapabiliyorsanız:

| Kayıt | Tip | Değer |
|-------|-----|-------|
| `@` veya `byc.net.tr` | A | Sabit genel IP'niz |
| `www` | CNAME | byc.net.tr |

Modem: **443 → sunucu IP:5000** (veya 80→5000)

Windows'ta **Caddy** veya Linux'ta **Nginx + Let's Encrypt** kullanın. Örnek Caddy:

```
byc.net.tr {
    reverse_proxy localhost:5000
}
```

---

## Yöntem 3: Bulut sunucu (VPS)

DigitalOcean, Hetzner, Turhost vb. bir Linux sunucuya:

```bash
git clone <repo>
cd byc-uretim-planlama
pip install -r requirements.txt
# uretim.db ve firebase-service-account.json kopyalayın
python web_app.py
```

Nginx reverse proxy + certbot ile SSL kurun.

---

## Güvenlik kontrol listesi

- [ ] `config.py` → `SECRET_KEY` değiştirin (rastgele uzun bir string)
- [ ] Varsayılan şifreleri değiştirin (admin, ofis, saha)
- [ ] Cloudflare'de **SSL/TLS → Full (strict)** seçin
- [ ] İsteğe bağlı: Cloudflare **Access** ile IP veya e-posta kısıtlaması
- [ ] `uretim.db` düzenli yedek (`5-YEDEK-AL.bat`)

---

## Sorun giderme

| Sorun | Çözüm |
|-------|-------|
| Site açılmıyor | `4-WEB-AC.bat` çalışıyor mu? Port 5000 dinliyor mu? |
| SSL hatası | Cloudflare'de SSL modu **Full** veya **Flexible** deneyin |
| QR kod eski IP gösteriyor | `yedekler/qr_cache/` klasörünü silin, yeniden oluşturulsun |
| Oturum açılmıyor | `BEHIND_PROXY = True` ve `SITE_DOMAIN` ayarlı mı? |
| Nameserver henüz aktif değil | https://dnschecker.org ile byc.net.tr kontrol edin |

---

## Hızlı test (tünel kurulmadan önce)

Yerel ağda çalıştığını doğrulayın:

```
http://localhost:5000
http://[YEREL-IP]:5000/mobile
```

Domain hazır olunca:

```
https://byc.net.tr
https://byc.net.tr/mobile
```
