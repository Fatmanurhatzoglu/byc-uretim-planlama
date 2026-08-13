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
import {
  emailToKullaniciAdi,
  kullaniciAdiToEmail,
  rolFromEmailOrKullanici,
} from "@/lib/constants";
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

function profilBirleştir(email: string, remote: KullaniciProfil | null): KullaniciProfil {
  const ka = emailToKullaniciAdi(email);
  const emailRol = rolFromEmailOrKullanici(email || ka);
  if (emailRol === "admin" || emailRol === "ofis") {
    return {
      kullanici_adi: remote?.kullanici_adi || ka,
      ad: remote?.ad || (ka === "fatmanur" ? "Fatmanur" : ka),
      rol: emailRol,
    };
  }
  return (
    remote || {
      kullanici_adi: ka,
      ad: ka,
      rol: "saha",
    }
  );
}

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
          let remote: KullaniciProfil | null = null;
          try {
            remote = await getKullaniciProfil(u.uid);
          } catch {
            remote = null;
          }
          setProfil(profilBirleştir(u.email || "", remote));
        } else {
          setProfil(null);
        }
        setLoading(false);
      });
    } catch {
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
