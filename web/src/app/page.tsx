"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { homePathForRol } from "@/lib/constants";

export default function HomePage() {
  const { user, profil, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (profil) router.replace(homePathForRol(profil.rol));
  }, [user, profil, loading, router]);

  return (
    <div className="loading-screen">
      <p>Yönlendiriliyor…</p>
    </div>
  );
}
