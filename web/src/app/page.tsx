"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      router.replace(user ? "/mobile" : "/login");
      return;
    }
    // Auth takılırsa kullanıcı mahsur kalmasın
    const t = setTimeout(() => {
      router.replace("/login");
    }, 4000);
    return () => clearTimeout(t);
  }, [user, loading, router]);

  return (
    <div className="loading-screen">
      <p>Yönlendiriliyor…</p>
      <p style={{ marginTop: 16 }}>
        <Link href="/login">Giriş sayfasına git →</Link>
      </p>
      <p style={{ marginTop: 8 }}>
        <Link href="/istasyon">İstasyon →</Link>
        {" · "}
        <Link href="/mobile">Saha →</Link>
      </p>
    </div>
  );
}
