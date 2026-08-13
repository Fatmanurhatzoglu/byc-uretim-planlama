"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Toast, useToast } from "@/components/Toast";
import { useAuth } from "@/components/AuthProvider";
import { kpiFromSiparisler } from "@/lib/asama";
import { subscribeSiparisler } from "@/lib/firestore";
import type { Siparis } from "@/lib/types";

function MobileContent() {
  const { profil, logout } = useAuth();
  const router = useRouter();
  const { message, show } = useToast();
  const [siparisler, setSiparisler] = useState<Siparis[]>([]);
  const [arama, setArama] = useState("");

  useEffect(() => {
    return subscribeSiparisler(setSiparisler, (e) => show(e.message));
  }, [show]);

  const kpi = useMemo(() => kpiFromSiparisler(siparisler), [siparisler]);

  const filtreli = useMemo(() => {
    const q = arama.toLowerCase().trim();
    return siparisler.filter(
      (s) =>
        s.durum !== "Tamamlandı" &&
        (!q || `${s.musteri} ${s.urun}`.toLowerCase().includes(q)),
    );
  }, [siparisler, arama]);

  return (
    <>
      <header className="mob-header">
        <h1>📱 BYC Saha</h1>
        <span>{profil?.ad || profil?.kullanici_adi}</span>
        <Link href="/ofis">📋 Ofis</Link>
        <Link href="/istasyon">🏭 İstasyon</Link>
        <button type="button" className="link-btn" onClick={() => logout().then(() => router.push("/login"))}>
          Çıkış
        </button>
      </header>

      <section className="mob-kpi">
        <div className="mob-kpi-item">
          <span>Aktif</span>
          <strong>{kpi.aktif}</strong>
        </div>
        <div className="mob-kpi-item warning">
          <span>Üretimde</span>
          <strong>{kpi.uretimde}</strong>
        </div>
        <div className="mob-kpi-item danger">
          <span>Acil</span>
          <strong>{kpi.acil}</strong>
        </div>
        <div className="mob-kpi-item">
          <span>Kalan</span>
          <strong>{kpi.kalan_adet}</strong>
        </div>
      </section>

      <section className="mob-section">
        <h2>Hızlı Sevk</h2>
        <input
          type="search"
          className="mob-input"
          placeholder="Sipariş ara..."
          value={arama}
          onChange={(e) => setArama(e.target.value)}
        />
        <div className="mob-list">
          {filtreli.length === 0 ? (
            <p className="mob-hint">Aktif sipariş yok</p>
          ) : (
            filtreli.map((s) => {
              const kalan = Math.max(0, s.adet - s.hazir_adet);
              return (
                <button
                  key={s.id}
                  type="button"
                  className="mob-card-item"
                  onClick={() => router.push(`/sevk/${s.id}`)}
                >
                  <strong>{s.musteri}</strong>
                  <span>
                    {s.urun} — Kalan: {kalan}
                  </span>
                  {s.oncelik === "Acil" && <span className="mob-badge">{s.oncelik}</span>}
                </button>
              );
            })
          )}
        </div>
      </section>

      <section className="mob-section">
        <p className="mob-hint">
          QR kodlar fabrika panelinden üretilir; okutunca sevk sayfası açılır.
        </p>
      </section>

      <Toast message={message} />
    </>
  );
}

export default function MobilePage() {
  return (
    <ProtectedRoute>
      <MobileContent />
    </ProtectedRoute>
  );
}
