import { NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { BarraDisciplinasPublica } from "./publico/BarraDisciplinasPublica";

export function NavBar() {
  const { session, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // T2.4/D12: el estado de disciplina elegida vive en la URL de "/"
  // (`/?deporte=<slug>`), no en useState — un refresh o un link
  // compartido tienen que conservar el deporte. El NavBar se monta en
  // TODA ruta (F18), así que solo lee `?deporte=` cuando la ruta activa
  // es la home; en cualquier otra página no hay "deporte actual" que
  // resaltar.
  const deporteActual = location.pathname === "/" ? searchParams.get("deporte") : null;
  function seleccionarDeporte(slug: string | null) {
    navigate(slug ? `/?deporte=${encodeURIComponent(slug)}` : "/");
  }

  // D13: el link a Dashboard/Control de Mesa/etc. son los únicos
  // ocupantes de esta fila — con T1.1/T1.2 un anónimo no ve ninguno, y
  // `.nav-bar__links` (flex:1) dejaba un hueco expansivo vacío entre la
  // marca y "Iniciar sesión" si se renderizaba igual. Se calcula acá para
  // no renderizar el `<nav>` en absoluto cuando no hay nada adentro.
  const hayLinksDeSesion = session != null;

  return (
    <header className="nav-bar">
      <div className="nav-bar__fila1">
        <div className="nav-bar__brand">Score-App</div>
        {hayLinksDeSesion && (
          <nav className="nav-bar__links">
            {/* portal-publico-feed-partidos-plan.md, T1.1/T1.2 (C7): el público
                anónimo ya no ve ni Dashboard ni Control de Mesa acá — el link a
                Control de Mesa quedaba visible para cualquiera aunque la ruta
                estuviera gateada por RequireRole. Dashboard se esconde para el
                anónimo (el link, no la ruta: /dashboard sigue alcanzable
                tipeada directo, ver F20 en App.routing.test.tsx) porque no
                aporta nada sin sesión. */}
            <NavLink to="/dashboard" className={({ isActive }) => (isActive ? "active" : undefined)}>
              Dashboard
            </NavLink>
            {/* D6: con T1.2 mandando a un logueado siempre a /dashboard y sin
                ningún link de vuelta al portal público, nadie con sesión podía
                llegar al feed — ni el TorneoAdmin que acaba de cargar los
                partidos. Una línea, mismo razonamiento que T5.2c aplicó a la
                vista de torneo. */}
            <NavLink to="/">Portal público</NavLink>
            {(session?.rol === "TorneoAdmin" || session?.rol === "AdminGeneral" || session?.rol === "Arbitro") && (
              <NavLink to="/control-de-mesa" className={({ isActive }) => (isActive ? "active" : undefined)}>
                Control de Mesa
              </NavLink>
            )}
            {(session?.rol === "TorneoAdmin" || session?.rol === "AdminGeneral") && (
              <NavLink to="/torneo-admin" className={({ isActive }) => (isActive ? "active" : undefined)}>
                Torneo Admin
              </NavLink>
            )}
            {(session?.rol === "Arbitro" || session?.rol === "AdminGeneral") && (
              <NavLink to="/arbitro" className={({ isActive }) => (isActive ? "active" : undefined)}>
                Mis partidos
              </NavLink>
            )}
            {session?.rol === "AdminGeneral" && (
              <NavLink to="/admin/usuarios" className={({ isActive }) => (isActive ? "active" : undefined)}>
                Usuarios
              </NavLink>
            )}
            {session?.rol === "AdminGeneral" && (
              <NavLink to="/admin/accesos" className={({ isActive }) => (isActive ? "active" : undefined)}>
                Accesos
              </NavLink>
            )}
            {session?.rol === "AdminGeneral" && (
              <NavLink to="/admin/auditoria" className={({ isActive }) => (isActive ? "active" : undefined)}>
                Auditoría
              </NavLink>
            )}
          </nav>
        )}
        <div className="nav-bar__session">
          {session ? (
            <>
              <span className="nav-bar__user">
                {session.username} <span className="badge">{session.rol}</span>
              </span>
              <button type="button" onClick={logout}>
                Salir
              </button>
            </>
          ) : (
            <NavLink to="/login">Iniciar sesión</NavLink>
          )}
        </div>
      </div>
      {/* T2.3/D13: segunda fila, visible SIN sesión (el NavBar ya se
          renderiza para anónimos) — la barra misma decide si tiene algo
          que mostrar (C8: con ≤1 disciplina con contenido, no se renderiza
          nada, ni siquiera el contenedor). */}
      <BarraDisciplinasPublica deporteSeleccionado={deporteActual} onSeleccionar={seleccionarDeporte} />
    </header>
  );
}
