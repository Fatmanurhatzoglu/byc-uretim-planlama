"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { homePathForRol } from "@/lib/constants";

export default function LoginPage() {
  const { login, user, profil, loading, configHata } = useAuth();
  const router = useRouter();
  const [hata, setHata] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user && profil) {
      router.replace(homePathForRol(profil.rol));
    }
  }, [user, profil, loading, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setHata("");
    setBusy(true);
    const fd = new FormData(e.target as HTMLFormElement);
    const kullaniciAdi = String(fd.get("kullanici_adi") || "");
    const sifre = String(fd.get("sifre") || "");
    try {
      await login(kullaniciAdi, sifre);
      const rol =
        kullaniciAdi.trim().toLowerCase() === "admin" ||
        kullaniciAdi.trim().toLowerCase() === "ofis"
          ? kullaniciAdi.trim().toLowerCase()
          : "saha";
      router.replace(homePathForRol(rol));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("auth/unauthorized-domain") || msg.includes("unauthorized-domain")) {
        setHata(
          "Bu site adresi Firebase'de yetkili değil. Console → Authentication → Settings → Authorized domains: byc-uretim.vercel.app ekleyin.",
        );
      } else if (msg.includes("auth/invalid-credential") || msg.includes("auth/wrong-password") || msg.includes("auth/user-not-found")) {
        setHata("Kullanıcı adı veya şifre hatalı.");
      } else if (msg.includes("auth/network-request-failed")) {
        setHata("Ağ hatası — interneti kontrol edin.");
      } else {
        setHata(msg || "Giriş başarısız. Kullanıcı adı ve şifreyi kontrol edin.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-body">
      <div className="login-card">
        <div className="login-brand">
          <div className="brand-icon">⚙</div>
          <h1>BYC Üretim Planlama</h1>
          <p>Devam etmek için giriş yapın</p>
        </div>
        {configHata && <div className="login-error">{configHata}</div>}
        {hata && <div className="login-error">{hata}</div>}
        <form onSubmit={onSubmit}>
          <div className="form-group">
            <label>Kullanıcı Adı</label>
            <input name="kullanici_adi" className="mob-input" required autoFocus />
          </div>
          <div className="form-group">
            <label>Şifre</label>
            <input name="sifre" type="password" className="mob-input" required />
          </div>
          <button type="submit" className="login-btn" disabled={busy || !!configHata}>
            {busy ? "Giriş yapılıyor…" : "Giriş Yap"}
          </button>
        </form>
        <div className="login-hint">
          <p>
            Doğru adres: <code>https://byc-uretim.vercel.app</code>
          </p>
          <p>
            <strong>ofis</strong> / <strong>admin</strong> → Ofis · <strong>saha</strong> → Saha
          </p>
        </div>
      </div>
    </div>
  );
}
