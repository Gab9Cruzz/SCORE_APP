import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { type Rol } from "../auth/authContextValue";
import { useAuth } from "../auth/useAuth";

// roles-3-modulos-plan.md, Fase 2, D2: landing por default después de
// loguearse. `from` (si existe) siempre gana — si alguien fue redirigido
// acá desde una ruta protegida específica, volver ahí importa más que el
// landing genérico del rol.
function landingPorRol(rol: Rol | undefined): string {
  if (rol === "TorneoAdmin" || rol === "AdminGeneral") return "/torneo-admin";
  // Fase 3, D3: Árbitro tiene su propia landing ("Mis partidos") — el
  // resto (Publico, sin sesión) sigue cayendo en /dashboard sin cambios.
  if (rol === "Arbitro") return "/arbitro";
  return "/dashboard";
}

export function LoginPage() {
  const { login, loginError, loggingIn, isAuthenticated, session } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;

  // <Navigate> (no una llamada a navigate() durante el render) — llamar
  // navigate() mientras este componente todavía se está renderizando dispara
  // el warning de React "Cannot update a component while rendering a
  // different component".
  if (isAuthenticated) {
    return <Navigate to={from ?? landingPorRol(session?.rol)} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      // login() devuelve el rol directamente (no lee `session`, que recién
      // se actualiza en el próximo render) — es lo que permite decidir el
      // destino correcto en este mismo tick, sin esperar un re-render.
      const rol = await login(username, password);
      navigate(from ?? landingPorRol(rol), { replace: true });
    } catch {
      // loginError ya quedó seteado en el contexto — el form lo muestra abajo.
    }
  }

  return (
    <div className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Iniciar sesión</h1>
        <label>
          Usuario
          <input
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        {loginError && <p className="error-text">{loginError}</p>}
        <button type="submit" disabled={loggingIn || !username || !password}>
          {loggingIn ? "Ingresando..." : "Ingresar"}
        </button>
      </form>
    </div>
  );
}

/** Lo que ve alguien sin sesión (o con rol insuficiente) al entrar a una ruta
 * protegida — nunca un 401 crudo. Ver "Manejo de sesión y roles" del design doc. */
export function LoginPrompt({ requiredRoles }: { requiredRoles: Rol[] }) {
  return (
    <div className="login-page">
      <div className="login-form login-form--prompt">
        <h1>Necesitás iniciar sesión</h1>
        <p>
          Esta sección requiere rol <strong>{requiredRoles.join(" o ")}</strong>.
        </p>
        <a className="button-link" href="/login">
          Ir a iniciar sesión
        </a>
      </div>
    </div>
  );
}
