# Firestore şema — mobil / web / fabrika

Kanonik veri yolu (tüm istemciler bunu kullanır):

```
byc / v1                            ← meta (şema keşfi)
byc / v1 / siparisler / {id}        ← sipariş belgesi
byc / v1 / siparisler / {id} / hareketler / {client_uid}
```

Proje ID örneği: `byc-uretim`

---

## Meta belge

**Yol:** `byc/v1`

| Alan | Açıklama |
|------|----------|
| `schema_version` | `"v1"` |
| `paths.siparisler` | Koleksiyon yolu |
| `paths.hareketler` | Alt koleksiyon yolu şablonu |
| `siparis_sayisi` / `hareket_sayisi` | Son seed sayıları |
| `updated_at` | UTC ISO |

Mobil uygulama açılışta `byc/v1` okuyup yolları doğrulasın.

---

## Sipariş belgesi

**Yol:** `byc/v1/siparisler/{id}`

| Alan | Tip | Not |
|------|-----|-----|
| `id` | string | Belge ID ile aynı |
| `musteri`, `urun`, `olcu` | string | |
| `adet`, `hazir_adet`, `kalan_adet` | number | `kalan = adet - hazir` |
| `bitis` | string | `GG.AA.YYYY` |
| `durum` | string | Beklemede / Üretimde / Durduruldu / Tamamlandı |
| `oncelik` | string | Acil / Normal / Düşük |
| `rotalar` | string | Virgüllü |
| `rota_listesi` | string[] | Mobil için dizi |
| `istasyon_kapasiteleri` | map | makine → adet/gün |
| `fire_oranlari` | map | makine → % |
| `uretim_detay` | map | boy, en, kalinlik, cam_turu, … |
| `olusturma`, `guncelleme` | string | ISO |
| `deleted` | bool | soft delete |
| `schema_version` | string | `"v1"` |
| `source` | string | `"fabrika"` |

**Çakışma:** `guncelleme` — son yazan kazanır.

**Liste (aktif):** `where('deleted', '==', false)` (+ isteğe `durum`).

---

## Hareket belgesi

**Yol:** `byc/v1/siparisler/{siparisId}/hareketler/{client_uid}`

| Alan | Tip | Not |
|------|-----|-----|
| `client_uid` | string | Belge ID (UUID) — idempotent |
| `siparis_id` | string | |
| `istasyon` | string | Kesim, Rodaj 1, … |
| `tur` | string | `giris` / `cikis` / `fire` |
| `adet` | number | |
| `neden`, `not_metin`, `kullanici` | string | |
| `zaman` | string | ISO |
| `auto` | bool | otomatik aktarım |
| `schema_version` | string | `"v1"` |

Hareketler **append-only**; üzerine yazma / silme yok. Aynı `client_uid` tekrar yazılırsa merge idempotent.

İstasyon stoku istemcide türetilir: `gelen - cikan - fire`.

---

## Örnek (Flutter / JS)

```text
siparisler = firestore.collection('byc').doc('v1').collection('siparisler')
hareketler = siparisler.doc(id).collection('hareketler')
```

```javascript
const meta = await db.collection('byc').doc('v1').get();
const siparisler = db.collection('byc').doc('v1').collection('siparisler')
  .where('deleted', '==', false);
```

---

## Güvenlik (ileride)

Şu an fabrika **Admin SDK** ile yazar. Mobil istemci için:

1. Firebase Auth (anonim veya e-posta)
2. Firestore Rules: okuma autentike; yazma sadece admin / Cloud Functions

---

## Seed

Fabrika uygulaması: **Ayarlar → Firebase’e temiz aktar (byc/v1)**  
veya `POST /api/sync/seed` (ofis/admin).
