"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import { isOfisRol } from "@/lib/constants";

export default function HomePage() {
  const { user, profil, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="loading-screen">
        <p>Yükleniyor…</p>
      </div>
    );
  }

  const ofis = isOfisRol(profil?.rol);

  return (
    <div className="menu-body">
      <div className="menu-card">
        <h1>BYC Üretim</h1>
        <p className="menu-sub">
          {profil?.ad || profil?.kullanici_adi || "Kullanıcı"}
          {profil?.rol ? ` · ${profil.rol}` : ""}
        </p>
        <p className="mob-hint">Hangi ekranı açmak istiyorsunuz?</p>

        <Link href="/ofis" className="menu-btn menu-btn-ofis">
          📋 Ofis
          <small>Sipariş ekle / listele</small>
        </Link>

        <Link href="/istasyon" className="menu-btn menu-btn-istasyon">
          🏭 İstasyon
          <small>Makine giriş / çıkış / fire</small>
        </Link>

        <Link href="/mobile" className="menu-btn menu-btn-saha">
          📱 Saha
          <small>Sevk ve hızlı bakış</small>
        </Link>

        {!ofis && (
          <p className="mob-hint" style={{ marginTop: 12 }}>
            Ofiste sipariş kaydetmek için <strong>ofis</strong> veya{" "}
            <strong>admin</strong> ile giriş yapın.
          </p>
        )}

        <button
          type="button"
          className="link-btn"
          style={{ marginTop: 16 }}
          onClick={() => logout().then(() => router.push("/login"))}
        >
          Çıkış
        </button>
      </div>
    </div>
  );
}
