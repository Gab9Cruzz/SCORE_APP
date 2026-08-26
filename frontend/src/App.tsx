import { Navigate, Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { RequireRole } from "./components/RequireRole";
import { ControlDeMesaPage } from "./pages/ControlDeMesa";
import { DashboardPage } from "./pages/Dashboard";
import { LoginPage } from "./pages/Login";
import { PartidoEnVivoPage } from "./pages/PartidoEnVivo";
import { MisPartidosPage } from "./pages/arbitro/MisPartidos";
import { UsuariosAdminPage } from "./pages/admin/UsuariosAdmin";
import { EquiposAdminPage } from "./pages/torneo-admin/EquiposAdmin";
import { InscripcionesAdminPage } from "./pages/torneo-admin/InscripcionesAdmin";
import { JugadoresAdminPage } from "./pages/torneo-admin/JugadoresAdmin";
import { PartidosAdminPage } from "./pages/torneo-admin/PartidosAdmin";
import { PlantillasAdminPage } from "./pages/torneo-admin/PlantillasAdmin";
import { TorneoAdminLayout } from "./pages/torneo-admin/TorneoAdminLayout";
import { TorneosAdminPage } from "./pages/torneo-admin/TorneosAdmin";

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
            <Route path="equipos" element={<EquiposAdminPage />} />
            <Route path="jugadores" element={<JugadoresAdminPage />} />
            <Route path="plantillas" element={<PlantillasAdminPage />} />
            <Route path="inscripciones" element={<InscripcionesAdminPage />} />
            <Route path="partidos" element={<PartidosAdminPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
