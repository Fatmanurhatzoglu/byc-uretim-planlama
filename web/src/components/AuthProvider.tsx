"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { emailToKullaniciAdi, kullaniciAdiToEmail } from "@/lib/constants";
import { getKullaniciProfil } from "@/lib/firestore";
import type { KullaniciProfil } from "@/lib/types";

interface AuthState {
  user: User | null;
  profil: KullaniciProfil | null;
  loading: boolean;
  login: (kullaniciAdi: string, sifre: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profil, setProfil] = useState<KullaniciProfil | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let unsub: (() => void) | undefined;
    try {
      const auth = getFirebaseAuth();
      unsub = onAuthStateChanged(auth, async (u) => {
        setUser(u);
        if (u) {
          try {
            const p = await getKullaniciProfil(u.uid);
            setProfil(
              p || {
                kullanici_adi: emailToKullaniciAdi(u.email || ""),
                ad: emailToKullaniciAdi(u.email || ""),
                rol: "saha",
              },
            );
          } catch {
            setProfil({
              kullanici_adi: emailToKullaniciAdi(u.email || ""),
              ad: emailToKullaniciAdi(u.email || ""),
              rol: "saha",
            });
          }
        } else {
          setProfil(null);
        }
        setLoading(false);
      });
    } catch {
      // Config yok / Firebase açılamadı — sonsuz "Yönlendiriliyor" olmasın
      setUser(null);
      setProfil(null);
      setLoading(false);
    }
    return () => {
      if (unsub) unsub();
    };
  }, []);

  const login = useCallback(async (kullaniciAdi: string, sifre: string) => {
    const email = kullaniciAdiToEmail(kullaniciAdi);
    await signInWithEmailAndPassword(getFirebaseAuth(), email, sifre);
  }, []);

  const logout = useCallback(async () => {
    await signOut(getFirebaseAuth());
  }, []);

  const value = useMemo(
    () => ({ user, profil, loading, login, logout }),
    [user, profil, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth AuthProvider içinde kullanılmalı");
  return ctx;
}
