"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { homePathForRol } from "@/lib/constants";

export default function HomePage() {
  const { user, profil, loading } = useAuth();

  useEffect(() => {
    if (!loading) {
      if (!user) {
        window.location.replace("/login");
      } else {
        window.location.replace(homePathForRol(profil?.rol));
      }
      return;
    }
    const t = setTimeout(() => {
      window.location.replace("/login");
    }, 4000);
    return () => clearTimeout(t);
  }, [user, profil, loading]);

  return (
    <div className="loading-screen">
      <p>Yönlendiriliyor…</p>
      <p style={{ marginTop: 16 }}>
        <Link href="/login">Giriş →</Link>
        {" · "}
        <Link href="/ofis">
          <strong>Yönetici panel →</strong>
        </Link>
      </p>
    </div>
  );
}
