import {
  collection,
  doc,
  getDoc,
  getDocs,
  onSnapshot,
  setDoc,
  updateDoc,
  writeBatch,
  type Unsubscribe,
} from "firebase/firestore";
import { FIREBASE_ROOT, FIREBASE_SCHEMA_VERSION } from "./constants";
import { getDb } from "./firebase";
import { kapasiteyiBol, normalizeRota, paralelGirisHedefleri } from "./rota";
import { asamaOzetHesapla } from "./asama";
import type { AsamaOzet, Hareket, HareketTur, IstasyonSiparis, KullaniciProfil, Siparis } from "./types";

function schemaDoc() {
  return doc(getDb(), FIREBASE_ROOT, FIREBASE_SCHEMA_VERSION);
}

function siparislerCol() {
  return collection(schemaDoc(), "siparisler");
}

function hareketlerCol(siparisId: string) {
  return collection(siparislerCol(), siparisId, "hareketler");
}

function kullaniciDoc(uid: string) {
  return doc(collection(schemaDoc(), "kullanicilar"), uid);
}

function docToSiparis(id: string, data: Record<string, unknown>): Siparis {
  const adet = Number(data.adet) || 0;
  const hazir = Number(data.hazir_adet) || 0;
  return {
    id,
    musteri: String(data.musteri || ""),
    urun: String(data.urun || ""),
    olcu: String(data.olcu || ""),
    adet,
    hazir_adet: hazir,
    kalan_adet: Number(data.kalan_adet) ?? Math.max(0, adet - hazir),
    bitis: String(data.bitis || ""),
    durum: String(data.durum || "Beklemede"),
    oncelik: String(data.oncelik || "Normal"),
    rotalar: String(data.rotalar || ""),
    rota_listesi: Array.isArray(data.rota_listesi)
      ? (data.rota_listesi as string[])
      : normalizeRota(String(data.rotalar || "")),
    deleted: Boolean(data.deleted),
    guncelleme: String(data.guncelleme || ""),
    uretim_detay: (data.uretim_detay as Record<string, unknown>) || {},
  };
}

function docToHareket(id: string, data: Record<string, unknown>): Hareket {
  return {
    client_uid: String(data.client_uid || id),
    siparis_id: String(data.siparis_id || ""),
    istasyon: String(data.istasyon || ""),
    tur: String(data.tur || "giris") as HareketTur,
    adet: Number(data.adet) || 0,
    neden: String(data.neden || ""),
    not_metin: String(data.not_metin || ""),
    kullanici: String(data.kullanici || ""),
    zaman: String(data.zaman || ""),
    auto: Boolean(data.auto),
  };
}

export async function getKullaniciProfil(uid: string): Promise<KullaniciProfil | null> {
  const snap = await getDoc(kullaniciDoc(uid));
  if (!snap.exists()) return null;
  const d = snap.data();
  return {
    kullanici_adi: String(d.kullanici_adi || ""),
    ad: String(d.ad || d.kullanici_adi || ""),
    rol: (d.rol as KullaniciProfil["rol"]) || "saha",
  };
}

export function subscribeSiparisler(
  onData: (siparisler: Siparis[]) => void,
  onError?: (e: Error) => void,
): Unsubscribe {
  // deleted alanı olmayan eski belgeler where("deleted"==false) ile kaçmasın
  return onSnapshot(
    siparislerCol(),
    (snap) => {
      const list = snap.docs
        .map((d) => docToSiparis(d.id, d.data()))
        .filter((s) => !s.deleted);
      list.sort((a, b) => (b.guncelleme || "").localeCompare(a.guncelleme || ""));
      onData(list);
    },
    (err) => onError?.(err),
  );
}

function yeniSiparisId(): string {
  const d = new Date();
  const pad = (n: number, len = 2) => String(n).padStart(len, "0");
  const stamp =
    pad(d.getDate()) +
    pad(d.getMonth() + 1) +
    d.getFullYear() +
    pad(d.getHours()) +
    pad(d.getMinutes()) +
    pad(d.getSeconds());
  return stamp + String(Math.floor(100 + Math.random() * 900));
}

export type SiparisOlusturGirdi = {
  musteri: string;
  urun: string;
  olcu?: string;
  adet: number;
  bitis: string;
  oncelik?: string;
  durum?: string;
  rotalar: string[] | string;
};

