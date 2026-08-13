export const FIREBASE_ROOT = "byc";
export const FIREBASE_SCHEMA_VERSION = "v1";

export const TUM_MAKINELER = [
  "Kesim",
  "Rodaj 1",
  "Rodaj 2",
  "Çin Rodajı",
  "Su Jeti",
  "Lazer Kesim",
  "Kimyasal Temper",
  "Büyük Temper",
  "Isıl Temper",
  "Vakum AR Kaplama",
  "Daldırma",
  "Serigrafi Baskı",
  "Laminasyon",
] as const;

export const PARALEL_GRUPLAR: readonly (readonly string[])[] = [
  ["Rodaj 1", "Rodaj 2"],
];

export const FIRE_NEDENLERI = [
  "Çatlak",
  "Çizik",
  "Ölçü hatası",
  "Kenar hatası",
  "Köpük / kalite",
  "Kırık",
  "Temper hatası",
  "Kaplama hatası",
  "Baskı hatası",
  "Lamine hatası",
  "Diğer",
];

export const ROLLER = ["admin", "ofis", "saha"] as const;
export type Rol = (typeof ROLLER)[number];

/** Firebase Auth e-posta formatı: admin → admin@byc.net.tr */
export const AUTH_EMAIL_DOMAIN = "byc.net.tr";

export function kullaniciAdiToEmail(kullaniciAdi: string): string {
  const u = kullaniciAdi.trim().toLowerCase();
  if (u.includes("@")) return u;
  return `${u}@${AUTH_EMAIL_DOMAIN}`;
}

export function emailToKullaniciAdi(email: string): string {
  return email.split("@")[0] || email;
}

/** Giriş sonrası varsayılan sayfa */
export function homePathForRol(rol?: string | null): string {
  if (rol === "admin" || rol === "ofis") return "/ofis";
  return "/mobile";
}

/** Profil yoksa e-postadan makul rol */
export function rolFromKullaniciAdi(kullaniciAdi: string): "admin" | "ofis" | "saha" {
  const u = kullaniciAdi.trim().toLowerCase();
  if (u === "admin") return "admin";
  if (u === "ofis") return "ofis";
  return "saha";
}

/** Firestore profil + e-posta — admin/ofis e-posta her zaman ofis yetkisi alır */
export function resolveProfil(
  email: string,
  remote: KullaniciProfil | null,
): KullaniciProfil {
  const ka = emailToKullaniciAdi(email || "");
  const emailRol = rolFromKullaniciAdi(ka);
  if (emailRol === "admin" || emailRol === "ofis") {
    return {
      kullanici_adi: remote?.kullanici_adi || ka,
      ad: remote?.ad || (emailRol === "admin" ? "Yönetici" : "Ofis"),
      rol: emailRol,
    };
  }
  if (remote?.rol) {
    return {
      kullanici_adi: remote.kullanici_adi || ka,
      ad: remote.ad || ka,
      rol: remote.rol,
    };
  }
  return { kullanici_adi: ka, ad: ka, rol: "saha" };
}

export function isOfisRol(rol?: string | null): boolean {
  return rol === "admin" || rol === "ofis";
}
