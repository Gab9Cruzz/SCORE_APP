import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, apiErrorMessage, getStoredToken, setOnUnauthorized, TOKEN_STORAGE_KEY } from "../api/client";
import { AuthContext, type AuthContextValue, type Rol, type Session } from "./authContextValue";

const SESSION_STORAGE_KEY = "score-app.session";

function loadStoredSession(): Session | null {
  const token = getStoredToken();
  if (!token) return null;
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Omit<Session, "token">;
    return { ...parsed, token };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => loadStoredSession());
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);

  const clearSession = useCallback(() => {
    setSession(null);
    try {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      /* localStorage no disponible (modo privado, etc.) — no bloquea el logout en memoria */
    }
  }, []);

  // Un 401 en cualquier request (token vencido o inválido) limpia la sesión
  // desde el cliente API — ver Constraint "sesión y roles" del design doc.
  useEffect(() => {
    setOnUnauthorized(() => clearSession());
    return () => setOnUnauthorized(null);
  }, [clearSession]);

  const login = useCallback(async (username: string, password: string) => {
    setLoggingIn(true);
    setLoginError(null);
    try {
      const body = new URLSearchParams({ username, password });
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(apiErrorMessage(errBody, "Usuario o contraseña incorrectos."));
      }
      const data = (await res.json()) as { access_token: string; rol: Rol };
      // El token se guarda YA (antes de pedir /auth/me) porque el
      // interceptor de `api` (client.ts) lo lee de localStorage en cada
      // request — sin esto, la llamada de abajo saldría sin Authorization.
      try {
        localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
      } catch {
        /* sesión igual queda activa en memoria para esta pestaña */
      }

      // GET /auth/me (roles-3-modulos-plan.md, Fase 3, D2): /auth/login no
      // devuelve el id numérico del usuario, así que se pide aparte acá en
      // vez de tocar el contrato de login. Si esta llamada falla, el login
      // en sí ya fue exitoso — no lo tumbamos, session.id queda undefined
      // (el filtro de "Mis partidos" no puede armarse hasta el próximo
      // login que sí consiga el id).
      let id: number | undefined;
      try {
        const { data: me, error } = await api.GET("/api/v1/auth/me", {});
        if (error) throw error;
        id = me.id;
      } catch {
        id = undefined;
      }

      const nextSession: Session = { token: data.access_token, username, rol: data.rol, id };
      setSession(nextSession);
      try {
        localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username, rol: data.rol, id }));
      } catch {
        /* sesión igual queda activa en memoria para esta pestaña */
      }
      return data.rol;
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "No se pudo iniciar sesión.");
      throw err;
    } finally {
      setLoggingIn(false);
    }
  }, []);

  const logout = useCallback(() => clearSession(), [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({ session, isAuthenticated: session !== null, login, logout, loginError, loggingIn }),
    [session, login, logout, loginError, loggingIn],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
