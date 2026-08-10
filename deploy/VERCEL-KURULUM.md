# BYC Web — Vercel + Firebase Kurulum

Detaylı adımlar için: [web/README.md](../web/README.md)

## Hızlı özet

1. Firebase Console → Web app config → `web/.env.local`
2. Authentication → Email/Password + kullanıcılar (`admin@byc.net.tr` vb.)
3. Firestore → `web/firestore.rules` yayınla
4. `byc/v1/kullanicilar/{uid}` profil belgeleri
5. Fabrikada Firebase seed (`/api/sync/seed`)
6. Vercel → root: `web` → deploy
7. Cloudflare DNS → Vercel CNAME
8. `byc.net.tr` → Vercel domain ayarı

## Önemli

- Mevcut `4-WEB-AC.bat` / Flask uygulaması **silinmez**
- İki sistem paralel çalışır; veri Firestore'da birleşir
- Tünel artık gerekmez (Vercel 7/24 ayakta)
