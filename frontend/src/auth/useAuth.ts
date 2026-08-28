import { useContext } from "react";
import { AuthContext, type AuthContextValue } from "./authContextValue";

/** Separado de `AuthContext.tsx` por Fast Refresh — ver el comentario en
 * `authContextValue.ts`. El punto de import para los consumidores no
 * cambió de forma: siguen escribiendo `useAuth()`, solo cambia de qué
 * archivo lo traen. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>.");
  return ctx;
}
