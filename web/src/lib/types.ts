export type HareketTur = "giris" | "cikis" | "fire";

export interface Siparis {
  id: string;
  musteri: string;
  urun: string;
  olcu: string;
  adet: number;
  hazir_adet: number;
  kalan_adet: number;
  bitis: string;
  durum: string;
  oncelik: string;
  rotalar: string;
  rota_listesi: string[];
  deleted: boolean;
  guncelleme: string;
  uretim_detay?: Record<string, unknown>;
}

export interface Hareket {
  client_uid: string;
  siparis_id: string;
  istasyon: string;
  tur: HareketTur;
  adet: number;
  neden: string;
  not_metin: string;
  kullanici: string;
  zaman: string;
  auto?: boolean;
}

export interface AsamaItem {
  istasyon: string;
  sira: number;
  gelen: number;
  cikan: number;
  fire: number;
  stok: number;
}

export interface AsamaOzet {
  siparis_id: string;
  musteri: string;
  urun: string;
  adet: number;
  hazir_adet: number;
  durum: string;
  rotalar: string[];
  asamalar: AsamaItem[];
  aktif_istasyon: string;
  aktif_stok: number;
}

export interface KullaniciProfil {
  kullanici_adi: string;
  ad: string;
  rol: "admin" | "ofis" | "saha";
}

export interface IstasyonSiparis {
  id: string;
  musteri: string;
  urun: string;
  olcu: string;
  adet: number;
  hazir_adet: number;
  durum: string;
  aktif_istasyon: string;
  aktif_stok: number;
  istasyon_stok: number;
  istasyon_gelen: number;
  istasyon_cikan: number;
  istasyon_fire: number;
}