export async function siparisEkle(girdi: SiparisOlusturGirdi): Promise<Siparis> {
  const musteri = (girdi.musteri || "").trim();
  const urun = (girdi.urun || "").trim().toUpperCase();
  const adet = Number(girdi.adet) || 0;
  if (!musteri) throw new Error("Müşteri zorunlu.");
  if (!urun) throw new Error("Ürün zorunlu.");
  if (adet <= 0) throw new Error("Adet 1 veya daha büyük olmalı.");

  const rota_listesi = normalizeRota(girdi.rotalar);
  if (!rota_listesi.length) throw new Error("En az bir işlem (rota) seçin.");

  const id = yeniSiparisId();
  const simdi = new Date().toISOString().slice(0, 19);
  const rotalar = rota_listesi.join(", ");
  const data = {
    schema_version: FIREBASE_SCHEMA_VERSION,
    id,
    musteri,
    urun,
    olcu: (girdi.olcu || "").trim(),
    adet,
    hazir_adet: 0,
    kalan_adet: adet,
    bitis: (girdi.bitis || "").trim(),
    durum: girdi.durum || "Beklemede",
    oncelik: girdi.oncelik || "Normal",
    rotalar,
    rota_listesi,
    istasyon_kapasiteleri: {},
    fire_oranlari: {},
    uretim_detay: {},
    olusturma: simdi,
    guncelleme: simdi,
    deleted: false,
    source: "web-ofis",
  };
  await setDoc(doc(siparislerCol(), id), data);
  return docToSiparis(id, data);
}

export async function getSiparis(id: string): Promise<Siparis | null> {
  const snap = await getDoc(doc(siparislerCol(), id));
  if (!snap.exists() || snap.data().deleted) return null;
  return docToSiparis(snap.id, snap.data());
}

export async function getHareketler(siparisId: string): Promise<Hareket[]> {
  const snap = await getDocs(hareketlerCol(siparisId));
  return snap.docs.map((d) => docToHareket(d.id, d.data()));
}

export async function getAsamaOzet(siparisId: string): Promise<AsamaOzet | null> {
  const sip = await getSiparis(siparisId);
  if (!sip) return null;
  const hareketler = await getHareketler(siparisId);
  return asamaOzetHesapla(sip, hareketler);
}

export async function sevkGuncelle(
  siparisId: string,
  adet: number,
): Promise<Siparis> {
  const sip = await getSiparis(siparisId);
  if (!sip) throw new Error("Sipariş bulunamadı.");
  const kalan = Math.max(0, sip.adet - sip.hazir_adet);
  if (adet <= 0 || adet > kalan) {
    throw new Error(`En fazla ${kalan} adet sevk edilebilir.`);
  }
  const yeni = sip.hazir_adet + adet;
  const simdi = new Date().toISOString().slice(0, 19);
  const durum = yeni >= sip.adet ? "Tamamlandı" : "Üretimde";
  await updateDoc(doc(siparislerCol(), siparisId), {
    hazir_adet: yeni,
    kalan_adet: Math.max(0, sip.adet - yeni),
    durum,
    guncelleme: simdi,
    source: "web",
  });
  return { ...sip, hazir_adet: yeni, kalan_adet: Math.max(0, sip.adet - yeni), durum, guncelleme: simdi };
}

function yeniHareketBelgesi(
  siparisId: string,
  istasyon: string,
  tur: HareketTur,
  adet: number,
  opts: {
    neden?: string;
    not_metin?: string;
    kullanici?: string;
    auto?: boolean;
  },
): { id: string; data: Record<string, unknown> } {
  const client_uid = crypto.randomUUID();
  const simdi = new Date().toISOString().slice(0, 19);
  return {
    id: client_uid,
    data: {
      schema_version: FIREBASE_SCHEMA_VERSION,
      client_uid,
      siparis_id: siparisId,
      istasyon,
      tur,
      adet,
      neden: opts.neden || "",
      not_metin: opts.not_metin || "",
      kullanici: opts.kullanici || "",
      zaman: simdi,
      auto: Boolean(opts.auto),
      source: "web",
    },
  };
}

