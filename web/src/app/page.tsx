"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { homePathForRol } from "@/lib/constants";

export default function HomePage() {
  const { user, profil, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      if (!user) router.replace("/login");
      else router.replace(homePathForRol(profil?.rol));
      return;
    }
    const t = setTimeout(() => router.replace("/login"), 4000);
    return () => clearTimeout(t);
  }, [user, profil, loading, router]);

  return (
    <div className="loading-screen">
      <p>Yönlendiriliyor…</p>
      <p style={{ marginTop: 16 }}>
        <Link href="/login">Giriş →</Link>
        {" · "}
        <Link href="/ofis">Yönetici panel →</Link>
      </p>
    </div>
  );
}
