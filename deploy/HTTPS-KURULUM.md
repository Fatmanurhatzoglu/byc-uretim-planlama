# BYC Üretim Planlama — HTTPS Kurulumu

## Yöntem 1: Otomatik (mkcert — önerilen, şirket içi ağ)

1. mkcert indirin: https://github.com/FiloSottile/mkcert/releases
2. Terminalde:
   ```
   mkcert -install
   mkcert localhost 192.168.1.X
   ```
   (192.168.1.X yerine kendi IP'nizi yazın)
3. Oluşan dosyaları `ssl/` klasörüne kopyalayın:
   - `localhost+1.pem` → `ssl/cert.pem`
   - `localhost+1-key.pem` → `ssl/key.pem`
4. `4-WEB-AC.bat` ile programı başlatın — otomatik HTTPS aktif olur.

## Yöntem 2: Windows Güvenlik Duvarı

Python'a ağ erişimi izni verin:
- Windows Güvenlik Duvarı → Gelen kurallar → Yeni kural
- Port: 5000 (TCP)
- İzin ver

## Yöntem 3: Üretim sunucusu (uzun vade)

- Windows Server veya Linux VM
- Nginx reverse proxy + Let's Encrypt
- `waitress` zaten requirements.txt'de mevcut

## Ağ Erişimi

| Cihaz | Adres |
|-------|-------|
| Sunucu bilgisayar | http://localhost:5000 |
| Tablet/telefon | http://[IP]:5000/mobile |
| QR sevk | http://[IP]:5000/sevk/[siparis-id] |