export async function hareketEkle(
  siparisId: string,
  istasyon: string,
  tur: HareketTur,
  adet: number,
  opts: {
    neden?: string;
    not_metin?: string;
    kullanici?: string;
    sonraki_aktar?: boolean;
  } = {},
): Promise<AsamaOzet> {
  if (!["giris", "cikis", "fire"].includes(tur)) {
    throw new Error("Tür giris, cikis veya fire olmalı.");
  }
  if (adet <= 0) throw new Error("Adet 1 veya daha büyük olmalı.");

  const sip = await getSiparis(siparisId);
  if (!sip) throw new Error("Sipariş bulunamadı.");

  const rotalar = sip.rota_listesi.length ? sip.rota_listesi : normalizeRota(sip.rotalar);
  if (!rotalar.includes(istasyon)) {
    throw new Error(`'${istasyon}' bu siparişin rotasında yok.`);
  }

  const hareketler = await getHareketler(siparisId);
  const ozet = asamaOzetHesapla(sip, hareketler);
  const mevcut = ozet.asamalar.find((a) => a.istasyon === istasyon) || {
    stok: 0,
    gelen: 0,
    cikan: 0,
    fire: 0,
    istasyon,
    sira: 0,
  };

  if ((tur === "cikis" || tur === "fire") && adet > mevcut.stok) {
    throw new Error(
      `${istasyon} stokunda ${mevcut.stok} adet var; ${adet} adet ${tur} yapılamaz.`,
    );
  }
  if (tur === "fire" && !(opts.neden || "").trim()) {
    throw new Error("Fire için neden seçilmeli.");
  }

  const batch = writeBatch(getDb());
  const ana = yeniHareketBelgesi(siparisId, istasyon, tur, adet, opts);
  batch.set(doc(hareketlerCol(siparisId), ana.id), ana.data);

  const sonrakiAktar = opts.sonraki_aktar !== false;
  if (tur === "cikis" && sonrakiAktar) {
    const hedefler = paralelGirisHedefleri(rotalar, istasyon);
    if (hedefler.length > 1) {
      const paylar = kapasiteyiBol(adet, hedefler.map(() => 1));
      hedefler.forEach((hedef, i) => {
        const pay = paylar[i] || 0;
        if (pay <= 0) return;
        const h = yeniHareketBelgesi(siparisId, hedef, "giris", pay, {
          kullanici: opts.kullanici,
          not_metin: `Otomatik aktarım ← ${istasyon} (paralel)`,
          auto: true,
        });
        batch.set(doc(hareketlerCol(siparisId), h.id), h.data);
      });
    } else if (hedefler.length === 1) {
      const h = yeniHareketBelgesi(siparisId, hedefler[0], "giris", adet, {
        kullanici: opts.kullanici,
        not_metin: `Otomatik aktarım ← ${istasyon}`,
        auto: true,
      });
      batch.set(doc(hareketlerCol(siparisId), h.id), h.data);
    }
  }

  const simdi = new Date().toISOString().slice(0, 19);
  const guncelleme: Record<string, unknown> = { guncelleme: simdi, source: "web" };
  if (sip.durum === "Beklemede") guncelleme.durum = "Üretimde";
  batch.update(doc(siparislerCol(), siparisId), guncelleme);

  await batch.commit();

  const yeniHareketler = await getHareketler(siparisId);
  return asamaOzetHesapla(sip, yeniHareketler);
}

export async function istasyonSiparisleri(makine: string): Promise<IstasyonSiparis[]> {
  const snap = await getDocs(siparislerCol());
  const sonuc: IstasyonSiparis[] = [];

  for (const d of snap.docs) {
    const sip = docToSiparis(d.id, d.data());
    if (sip.deleted || sip.durum === "Tamamlandı") continue;
    const rotalar = sip.rota_listesi.length ? sip.rota_listesi : normalizeRota(sip.rotalar);
    if (makine && !rotalar.includes(makine)) continue;

    const hareketler = await getHareketler(sip.id);
    const ozet = asamaOzetHesapla(sip, hareketler);
    const ist = ozet.asamalar.find((a) => a.istasyon === makine);

    sonuc.push({
      id: sip.id,
      musteri: sip.musteri,
      urun: sip.urun,
      olcu: sip.olcu,
      adet: sip.adet,
      hazir_adet: sip.hazir_adet,
      durum: sip.durum,
      aktif_istasyon: ozet.aktif_istasyon,
      aktif_stok: ozet.aktif_stok,
      istasyon_stok: ist?.stok ?? 0,
      istasyon_gelen: ist?.gelen ?? 0,
      istasyon_cikan: ist?.cikan ?? 0,
      istasyon_fire: ist?.fire ?? 0,
    });
  }

  return sonuc;
}

export function sevkQrUrl(siparisId: string, siteUrl?: string): string {
  const base = (siteUrl || (typeof window !== "undefined" ? window.location.origin : "")).replace(/\/$/, "");
  return `${base}/sevk/${encodeURIComponent(siparisId)}`;
}
