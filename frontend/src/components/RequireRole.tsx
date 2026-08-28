import type { ReactNode } from "react";
import { type Rol } from "../auth/authContextValue";
import { useAuth } from "../auth/useAuth";
import { LoginPrompt } from "../pages/Login";

/** Bloquea acceso si no hay sesión o el rol no está en `roles`.
 * No devuelve un 401 crudo — ver "Manejo de sesión y roles" del design doc:
 * muestra una pantalla explicando qué hace falta, no un error técnico. */
export function RequireRole({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const { session } = useAuth();

  if (!session || !roles.includes(session.rol)) {
    return <LoginPrompt requiredRoles={roles} />;
  }

  return <>{children}</>;
}
