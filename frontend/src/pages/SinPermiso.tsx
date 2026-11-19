import { Link } from "react-router-dom";
import type { Rol } from "../auth/authContextValue";
import { landingPorRol } from "../auth/landing";
import { useAuth } from "../auth/useAuth";
import { useTituloPagina } from "../hooks/useTituloPagina";

/** TASK-036 (UX-02): lo que ve alguien CON sesión que entra a una página
 * de otro rol. Antes leía "Necesitás iniciar sesión" con un enlace al
 * login, como si no la tuviera. */
export function SinPermisoPage({ rolesRequeridos }: { rolesRequeridos: Rol[] }) {
  useTituloPagina("Sin permiso");
  const { session } = useAuth();
  return (
    <div className="page estado-acceso">
      <h1>No tenés permiso para ver esta página</h1>
      <p>
        Esta sección es para <strong>{rolesRequeridos.join(" o ")}</strong>.
        {session && (
          <>
            {" "}
            Tu cuenta ({session.username}) es <strong>{session.rol}</strong>.
          </>
        )}
      </p>
      <p className="muted--cuerpo">Si creés que deberías tener acceso, pedíselo a quien administra el sistema.</p>
      <Link className="button-link" to={landingPorRol(session?.rol)}>
        Ir a mi inicio
      </Link>
    </div>
  );
}
