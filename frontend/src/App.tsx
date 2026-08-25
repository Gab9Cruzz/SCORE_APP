import { Navigate, Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { RequireRole } from "./components/RequireRole";
import { ControlDeMesaPage } from "./pages/ControlDeMesa";
import { DashboardPage } from "./pages/Dashboard";
import { LoginPage } from "./pages/Login";
import { PartidoEnVivoPage } from "./pages/PartidoEnVivo";

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
              <RequireRole roles={["Admin", "Arbitro"]}>
                <ControlDeMesaPage />
              </RequireRole>
            }
          />
          <Route path="/partido/:partidoId/en-vivo" element={<PartidoEnVivoPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
