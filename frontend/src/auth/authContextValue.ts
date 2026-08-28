import { createContext } from "react";

export type Rol = "AdminGeneral" | "TorneoAdmin" | "Arbitro" | "Publico";

export interface Session {
  token: string;
  username: string;
  rol: Rol;
  /** id numérico del usuario logueado — no viene en la respuesta de
   * /auth/login (roles-3-modulos-plan.md, Fase 3, D2: se pide aparte a
   * GET /auth/me en vez de tocar el contrato de login). `undefined`
   * hasta que esa llamada resuelve, o si falló — el filtro de "Mis
   * partidos" (Fase 3) queda deshabilitado hasta tener un id real. */
  id: number | undefined;
}

export interface AuthContextValue {
  session: Session | null;
  isAuthenticated: boolean;
  /** Devuelve el rol logueado — quien llama lo necesita para decidir a
   * dónde redirigir (roles-3-modulos-plan.md, Fase 2, D2). El rol vive en
   * la respuesta del login, no en `session` todavía en ese mismo tick:
   * `setSession` es async, así que devolverlo acá evita depender de un
   * re-render para tener el dato a tiempo. */
  login: (username: string, password: string) => Promise<Rol>;
  logout: () => void;
  loginError: string | null;
  loggingIn: boolean;
}

/** El contexto y sus tipos viven acá, separados de `AuthContext.tsx`, por
 * Fast Refresh: un módulo que exporta un componente (`AuthProvider`) Y
 * además valores que no lo son pierde el hot-reload granular — editar el
 * provider forzaba un reload completo de la página, y con él la sesión de
 * desarrollo. Separar lo que no es componente deja que Vite reemplace solo
 * el módulo tocado. */
export const AuthContext = createContext<AuthContextValue | null>(null);
