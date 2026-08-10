import type { AsamaItem, AsamaOzet, Hareket, HareketTur, Siparis } from "./types";
import { normalizeRota, paralelGrubu } from "./rota";

interface AggRow {
  gelen: number;
  cikan: number;
  fire: number;
}

function aggregateHareketler(hareketler: Hareket[]): Map<string, AggRow> {
  const agg = new Map<string, AggRow>();
  for (const h of hareketler) {
    const st = agg.get(h.istasyon) || { gelen: 0, cikan: 0, fire: 0 };
    if (h.tur === "giris") st.gelen += h.adet;
    else if (h.tur === "cikis") st.cikan += h.adet;
    else if (h.tur === "fire") st.fire += h.adet;
    agg.set(h.istasyon, st);
  }
  return agg;
}

export function asamaOzetHesapla(sip: Siparis, hareketler: Hareket[]): AsamaOzet {
  const rotalar = sip.rota_listesi?.length
    ? [...sip.rota_listesi]
    : normalizeRota(sip.rotalar);
  const agg = aggregateHareketler(hareketler);

  const asamalar: AsamaItem[] = [];
  let aktifIdx: number | null = null;

  rotalar.forEach((ist, i) => {
    const st = agg.get(ist) || { gelen: 0, cikan: 0, fire: 0 };
    const gelen = st.gelen;
    const cikan = st.cikan;
    const fire = st.fire;
    const stok = Math.max(0, gelen - cikan - fire);
    asamalar.push({ istasyon: ist, sira: i + 1, gelen, cikan, fire, stok });
    if (stok > 0 && aktifIdx === null) aktifIdx = i;
  });

  let aktif_istasyon = "Başlamadı";
  let aktif_stok = 0;

  if (aktifIdx === null) {
    if (!asamalar.some((a) => a.gelen > 0)) {
      aktif_istasyon = "Başlamadı";
    } else {
      aktif_istasyon = "Sevk bekliyor";
      for (let i = asamalar.length - 1; i >= 0; i--) {
        const a = asamalar[i];
        if (a.cikan > 0 || a.gelen > 0) {
          if (a.stok === 0 && a.sira === asamalar.length) {
            aktif_istasyon = "Sevk bekliyor";
          } else if (a.stok === 0) {
            const nxt = asamalar[a.sira];
            if (nxt && nxt.gelen > 0) {
              aktif_istasyon = nxt.istasyon;
              aktif_stok = nxt.stok;
            } else {
              aktif_istasyon = a.istasyon;
            }
          }
          break;
        }
      }
    }
  } else {
    aktif_istasyon = asamalar[aktifIdx].istasyon;
    aktif_stok = asamalar[aktifIdx].stok;
  }

  return {
    siparis_id: sip.id,
    musteri: sip.musteri,
    urun: sip.urun,
    adet: sip.adet,
    hazir_adet: sip.hazir_adet,
    durum: sip.durum,
    rotalar,
    asamalar,
    aktif_istasyon,
    aktif_stok,
  };
}

export function asamaSiraUyarisi(
  ozet: AsamaOzet,
  istasyon: string,
  tur: HareketTur,
): string {
  const { rotalar, asamalar } = ozet;
  if (!rotalar.includes(istasyon)) return "";
  const idx = rotalar.indexOf(istasyon);
  const grup = paralelGrubu(istasyon);
  const uyarilar: string[] = [];

  for (const a of asamalar.slice(0, idx)) {
    if (grup?.has(a.istasyon)) continue;
    if (a.stok > 0 && a.istasyon !== istasyon) {
      uyarilar.push(`${a.istasyon} hâlâ ${a.stok} stokta`);
    }
    if (a.gelen === 0 && a.cikan === 0 && a.fire === 0) {
      uyarilar.push(`${a.istasyon} henüz başlamadı`);
    }
  }

  if (tur === "cikis" || tur === "fire") {
    const mevcut = asamalar.find((a) => a.istasyon === istasyon);
    if (mevcut && mevcut.gelen === 0 && mevcut.stok === 0) {
      uyarilar.push(`${istasyon} için önce giriş yapılmamış`);
    }
  }

  return uyarilar.join(" · ");
}

export function kpiFromSiparisler(siparisler: Siparis[]) {
  const aktif = siparisler.filter((s) => s.durum !== "Tamamlandı" && !s.deleted);
  return {
    aktif: aktif.length,
    uretimde: aktif.filter((s) => s.durum === "Üretimde").length,
    acil: aktif.filter((s) => s.oncelik === "Acil").length,
    kalan_adet: aktif.reduce(
      (sum, s) => sum + Math.max(0, s.adet - s.hazir_adet),
      0,
    ),
  };
}
