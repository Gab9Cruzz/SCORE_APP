import { Navigate, Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { RequireRole } from "./components/RequireRole";
import { ControlDeMesaPage } from "./pages/ControlDeMesa";
import { DashboardPage } from "./pages/Dashboard";
import { LoginPage } from "./pages/Login";
import { PartidoEnVivoPage } from "./pages/PartidoEnVivo";
import { MisPartidosPage } from "./pages/arbitro/MisPartidos";
import { UsuariosAdminPage } from "./pages/admin/UsuariosAdmin";
import { CatalogoDisciplinasPage } from "./pages/torneo-admin/CatalogoDisciplinas";
import { EquiposAdminPage } from "./pages/torneo-admin/EquiposAdmin";
import { JugadoresAdminPage } from "./pages/torneo-admin/JugadoresAdmin";
import { PerfilJugadorAdminPage } from "./pages/torneo-admin/PerfilJugadorAdmin";
import { RegistroLoteAdminPage } from "./pages/torneo-admin/RegistroLoteAdmin";
import { TorneoAdminLayout } from "./pages/torneo-admin/TorneoAdminLayout";
import { TorneosAdminPage } from "./pages/torneo-admin/TorneosAdmin";
import { EquiposDelTorneoPage } from "./pages/torneo-admin/torneo-dashboard/EquiposDelTorneo";
import { EstadisticasDelTorneoPage } from "./pages/torneo-admin/torneo-dashboard/EstadisticasDelTorneo";
import { PartidosDelTorneoPage } from "./pages/torneo-admin/torneo-dashboard/PartidosDelTorneo";
import { PlantillasDelTorneoPage } from "./pages/torneo-admin/torneo-dashboard/PlantillasDelTorneo";
import { TorneoDashboardPage } from "./pages/torneo-admin/torneo-dashboard/TorneoDashboard";
import { TraspasosDelTorneoPage } from "./pages/torneo-admin/torneo-dashboard/TraspasosDelTorneo";

export function App() {
  return (
    <div className="app-shell">
      <NavBar />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/control-de-mesa"
            element={
              <RequireRole roles={["TorneoAdmin", "AdminGeneral", "Arbitro"]}>
                <ControlDeMesaPage />
              </RequireRole>
            }
          />
          <Route path="/partido/:partidoId/en-vivo" element={<PartidoEnVivoPage />} />

          {/* Módulo Árbitro (roles-3-modulos-plan.md, Fase 3, D3 + Fase 4,
              D1): ruta única, sin layout/Outlet — hoy es una sola
              pantalla. AdminGeneral se agregó en Fase 4 (acceso cruzado
              "sin restricción" del plan original) — sin selector "entrar
              como", solo la lista de roles ampliada. En la práctica un
              AdminGeneral casi siempre ve el empty-state (no suele tener
              arbitro_id asignado), pero backend-side ya tenía acceso
              (bypass de require_roles, D3 confirmado por la voz externa). */}
          <Route
            path="/arbitro"
            element={
              <RequireRole roles={["Arbitro", "AdminGeneral"]}>
                <MisPartidosPage />
              </RequireRole>
            }
          />

          {/* Módulo Admin General (roles-3-modulos-plan.md, Fase 4, D4):
              ruta standalone, NO anidada bajo /torneo-admin — ese layout
              no gatea por pestaña, así que un tab acá le mostraría un
              link muerto a TorneoAdmin. RequireRole solo AdminGeneral,
              coincide exacto con el gate literal de escritura del
              backend (usuarios.py). */}
          <Route
            path="/admin/usuarios"
            element={
              <RequireRole roles={["AdminGeneral"]}>
                <UsuariosAdminPage />
              </RequireRole>
            }
          />

          {/* Módulo Torneo Admin (roles-3-modulos-plan.md, Fase 2, D2). El
              gate de rol vive DENTRO de TorneoAdminLayout (RequireRole
              envolviendo el <Outlet/>), no acá — así el mismo layout se
              puede usar sin repetir el gate en cada sub-ruta. */}
          <Route path="/torneo-admin" element={<TorneoAdminLayout />}>
            <Route index element={<Navigate to="torneos" replace />} />
            <Route path="torneos" element={<TorneosAdminPage />} />
            {/* Dashboard scoped de UNA edición puntual (torneos-admin-plan.md,
                Fase 2): "Ver Torneo" desde la tarjeta de arriba entra acá.
                No es una pestaña de PESTANIAS — mismo criterio que
                jugadores/:jugadorId/perfil, alcanzable solo por link, no
                por tab. */}
            <Route path="torneos/:torneoId" element={<TorneoDashboardPage />}>
              <Route index element={<Navigate to="equipos" replace />} />
              <Route path="equipos" element={<EquiposDelTorneoPage />} />
              <Route path="plantillas" element={<PlantillasDelTorneoPage />} />
              <Route path="traspasos" element={<TraspasosDelTorneoPage />} />
              <Route path="partidos" element={<PartidosDelTorneoPage />} />
              <Route path="estadisticas" element={<EstadisticasDelTorneoPage />} />
            </Route>
            <Route path="disciplinas" element={<CatalogoDisciplinasPage />} />
            <Route path="equipos" element={<EquiposAdminPage />} />
            <Route path="jugadores" element={<JugadoresAdminPage />} />
            <Route path="jugadores/:jugadorId/perfil" element={<PerfilJugadorAdminPage />} />
            {/* Alcanzable solo desde el modal "Agregar Equipo" o el botón
                "+ Registro por lote" del dashboard scoped (ver
                RegistroLoteAdmin.tsx) — ya no hay pestaña global de
                Plantillas desde la que se llegaba antes (Fase 3). */}
            <Route path="plantillas/lote" element={<RegistroLoteAdminPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
