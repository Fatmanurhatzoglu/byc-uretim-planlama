"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Toast, useToast } from "@/components/Toast";
import { getSiparis, sevkGuncelle } from "@/lib/firestore";
import type { Siparis } from "@/lib/types";

function SevkContent() {
  const params = useParams();
  const siparisId = String(params.id || "");
  const { message, show } = useToast();
  const [siparis, setSiparis] = useState<Siparis | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getSiparis(siparisId)
      .then(setSiparis)
      .catch((e) => show(e.message))
      .finally(() => setLoading(false));
  }, [siparisId, show]);

  async function onSevk(e: FormEvent) {
    e.preventDefault();
    const fd = new FormData(e.target as HTMLFormElement);
    const adet = parseInt(String(fd.get("adet") || "0"), 10);
    if (!adet || adet <= 0) {
      show("Geçerli adet girin");
      return;
    }
    setBusy(true);
    try {
      const guncel = await sevkGuncelle(siparisId, adet);
      setSiparis(guncel);
      (e.target as HTMLFormElement).reset();
      show(`✅ ${adet} adet sevk edildi`);
    } catch (err) {
      show(err instanceof Error ? err.message : "Hata");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <div className="loading-screen"><p>Yükleniyor…</p></div>;
  }

  if (!siparis) {
    return (
      <div className="mob-card">
        <p>Sipariş bulunamadı.</p>
        <Link href="/mobile">← Geri</Link>
      </div>
    );
  }

  const kalan = Math.max(0, siparis.adet - siparis.hazir_adet);

  return (
    <>
      <header className="mob-header">
        <h1>📦 Sevk</h1>
        <Link href="/mobile">← Geri</Link>
      </header>
      <div className="mob-card">
        <h2>{siparis.musteri}</h2>
        <p>
          <strong>{siparis.urun}</strong> — {siparis.olcu || "-"}
        </p>
        <div className="mob-stats">
          <div>
            <span>Toplam</span>
            <strong>{siparis.adet}</strong>
          </div>
          <div>
            <span>Sevk Edilen</span>
            <strong>{siparis.hazir_adet}</strong>
          </div>
          <div>
            <span>Kalan</span>
            <strong>{kalan}</strong>
          </div>
        </div>
        <form onSubmit={onSevk}>
          <div className="form-group">
            <label>Sevk Adedi</label>
            <input name="adet" type="number" className="mob-input" min={1} max={kalan} required />
          </div>
          <button type="submit" className="btn-mob" disabled={busy || kalan <= 0}>
            {kalan <= 0 ? "Tamamlandı" : busy ? "Kaydediliyor…" : "Sevk Et"}
          </button>
        </form>
      </div>
      <Toast message={message} />
    </>
  );
}

export default function SevkPage() {
  return (
    <ProtectedRoute>
      <SevkContent />
    </ProtectedRoute>
  );
}
