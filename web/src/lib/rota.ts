import { PARALEL_GRUPLAR } from "./constants";

const ESKI_RODAJ = "Rodaj";
const YENI_RODAJLAR = ["Rodaj 1", "Rodaj 2"];

const PARALEL_UYELIK = new Map<string, ReadonlySet<string>>();
for (const g of PARALEL_GRUPLAR) {
  const fs = new Set(g);
  for (const m of g) PARALEL_UYELIK.set(m, fs);
}

export function paralelGrubu(makine: string): ReadonlySet<string> | undefined {
  return PARALEL_UYELIK.get(makine);
}

function rotaTokenleri(rotalar: string | string[] | undefined): string[] {
  if (Array.isArray(rotalar)) return rotalar.map((x) => String(x).trim()).filter(Boolean);
  return String(rotalar || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

function genisletEskiRodaj(tokens: string[]): string[] {
  const out: string[] = [];
  for (const t of tokens) {
    if (t === ESKI_RODAJ) {
      for (const y of YENI_RODAJLAR) {
        if (!out.includes(y)) out.push(y);
      }
    } else {
      out.push(t);
    }
  }
  return out;
}

export function normalizeRota(rotalar: string | string[] | undefined): string[] {
  return genisletEskiRodaj(rotaTokenleri(rotalar));
}

export function kapasiteyiBol(adet: number, agirliklar: number[]): number[] {
  const n = agirliklar.length;
  if (n === 0) return [];
  if (adet <= 0) return Array(n).fill(0);
  const w = agirliklar.map((x) => Math.max(0, Math.floor(x)));
  if (w.reduce((a, b) => a + b, 0) <= 0) {
    for (let i = 0; i < n; i++) w[i] = 1;
  }
  const toplamW = w.reduce((a, b) => a + b, 0);
  const paylar = w.map((wi) => Math.floor((adet * wi) / toplamW));
  let fark = adet - paylar.reduce((a, b) => a + b, 0);
  const sira = [...Array(n).keys()].sort((a, b) => w[b] - w[a]);
  let i = 0;
  while (fark > 0 && sira.length) {
    paylar[sira[i % n]] += 1;
    fark -= 1;
    i += 1;
  }
  return paylar;
}

export function paralelGirisHedefleri(rotalar: string[], istasyon: string): string[] {
  const tokens = [...rotalar];
  if (!tokens.includes(istasyon)) return [];
  const idx = tokens.indexOf(istasyon);
  let j = idx + 1;
  if (j >= tokens.length) return [];
  const sonraki = tokens[j];
  const grup = paralelGrubu(sonraki);
  if (!grup) return [sonraki];
  const hedefler: string[] = [];
  while (j < tokens.length && grup.has(tokens[j])) {
    if (!hedefler.includes(tokens[j])) hedefler.push(tokens[j]);
    j += 1;
  }
  return hedefler;
}

export function makineListesi(makineler: readonly string[]): string[] {
  const out: string[] = [];
  for (const m of makineler) {
    if (m === ESKI_RODAJ) {
      for (const y of YENI_RODAJLAR) {
        if (!out.includes(y)) out.push(y);
      }
    } else if (!out.includes(m)) {
      out.push(m);
    }
  }
  return out;
}
