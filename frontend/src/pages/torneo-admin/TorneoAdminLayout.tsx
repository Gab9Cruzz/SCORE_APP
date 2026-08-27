import { NavLink, Outlet } from "react-router-dom";
import { RequireRole } from "../../components/RequireRole";

const PESTANIAS = [
  { to: "torneos", label: "Torneos" },
  { to: "disciplinas", label: "Disciplinas" },
  { to: "modalidades", label: "Modalidades" },
  { to: "equipos", label: "Equipos" },
  { to: "jugadores", label: "Jugadores" },
  { to: "plantillas", label: "Plantillas" },
  { to: "traspasos", label: "Traspasos" },
  { to: "inscripciones", label: "Inscripciones" },
  { to: "partidos", label: "Partidos" },
];

/** Landing de TorneoAdmin (roles-3-modulos-plan.md, Fase 2, D2) — sub-rutas
 * anidadas bajo /torneo-admin/*, gateado a TorneoAdmin/AdminGeneral. */
export function TorneoAdminLayout() {
  return (
    <RequireRole roles={["TorneoAdmin", "AdminGeneral"]}>
      <div className="page">
        <h1>Torneo Admin</h1>
        <nav className="admin-nav">
          {PESTANIAS.map((p) => (
            <NavLink key={p.to} to={p.to} className={({ isActive }) => (isActive ? "active" : undefined)}>
              {p.label}
            </NavLink>
          ))}
        </nav>
        <Outlet />
      </div>
    </RequireRole>
  );
}
