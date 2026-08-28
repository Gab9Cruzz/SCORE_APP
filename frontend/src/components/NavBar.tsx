import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export function NavBar() {
  const { session, logout } = useAuth();

  return (
    <header className="nav-bar">
      <div className="nav-bar__brand">Score-App</div>
      <nav className="nav-bar__links">
        <NavLink to="/dashboard" className={({ isActive }) => (isActive ? "active" : undefined)}>
          Dashboard
        </NavLink>
        <NavLink to="/control-de-mesa" className={({ isActive }) => (isActive ? "active" : undefined)}>
          Control de Mesa
        </NavLink>
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
      </nav>
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
    </header>
  );
}
