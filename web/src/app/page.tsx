"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/mobile" : "/login");
  }, [user, loading, router]);

  return (
    <div className="loading-screen">
      <p>Yönlendiriliyor…</p>
    </div>
  );
}
