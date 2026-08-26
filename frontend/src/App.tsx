import { Navigate, Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { RequireRole } from "./components/RequireRole";
import { ControlDeMesaPage } from "./pages/ControlDeMesa";
import { DashboardPage } from "./pages/Dashboard";
import { LoginPage } from "./pages/Login";
import { PartidoEnVivoPage } from "./pages/PartidoEnVivo";
import { MisPartidosPage } from "./pages/arbitro/MisPartidos";
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

          {/* Módulo Árbitro (roles-3-modulos-plan.md, Fase 3, D3): ruta
              única, sin layout/Outlet — hoy es una sola pantalla. Sin
              AdminGeneral en la lista de roles a propósito: el "entrar
              como" de AdminGeneral en este módulo es la pregunta que
              Fase 4 todavía no decidió. */}
          <Route
            path="/arbitro"
            element={
              <RequireRole roles={["Arbitro"]}>
                <MisPartidosPage />
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
