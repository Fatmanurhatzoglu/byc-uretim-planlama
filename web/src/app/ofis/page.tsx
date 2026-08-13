"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Toast, useToast } from "@/components/Toast";
import { useAuth } from "@/components/AuthProvider";
import { TUM_MAKINELER, isOfisRol } from "@/lib/constants";
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
  const yetki = isOfisRol(profil?.rol);

  const [musteri, setMusteri] = useState("");
  const [urun, setUrun] = useState("");
  const [olcu, setOlcu] = useState("");
  const [adet, setAdet] = useState("1");
  const [bitis, setBitis] = useState(bugunBitis());
  const [oncelik, setOncelik] = useState("Normal");
  const [rota, setRota] = useState<string[]>([...VARSAYILAN_ROTA]);

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
    if (!yetki) {
      show("Sipariş ekleme yetkisi yok");
      return;
    }
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
      setFormAcik(false);
    } catch (err) {
      show(err instanceof Error ? err.message : "Kayıt hatası");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="mob-header" style={{ flexWrap: "wrap", gap: 8 }}>
        <h1>📋 Yönetici / Ofis</h1>
        <span>
          {profil?.ad || profil?.kullanici_adi} ({profil?.rol || "?"})
        </span>
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
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <input
            type="search"
            className="mob-input"
            placeholder="Sipariş ara…"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
            style={{ flex: 1 }}
          />
          {yetki && (
            <button
              type="button"
              className="login-btn"
              style={{ width: "auto", padding: "12px 16px" }}
              onClick={() => setFormAcik((v) => !v)}
            >
              {formAcik ? "Kapat" : "+ Yeni sipariş"}
            </button>
          )}
        </div>
      </section>

      {formAcik && yetki && (
        <section className="mob-section" style={{ background: "#fff", padding: 16, borderRadius: 12 }}>
          <h2>Yeni sipariş</h2>
          <form onSubmit={kaydet}>
            <div className="form-group">
              <label>Müşteri *</label>
              <input className="mob-input" value={musteri} onChange={(e) => setMusteri(e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Ürün *</label>
              <input className="mob-input" value={urun} onChange={(e) => setUrun(e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Ölçü</label>
              <input className="mob-input" value={olcu} onChange={(e) => setOlcu(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Adet *</label>
              <input className="mob-input" type="number" min={1} value={adet} onChange={(e) => setAdet(e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Sevk (GG.AA.YYYY)</label>
              <input className="mob-input" value={bitis} onChange={(e) => setBitis(e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Öncelik</label>
              <select className="mob-input" value={oncelik} onChange={(e) => setOncelik(e.target.value)}>
                <option>Normal</option>
                <option>Acil</option>
                <option>Düşük</option>
              </select>
            </div>
            <div className="form-group">
              <label>Rota</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {TUM_MAKINELER.map((m) => (
                  <label key={m} style={{ fontSize: 13 }}>
                    <input type="checkbox" checked={rota.includes(m)} onChange={() => toggleMakine(m)} /> {m}
                  </label>
                ))}
              </div>
            </div>
            <button type="submit" className="login-btn" disabled={busy}>
              {busy ? "Kaydediliyor…" : "Kaydet"}
            </button>
          </form>
        </section>
      )}

      <section className="mob-section">
        <h2>Siparişler ({filtreli.length})</h2>
        <div className="mob-list">
          {filtreli.length === 0 ? (
            <p className="mob-hint">Sipariş yok</p>
          ) : (
            filtreli.map((s) => (
              <div key={s.id} className="mob-card-item" style={{ cursor: "default", textAlign: "left" }}>
                <strong>
                  {s.musteri} · {s.urun}
                </strong>
                <span>
                  {s.adet} adet · {s.durum} · {s.oncelik}
                </span>
                <span className="mob-hint">{s.rotalar}</span>
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
