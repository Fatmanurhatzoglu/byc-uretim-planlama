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
import { firebaseConfigEksik, getFirebaseAuth } from "@/lib/firebase";
import { kullaniciAdiToEmail, resolveProfil } from "@/lib/constants";
import { getKullaniciProfil } from "@/lib/firestore";
import type { KullaniciProfil } from "@/lib/types";

interface AuthState {
  user: User | null;
  profil: KullaniciProfil | null;
  loading: boolean;
  configHata: string | null;
  login: (kullaniciAdi: string, sifre: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profil, setProfil] = useState<KullaniciProfil | null>(null);
  const [loading, setLoading] = useState(true);
  const [configHata, setConfigHata] = useState<string | null>(null);

  useEffect(() => {
    if (firebaseConfigEksik()) {
      setConfigHata(
        "Firebase ayarları eksik. Vercel → Settings → Environment Variables.",
      );
      setLoading(false);
      return;
    }
    try {
      const auth = getFirebaseAuth();
      return onAuthStateChanged(auth, async (u) => {
        setUser(u);
        if (u) {
          let remote: KullaniciProfil | null = null;
          try {
            remote = await getKullaniciProfil(u.uid);
          } catch {
            remote = null;
          }
          setProfil(resolveProfil(u.email || "", remote));
        } else {
          setProfil(null);
        }
        setLoading(false);
      });
    } catch (e) {
      setConfigHata(e instanceof Error ? e.message : "Firebase başlatılamadı");
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (kullaniciAdi: string, sifre: string) => {
    if (firebaseConfigEksik()) {
      throw new Error("Firebase yapılandırması eksik.");
    }
    const email = kullaniciAdiToEmail(kullaniciAdi);
    await signInWithEmailAndPassword(getFirebaseAuth(), email, sifre);
  }, []);

  const logout = useCallback(async () => {
    await signOut(getFirebaseAuth());
  }, []);

  const value = useMemo(
    () => ({ user, profil, loading, configHata, login, logout }),
    [user, profil, loading, configHata, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth AuthProvider içinde kullanılmalı");
  return ctx;
}
