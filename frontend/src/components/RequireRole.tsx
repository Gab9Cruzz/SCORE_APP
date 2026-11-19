import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { type Rol } from "../auth/authContextValue";
import { useAuth } from "../auth/useAuth";
import { SinPermisoPage } from "../pages/SinPermiso";

/** Bloquea el acceso si no hay sesión o el rol no está en `roles`
 * (TASK-036, UX-02):
 *
 * - sin sesión, al login, recordando adónde iba (`state.from`): después de
 *   entrar vuelve a esa misma página;
 * - con sesión pero otro rol, "sin permiso", no "iniciá sesión". */
export function RequireRole({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const { session } = useAuth();
  const location = useLocation();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (!roles.includes(session.rol)) {
    return <SinPermisoPage rolesRequeridos={roles} />;
  }
  return <>{children}</>;
}
