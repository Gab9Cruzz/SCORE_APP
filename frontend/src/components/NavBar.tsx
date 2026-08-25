import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

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
