"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { homePathForRol, rolFromEmailOrKullanici } from "@/lib/constants";

export default function LoginPage() {
  const { login, user, profil, loading } = useAuth();
  const router = useRouter();
  const [hata, setHata] = useState("");
  const [busy, setBusy] = useState(false);

  // Zaten girişliyse bir kez yönlendir (form submit ile yarışmasın)
  useEffect(() => {
    if (busy) return;
    if (!loading && user && profil) {
      const hedef = homePathForRol(profil.rol);
      if (typeof window !== "undefined" && window.location.pathname === "/login") {
        window.location.replace(hedef);
      }
    }
  }, [user, profil, loading, busy]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setHata("");
    setBusy(true);
    const fd = new FormData(e.target as HTMLFormElement);
    const kullaniciAdi = String(fd.get("kullanici_adi") || "");
    const sifre = String(fd.get("sifre") || "");
    try {
      await login(kullaniciAdi, sifre);
      const hedef = homePathForRol(rolFromEmailOrKullanici(kullaniciAdi));
      // Hard redirect — Next router /mobile yarışını engeller
      window.location.replace(hedef);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("unauthorized-domain")) {
        setHata("Site domain Firebase Authorized domains listesinde değil.");
      } else if (
        msg.includes("invalid-credential") ||
        msg.includes("wrong-password") ||
        msg.includes("user-not-found") ||
        msg.includes("invalid-email")
      ) {
        setHata("E-posta veya şifre hatalı.");
      } else {
        setHata(msg || "Giriş başarısız.");
      }
      setBusy(false);
    }
  }

  return (
    <div className="login-body">
      <div className="login-card">
        <div className="login-brand">
          <div className="brand-icon">⚙</div>
          <h1>BYC Üretim Planlama</h1>
          <p>Yönetici / saha girişi</p>
        </div>
        {hata && <div className="login-error">{hata}</div>}
        <form onSubmit={onSubmit}>
          <div className="form-group">
            <label>E-posta veya kullanıcı adı</label>
            <input
              name="kullanici_adi"
              className="mob-input"
              required
              autoFocus
              placeholder="fatmanur@byc.net.tr"
              defaultValue="fatmanur@byc.net.tr"
            />
          </div>
          <div className="form-group">
            <label>Şifre</label>
            <input name="sifre" type="password" className="mob-input" required />
          </div>
          <button type="submit" className="login-btn" disabled={busy}>
            {busy ? "Giriş yapılıyor…" : "Giriş Yap"}
          </button>
        </form>
        <div className="login-hint">
          <p>
            Yönetici: <code>fatmanur@byc.net.tr</code>
          </p>
          <p>
            Panel:{" "}
            <a href="/ofis" style={{ color: "#2563eb" }}>
              /ofis
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
