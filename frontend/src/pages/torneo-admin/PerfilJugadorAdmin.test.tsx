import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { JugadoresAdminPage } from "./JugadoresAdmin";
import { PerfilJugadorAdminPage } from "./PerfilJugadorAdmin";

const PERFIL_1 = "http://127.0.0.1:8000/api/v1/jugadores/1/perfil";

/** Esta página usa useParams (ruta con :jugadorId) — createWrapper() del
 * resto de los tests no sirve acá (no arma rutas anidadas reales), se
 * monta con su propio MemoryRouter + <Routes>, igual que
 * App.routing.test.tsx. */
function renderConRuta(path: string) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/torneo-admin/jugadores" element={<JugadoresAdminPage />} />
          <Route path="/torneo-admin/jugadores/:jugadorId/perfil" element={<PerfilJugadorAdminPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PerfilJugadorAdminPage", () => {
  it("renderiza una disciplina Activa con goles y trayectoria", async () => {
    server.use(
      http.get(PERFIL_1, () =>
        HttpResponse.json({
          jugador_id: 1,
          nombre: "Carlos Pérez",
          cedula: "0900000001",
          correo_electronico: "carlos@example.com",
          disciplinas: [
            {
              jugador_perfil_id: 1,
              disciplina_id: 1,
              disciplina: "Fútbol",
              estado: "Activo",
              goles_totales: 3,
              equipos_activos: [
                {
                  inscripcion_torneo_id: 2,
                  torneo_id: 1,
                  torneo: "Copa Ecotec 2026",
                  equipo_id: 2,
                  equipo: "Águilas del Sur",
                  dorsal: 99,
                  fecha_inicio: "2026-02-01",
                },
              ],
              trayectoria: [
                {
                  id: 1,
                  fecha_traspaso: "2026-02-01T10:00:00",
                  origen: "Copa Ecotec 2026 — Tiburones FC",
                  destino: "Copa Ecotec 2026 — Águilas del Sur",
                  motivo: "Prueba",
                  estado: "Completado",
                },
              ],
            },
          ],
        }),
      ),
    );

    renderConRuta("/torneo-admin/jugadores/1/perfil");

    expect(await screen.findByRole("heading", { name: "Carlos Pérez" })).toBeInTheDocument();
    expect(screen.getByText("Fútbol")).toBeInTheDocument();
    expect(screen.getByText("Activo")).toBeInTheDocument();
    expect(screen.getByText("Goles totales: 3")).toBeInTheDocument();
    expect(screen.getByText(/Águilas del Sur.*dorsal #99/)).toBeInTheDocument();
    expect(screen.getByText("Prueba")).toBeInTheDocument();
  });

  it("perfil Libre sin equipos activos muestra el mensaje vacío, no una tabla vacía", async () => {
    server.use(
      http.get(PERFIL_1, () =>
        HttpResponse.json({
          jugador_id: 1,
          nombre: "Jugador Libre",
          cedula: "0900000099",
          correo_electronico: "libre@example.com",
          disciplinas: [
            {
              jugador_perfil_id: 5,
              disciplina_id: 1,
              disciplina: "Fútbol",
              estado: "Libre",
              goles_totales: 0,
              equipos_activos: [],
              trayectoria: [],
            },
          ],
        }),
      ),
    );

    renderConRuta("/torneo-admin/jugadores/1/perfil");

    expect(await screen.findByText("Libre")).toBeInTheDocument();
    expect(screen.getByText("Sin equipos activos en esta disciplina.")).toBeInTheDocument();
    expect(screen.getByText("Sin traspasos registrados en esta disciplina.")).toBeInTheDocument();
  });

  it("el link 'Ver perfil' desde Jugadores navega a la ruta correcta", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/jugadores", () =>
        HttpResponse.json([
          { id: 1, nombre: "Carlos Pérez", cedula: "0900000001", correo_electronico: "c@example.com", estado: "Activo" },
        ]),
      ),
      http.get(PERFIL_1, () =>
        HttpResponse.json({
          jugador_id: 1,
          nombre: "Carlos Pérez",
          cedula: "0900000001",
          correo_electronico: "carlos@example.com",
          disciplinas: [],
        }),
      ),
    );

    renderConRuta("/torneo-admin/jugadores");
    await screen.findByText("Carlos Pérez");

    await user.click(screen.getByRole("link", { name: "Ver perfil" }));

    expect(await screen.findByRole("heading", { name: "Carlos Pérez" })).toBeInTheDocument();
    expect(screen.getByText("Sin perfiles de disciplina todavía.")).toBeInTheDocument();
  });
});
