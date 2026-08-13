"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Toast, useToast } from "@/components/Toast";
import { useAuth } from "@/components/AuthProvider";
import { TUM_MAKINELER } from "@/lib/constants";
import { siparisEkle, subscribeSiparisler } from "@/lib/firestore";
import type { Siparis } from "@/lib/types";

const VARSAYILAN_ROTA = ["Kesim", "Rodaj 1", "Rodaj 2", "Isıl Temper"];

function bugunBitis(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

function OfisContent() {
  const { profil, logout } = useAuth();
  const router = useRouter();
  const { message, show } = useToast();
  const [siparisler, setSiparisler] = useState<Siparis[]>([]);
  const [arama, setArama] = useState("");
  const [busy, setBusy] = useState(false);
  const [formAcik, setFormAcik] = useState(false);

  const [musteri, setMusteri] = useState("");
  const [urun, setUrun] = useState("");
  const [olcu, setOlcu] = useState("");
  const [adet, setAdet] = useState("1");
  const [bitis, setBitis] = useState(bugunBitis());
  const [oncelik, setOncelik] = useState("Normal");
  const [rota, setRota] = useState<string[]>([...VARSAYILAN_ROTA]);

  useEffect(() => {
    // Sadece gerçek saha rolü ofisten çıkarılsın (admin/ofis e-posta resolveProfil ile korunur)
    if (profil && profil.rol === "saha") {
      router.replace("/mobile");
    }
  }, [profil, router]);

  useEffect(() => {
    return subscribeSiparisler(setSiparisler, (e) => show(e.message));
  }, [show]);

  const filtreli = useMemo(() => {
    const q = arama.toLowerCase().trim();
    return siparisler.filter(
      (s) => !q || `${s.musteri} ${s.urun} ${s.id}`.toLowerCase().includes(q),
    );
  }, [siparisler, arama]);

  function toggleMakine(m: string) {
    setRota((prev) =>
      prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m],
    );
  }

  async function kaydet(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const s = await siparisEkle({
        musteri,
        urun,
        olcu,
        adet: parseInt(adet, 10) || 0,
        bitis,
        oncelik,
        rotalar: rota,
      });
      show(`Sipariş kaydedildi: ${s.id}`);
      setMusteri("");
      setUrun("");
      setOlcu("");
      setAdet("1");
      setBitis(bugunBitis());
      setOncelik("Normal");
      setRota([...VARSAYILAN_ROTA]);
      setFormAcik(false);
    } catch (err) {
      show(err instanceof Error ? err.message : "Kayıt hatası");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="mob-header ofis-header">
        <h1>📋 BYC Ofis</h1>
        <span>
          {profil?.ad || profil?.kullanici_adi}
          {profil?.rol ? ` (${profil.rol})` : ""}
        </span>
        <Link href="/ofis">📋 Ofis</Link>
        <Link href="/istasyon">🏭 İstasyon</Link>
        <Link href="/mobile">📱 Saha</Link>
        <button
          type="button"
          className="link-btn"
          onClick={() => logout().then(() => router.push("/login"))}
        >
          Çıkış
        </button>
      </header>

      <section className="mob-section">
        <div className="ofis-toolbar">
          <input
            type="search"
            className="mob-input"
            placeholder="Sipariş ara…"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
          />
          <button
            type="button"
            className="login-btn ofis-yeni-btn"
            onClick={() => setFormAcik((v) => !v)}
          >
            {formAcik ? "Formu kapat" : "+ Yeni sipariş"}
          </button>
        </div>
        <p className="mob-hint">
          Buradan eklenen siparişler anında Firebase&apos;e yazılır; istasyon ekranı
          aynı listeden görür. (PC&apos;deki Gantt/Excel hâlâ yerel Flask&apos;ta.)
        </p>
      </section>

      {formAcik && (
        <section className="mob-section ofis-form-card">
          <h2>Yeni sipariş</h2>
          <form onSubmit={kaydet} className="ofis-form">
            <div className="form-group">
              <label>Müşteri *</label>
              <input
                className="mob-input"
                value={musteri}
                onChange={(e) => setMusteri(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Ürün *</label>
              <input
                className="mob-input"
                value={urun}
                onChange={(e) => setUrun(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Ölçü</label>
              <input
                className="mob-input"
                value={olcu}
                onChange={(e) => setOlcu(e.target.value)}
                placeholder="örn. 400x300x4"
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Adet *</label>
                <input
                  className="mob-input"
                  type="number"
                  min={1}
                  value={adet}
                  onChange={(e) => setAdet(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Sevk (GG.AA.YYYY)</label>
                <input
                  className="mob-input"
                  value={bitis}
                  onChange={(e) => setBitis(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Öncelik</label>
                <select
                  className="mob-input"
                  value={oncelik}
                  onChange={(e) => setOncelik(e.target.value)}
                >
                  <option>Normal</option>
                  <option>Acil</option>
                  <option>Düşük</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>İşlem sırası (rota)</label>
              <div className="rota-grid">
                {TUM_MAKINELER.map((m) => (
                  <label key={m} className="rota-chip">
                    <input
                      type="checkbox"
                      checked={rota.includes(m)}
                      onChange={() => toggleMakine(m)}
                    />
                    {m}
                  </label>
                ))}
              </div>
            </div>
            <button type="submit" className="login-btn" disabled={busy}>
              {busy ? "Kaydediliyor…" : "Siparişi kaydet"}
            </button>
          </form>
        </section>
      )}

      <section className="mob-section">
        <h2>Siparişler ({filtreli.length})</h2>
        <div className="mob-list">
          {filtreli.length === 0 ? (
            <p className="mob-hint">Henüz sipariş yok — yukarıdan ekleyin.</p>
          ) : (
            filtreli.map((s) => (
              <div key={s.id} className="mob-card-item ofis-siparis-card">
                <strong>
                  {s.musteri} · {s.urun}
                </strong>
                <span>
                  {s.adet} adet · {s.durum} · {s.oncelik}
                  {s.olcu ? ` · ${s.olcu}` : ""}
                </span>
                <span className="mob-hint">Rota: {s.rotalar || "—"}</span>
                <span className="mob-hint">ID: {s.id}</span>
              </div>
            ))
          )}
        </div>
      </section>

      <Toast message={message} />
    </>
  );
}

export default function OfisPage() {
  return (
    <ProtectedRoute>
      <OfisContent />
    </ProtectedRoute>
  );
}
