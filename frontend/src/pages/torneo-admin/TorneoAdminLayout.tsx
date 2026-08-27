import { NavLink, Outlet } from "react-router-dom";
import { RequireRole } from "../../components/RequireRole";

const PESTANIAS = [
  { to: "torneos", label: "Torneos" },
  { to: "disciplinas", label: "Disciplinas" },
  { to: "modalidades", label: "Modalidades" },
  { to: "equipos", label: "Equipos" },
  { to: "jugadores", label: "Jugadores" },
];

/** Landing de TorneoAdmin (roles-3-modulos-plan.md, Fase 2, D2) — sub-rutas
 * anidadas bajo /torneo-admin/*, gateado a TorneoAdmin/AdminGeneral.
 *
 * Plantillas/Traspasos/Inscripciones/Partidos ya NO son pestañas globales
 * (torneos-admin-plan.md, Fase 3: consolidación) — esos 4 recursos son
 * inherentemente de UN torneo, mostrarlos sin acotar mezclaba todas las
 * ediciones de todos los grupos en una sola tabla. Viven ahora dentro del
 * dashboard scoped (`torneos/:torneoId/*`, ver TorneoDashboard.tsx),
 * alcanzable solo con "Ver Torneo" desde la tarjeta de Torneos — mismo
 * criterio que jugadores/:jugadorId/perfil, un link, no un tab acá.
 * Disciplinas/Modalidades/Jugadores/Equipos siguen siendo catálogos
 * globales reusados entre torneos, esos sí quedan como pestaña. */
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
