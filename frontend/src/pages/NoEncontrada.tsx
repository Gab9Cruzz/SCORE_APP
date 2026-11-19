import { Link, useLocation } from "react-router-dom";
import { landingPorRol } from "../auth/landing";
import { useAuth } from "../auth/useAuth";
import { useTituloPagina } from "../hooks/useTituloPagina";

/** TASK-036 (FE-03): una dirección que no existe muestra esto. Antes
 * redirigía en silencio al inicio y un enlace roto o un error de tipeo
 * parecían "la app me sacó". */
export function NoEncontradaPage() {
  useTituloPagina("Página no encontrada");
  const { session } = useAuth();
  const { pathname } = useLocation();
  return (
    <div className="page estado-acceso">
      <h1>No encontramos esta página</h1>
      <p>
        La dirección <code>{pathname}</code> no existe o cambió.
      </p>
      <Link className="button-link" to={session ? landingPorRol(session.rol) : "/"}>
        {session ? "Ir a mi inicio" : "Ir al portal"}
      </Link>
    </div>
  );
}
