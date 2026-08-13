"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Toast, useToast } from "@/components/Toast";
import { useAuth } from "@/components/AuthProvider";
import { asamaSiraUyarisi } from "@/lib/asama";
import { FIRE_NEDENLERI, TUM_MAKINELER } from "@/lib/constants";
import {
  getAsamaOzet,
  hareketEkle,
  istasyonSiparisleri,
} from "@/lib/firestore";
import { makineListesi } from "@/lib/rota";
import type { AsamaOzet, HareketTur, IstasyonSiparis } from "@/lib/types";

const LS_KEY = "byc_istasyon_makine";

type Ekran = "makine" | "liste" | "islem";

function IstasyonContent() {
  const { profil, logout } = useAuth();
  const router = useRouter();
  const { message, show } = useToast();

  const makineler = useMemo(() => makineListesi(TUM_MAKINELER), []);

  const [ekran, setEkran] = useState<Ekran>("makine");
  const [seciliMakine, setSeciliMakine] = useState("");
  const [liste, setListe] = useState<IstasyonSiparis[]>([]);
  const [arama, setArama] = useState("");
  const [seciliSiparisId, setSeciliSiparisId] = useState("");
  const [ozet, setOzet] = useState<AsamaOzet | null>(null);
  const [seciliTur, setSeciliTur] = useState<HareketTur | "kesim">("cikis");
  const [adet, setAdet] = useState("1");
  const [neden, setNeden] = useState(FIRE_NEDENLERI[0]);
  const [not, setNot] = useState("");
  const [sonrakiAktar, setSonrakiAktar] = useState(true);
  const [busy, setBusy] = useState(false);

  const isKesim = seciliMakine === "Kesim";

  useEffect(() => {
    const saved = localStorage.getItem(LS_KEY) || "";
    const m = saved === "Rodaj" ? "Rodaj 1" : saved;
    if (m && makineler.includes(m)) {
      setSeciliMakine(m);
      setEkran("liste");
    }
  }, [makineler]);

  const yukleListe = useCallback(async () => {
    if (!seciliMakine) return;
    try {
      const rows = await istasyonSiparisleri(seciliMakine);
      setListe(rows);
    } catch (e) {
      show(e instanceof Error ? e.message : "Liste yüklenemedi");
    }
  }, [seciliMakine, show]);

  useEffect(() => {
    if (ekran === "liste" && seciliMakine) yukleListe();
  }, [ekran, seciliMakine, yukleListe]);

  async function makineSec(m: string) {
    setSeciliMakine(m);
    localStorage.setItem(LS_KEY, m);
    setSeciliTur(m === "Kesim" ? "kesim" : "cikis");
    setEkran("liste");
  }

  async function siparisAc(id: string) {
    try {
      const o = await getAsamaOzet(id);
      if (!o) {
        show("Sipariş bulunamadı");
        return;
      }
      if (!o.rotalar.includes(seciliMakine)) {
        show("Bu siparişin rotasında seçili makine yok");
        return;
      }
      setSeciliSiparisId(id);
      setOzet(o);
      setEkran("islem");
    } catch (e) {
      show(e instanceof Error ? e.message : "Hata");
    }
  }

  const filtreliListe = useMemo(() => {
    const q = arama.toLowerCase().trim();
    return liste.filter(
      (s) =>
        !q ||
        `${s.musteri} ${s.urun} ${s.olcu}`.toLowerCase().includes(q),
    );
  }, [liste, arama]);

  const istOzet = ozet?.asamalar.find((a) => a.istasyon === seciliMakine);

  async function kaydet() {
    if (!seciliSiparisId || !seciliMakine || !ozet) return;

    let tur: HareketTur = seciliTur === "kesim" ? "cikis" : seciliTur;
    let parcaAdet = parseInt(adet, 10);
    let notMetin = not.trim();

    if (isKesim && seciliTur !== "fire") {
      if (!parcaAdet || parcaAdet <= 0) {
        show("Geçerli kesilen parça adedi girin");
        return;
      }
      tur = "cikis";
      notMetin = [notMetin, `Kesim: ${parcaAdet} parça`].filter(Boolean).join(" · ");
    } else {
      if (!parcaAdet || parcaAdet <= 0) {
        show("Geçerli adet girin");
        return;
      }
    }

    const uyariTur = tur;
    const uyari = asamaSiraUyarisi(ozet, seciliMakine, uyariTur);
    if (uyari) {
      const ok = window.confirm(`Sıra uyarısı:\n${uyari}\n\nYine de kaydedilsin mi?`);
      if (!ok) return;
    }

    setBusy(true);
    try {
      const yeni = await hareketEkle(seciliSiparisId, seciliMakine, tur, parcaAdet, {
        neden: tur === "fire" ? neden : "",
        not_metin: notMetin,
        kullanici: profil?.kullanici_adi || "",
        sonraki_aktar: sonrakiAktar,
      });
      setOzet(yeni);
      setNot("");
      show("Kaydedildi");
      await yukleListe();
    } catch (e) {
      show(e instanceof Error ? e.message : "Kayıt hatası");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="mob-header">
        <h1>🏭 İstasyon</h1>
        <span>{seciliMakine || "Makine seçin"}</span>
        {(profil?.rol === "admin" || profil?.rol === "ofis") && (
          <Link href="/ofis">Ofis</Link>
        )}
        <Link href="/mobile">Saha</Link>
        <button type="button" className="link-btn" onClick={() => logout().then(() => router.push("/login"))}>
          Çıkış
        </button>
      </header>

      {ekran === "makine" && (
        <section className="mob-section">
          <h2>Bu cihaz hangi makine?</h2>
          <p className="mob-hint">Seçiminiz bu cihazda hatırlanır.</p>
          <div className="makine-grid">
            {makineler.map((m) => (
              <button key={m} type="button" className="makine-btn" onClick={() => makineSec(m)}>
                {m}
              </button>
            ))}
          </div>
        </section>
      )}

      {ekran === "liste" && (
        <section className="mob-section">
          <div className="ist-toolbar">
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                localStorage.removeItem(LS_KEY);
                setSeciliMakine("");
                setEkran("makine");
              }}
            >
              ← Makine değiştir
            </button>
            <strong>{seciliMakine}</strong>
          </div>
          <input
            type="search"
            className="mob-input"
            placeholder="Müşteri / ürün ara..."
            value={arama}
            onChange={(e) => setArama(e.target.value)}
          />
          <div className="mob-list">
            {filtreliListe.length === 0 ? (
              <p className="mob-hint">Bu makinede bekleyen sipariş yok.</p>
            ) : (
              filtreliListe.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`mob-card-item ${s.istasyon_stok > 0 ? "ist-card-aktif" : ""}`}
                  onClick={() => siparisAc(s.id)}
                >
                  <strong>{s.musteri}</strong>
                  <span>
                    {s.urun} · {s.olcu || "-"}
                  </span>
                  <span className="stok-pill">
                    {seciliMakine} stok: {s.istasyon_stok}
                  </span>
                  <span style={{ display: "block", fontSize: 12, marginTop: 4, color: "#64748b" }}>
                    Aktif: {s.aktif_istasyon} · Gelen {s.istasyon_gelen} / Çıkan {s.istasyon_cikan} / Fire{" "}
                    {s.istasyon_fire}
                  </span>
                </button>
              ))
            )}
          </div>
        </section>
      )}

      {ekran === "islem" && ozet && (
        <section className="mob-section">
          <div className="ist-toolbar">
            <button type="button" className="btn-ghost" onClick={() => setEkran("liste")}>
              ← Listeye dön
            </button>
          </div>
          <div className="mob-card">
            <strong>{ozet.musteri}</strong>
            <span>
              {ozet.urun} · Toplam {ozet.adet}
            </span>
            <div className="mob-stats cols-4" style={{ marginTop: 12 }}>
              <div>
                <span>Stok</span>
                <strong>{istOzet?.stok ?? 0}</strong>
              </div>
              <div>
                <span>Gelen</span>
                <strong>{istOzet?.gelen ?? 0}</strong>
              </div>
              <div>
                <span>Çıkan</span>
                <strong>{istOzet?.cikan ?? 0}</strong>
              </div>
              <div>
                <span>Fire</span>
                <strong>{istOzet?.fire ?? 0}</strong>
              </div>
            </div>
            <p className="mob-hint">
              Aktif: {ozet.aktif_istasyon}
              {ozet.aktif_stok ? ` (${ozet.aktif_stok} stok)` : ""}
            </p>
            {isKesim && (
              <p className="kesim-not">
                Plaka stok düşümü fabrika panelinde yapılır. Burada kesim çıkışı kaydedilir; veri Firestore&apos;a
                yazılır ve fabrika ile senkronlanır.
              </p>
            )}
          </div>

          <div className="mob-card">
            {!isKesim ? (
              <div className="tur-btns">
                <button
                  type="button"
                  className={`tur-btn giris ${seciliTur === "giris" ? "aktif" : ""}`}
                  onClick={() => setSeciliTur("giris")}
                >
                  + Giriş
                </button>
                <button
                  type="button"
                  className={`tur-btn ${seciliTur === "cikis" ? "aktif" : ""}`}
                  onClick={() => setSeciliTur("cikis")}
                >
                  ✓ İyi çıktı
                </button>
                <button
                  type="button"
                  className={`tur-btn fire ${seciliTur === "fire" ? "aktif" : ""}`}
                  onClick={() => setSeciliTur("fire")}
                >
                  Fire
                </button>
              </div>
            ) : (
              <div className="tur-btns" style={{ gridTemplateColumns: "1fr 1fr" }}>
                <button
                  type="button"
                  className={`tur-btn ${seciliTur === "kesim" ? "aktif" : ""}`}
                  onClick={() => setSeciliTur("kesim")}
                >
                  ✂ Kesim kaydı
                </button>
                <button
                  type="button"
                  className={`tur-btn fire ${seciliTur === "fire" ? "aktif" : ""}`}
                  onClick={() => setSeciliTur("fire")}
                >
                  Fire
                </button>
              </div>
            )}

            <div className="form-group">
              <label>
                {seciliTur === "fire"
                  ? isKesim
                    ? "Fire parça adedi"
                    : "Fire adedi"
                  : seciliTur === "giris"
                    ? "Giriş adedi"
                    : isKesim
                      ? "Kesilen parça adedi"
                      : "Çıkan adet"}
              </label>
              <input
                type="number"
                className="mob-input"
                min={1}
                value={adet}
                onChange={(e) => setAdet(e.target.value)}
              />
            </div>

            {seciliTur === "fire" && (
              <div className="form-group">
                <label>Fire nedeni</label>
                <select className="mob-input" value={neden} onChange={(e) => setNeden(e.target.value)}>
                  {FIRE_NEDENLERI.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="form-group">
              <label>Not (opsiyonel)</label>
              <input
                type="text"
                className="mob-input"
                value={not}
                onChange={(e) => setNot(e.target.value)}
                placeholder="Kısa not"
              />
            </div>

            {seciliTur !== "fire" && (
              <label className="chk-line">
                <input type="checkbox" checked={sonrakiAktar} onChange={(e) => setSonrakiAktar(e.target.checked)} />
                İyi çıktıda sonraki aşamaya otomatik aktar
              </label>
            )}

            <button type="button" className="btn-mob" onClick={kaydet} disabled={busy}>
              {busy ? "Kaydediliyor…" : "💾 Kaydet"}
            </button>
          </div>
        </section>
      )}

      <Toast message={message} />
    </>
  );
}

export default function IstasyonPage() {
  return (
    <ProtectedRoute>
      <IstasyonContent />
    </ProtectedRoute>
  );
}
