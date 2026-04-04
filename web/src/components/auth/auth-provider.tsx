"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  type AuthUser,
  apiGetMe,
  apiLogin,
  apiSignup,
  clearAuth,
  getAuthUser,
  getToken,
  saveAuth,
} from "@/lib/auth";

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  signup: (username: string, password: string, email?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const PUBLIC_PATHS = ["/login", "/signup"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const token = getToken();
    const stored = getAuthUser();
    if (!token || !stored) {
      setIsLoading(false);
      return;
    }

    // Optimistically set user from cache, then validate token with server
    setUser(stored);

    apiGetMe()
      .then((fresh) => {
        const authUser: AuthUser = {
          user_id: fresh.user_id,
          username: fresh.username,
          onboarding_completed: fresh.onboarding_completed,
        };
        saveAuth(token, authUser);
        setUser(authUser);
      })
      .catch(() => {
        // Token is expired or invalid — clear stale auth
        clearAuth();
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (isLoading) return;
    const isPublic = PUBLIC_PATHS.includes(pathname);

    if (!user && !isPublic) {
      router.replace("/login");
    }
    if (user && isPublic) {
      router.replace(user.onboarding_completed ? "/" : "/onboarding");
    }
  }, [user, isLoading, pathname, router]);

  const handleLogin = useCallback(async (username: string, password: string) => {
    const data = await apiLogin(username, password);
    const authUser: AuthUser = {
      user_id: data.user_id,
      username: data.username,
      onboarding_completed: data.onboarding_completed,
    };
    saveAuth(data.access_token, authUser);
    setUser(authUser);
  }, []);

  const handleSignup = useCallback(async (username: string, password: string, email?: string) => {
    await apiSignup(username, password, email);
    await handleLogin(username, password);
  }, [handleLogin]);

  const handleLogout = useCallback(() => {
    clearAuth();
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      login: handleLogin,
      signup: handleSignup,
      logout: handleLogout,
    }),
    [user, isLoading, handleLogin, handleSignup, handleLogout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
