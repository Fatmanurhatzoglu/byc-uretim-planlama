"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const [hata, setHata] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/mobile");
  }, [user, loading, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setHata("");
    setBusy(true);
    const fd = new FormData(e.target as HTMLFormElement);
    const kullaniciAdi = String(fd.get("kullanici_adi") || "");
    const sifre = String(fd.get("sifre") || "");
    try {
      await login(kullaniciAdi, sifre);
      router.replace("/mobile");
    } catch (err) {
      setHata(
        err instanceof Error
          ? "Giriş başarısız. Kullanıcı adı ve şifreyi kontrol edin."
          : "Giriş hatası",
      );
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
          <button type="submit" className="login-btn" disabled={busy}>
            {busy ? "Giriş yapılıyor…" : "Giriş Yap"}
          </button>
        </form>
        <div className="login-hint">
          <p>
            <strong>Firebase giriş:</strong> kullanıcı adı olarak{" "}
            <code>admin</code> yazın (e-posta: admin@byc.net.tr).
          </p>
          <p>İlk kurulumda Firebase Console&apos;dan kullanıcı oluşturun.</p>
        </div>
      </div>
    </div>
  );
}
