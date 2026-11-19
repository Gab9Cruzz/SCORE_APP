import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { landingPorRol } from "../auth/landing";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { useTituloPagina } from "../hooks/useTituloPagina";

// roles-3-modulos-plan.md, Fase 2, D2: landing por default después de
// loguearse (auth/landing.ts). `from` (si existe) siempre gana — si alguien
// fue redirigido acá desde una ruta protegida específica (RequireRole,
// TASK-036), volver ahí importa más que el landing genérico del rol.
export function LoginPage() {
  useTituloPagina("Iniciar sesión");
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
        {from && <p className="muted--cuerpo">Iniciá sesión para seguir a la página que querías ver.</p>}
        <Field etiqueta="Usuario">
          {(p) => (
            <input
              {...p}
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          )}
        </Field>
        <Field etiqueta="Contraseña">
          {(p) => (
            <input
              {...p}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          )}
        </Field>
        {loginError && <p className="error-text">{loginError}</p>}
        <Button variante="primario" type="submit" disabled={loggingIn || !username || !password}>
          {loggingIn ? "Ingresando..." : "Ingresar"}
        </Button>
      </form>
    </div>
  );
}
