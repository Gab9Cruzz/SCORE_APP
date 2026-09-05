import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { TraspasosDelTorneoPage } from "./TraspasosDelTorneo";
import type { TorneoDashboardContext } from "./TorneoDashboard";

const CONTEXTO: TorneoDashboardContext = {
  torneoId: 20,
  torneoGrupoId: 7,
  disciplinaId: 1,
  modalidadId: 1,
  torneoContexto: "Liga Relámpago — Edición 2",
  formato: "Liga",
  incluyeTercerLugar: true,
};

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useOutletContext: () => CONTEXTO };
});

const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";
const PERFILES = "http://127.0.0.1:8000/api/v1/perfiles";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const TRASPASOS = "http://127.0.0.1:8000/api/v1/traspasos";
const PLANTILLAS = "http://127.0.0.1:8000/api/v1/plantillas";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <TraspasosDelTorneoPage />
    </Wrapper>,
  );
}

function mockBase() {
  server.use(
    http.get(JUGADORES, () => HttpResponse.json([{ id: 1, nombre: "Carlos Pérez" }])),
    http.get(PERFILES, () => HttpResponse.json([{ id: 1, jugador_id: 1 }])),
    http.get(EQUIPOS, () =>
      HttpResponse.json([
        { id: 1, nombre: "Halcones FC" },
        { id: 2, nombre: "Tiburones FC" },
      ]),
    ),
    http.get(INSCRIPCIONES, () =>
      HttpResponse.json([
        { id: 5, equipo_id: 1 },
        { id: 6, equipo_id: 2 },
      ]),
    ),
    http.get(TRASPASOS, () => HttpResponse.json([])),
    // D3 (fixes-datos-traspasos-control-mesa-plan.md): useOrigenActualDelPerfil
    // (con torneo_id) y useDorsalesHistoricos (sin torneo_id) pegan al mismo
    // endpoint con distinto query — acá el jugador no tiene ningún vínculo,
    // así que "Agencia Libre" y sin chips de dorsal (EC-Tr1).
    http.get(PLANTILLAS, () => HttpResponse.json([])),
  );
}

describe("TraspasosDelTorneoPage", () => {
  it("resuelve jugador y equipos de origen/destino a nombres", async () => {
    mockBase();
    server.use(
      http.get(TRASPASOS, () =>
        HttpResponse.json([
          {
            id: 1,
            jugador_perfil_id: 1,
            inscripcion_origen_id: 5,
            inscripcion_destino_id: 6,
            motivo: "Prueba",
            fecha_traspaso: "2026-02-01T10:00:00",
            estado: "Completado",
          },
        ]),
      ),
    );
    renderPagina();

    expect(await screen.findByText("Carlos Pérez")).toBeInTheDocument();
    expect(screen.getByText("Halcones FC → Tiburones FC")).toBeInTheDocument();
  });

  it("busca el jugador por nombre/cédula, autocompleta el origen y crea el traspaso", async () => {
    mockBase();
    server.use(
      // SelectorJugadorBuscable — GET /jugadores?q= (mismo endpoint que
      // JUGADORES pero acá se le agrega el resultado de la búsqueda).
      http.get(JUGADORES, ({ request }) => {
        const q = new URL(request.url).searchParams.get("q") ?? "";
        return HttpResponse.json(
          q.trim() === "" ? [] : [{ id: 1, nombre: "Carlos Pérez", cedula: "0900000001" }],
        );
      }),
      // Origen: membresía Activo en ESTE torneo → "Halcones FC" (no
      // Agencia Libre). Dorsales históricos: [7].
      http.get(PLANTILLAS, ({ request }) => {
        const url = new URL(request.url);
        if (url.searchParams.get("torneo_id")) {
          return HttpResponse.json([
            { id: 9, inscripcion_torneo_id: 5, dorsal: 7, estado: "Activo" },
          ]);
        }
        return HttpResponse.json([{ id: 9, inscripcion_torneo_id: 5, dorsal: 7, estado: "Activo" }]);
      }),
    );
    let bodyRecibido: unknown;
    server.use(
      http.post(TRASPASOS, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 2, estado: "Completado" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Nuevo traspaso" }));
    await user.type(await screen.findByLabelText("Jugador"), "Carlos");
    await user.click(await screen.findByRole("button", { name: "Elegir" }));

    expect(await screen.findByText("Halcones FC")).toBeInTheDocument();
    // Chip de dorsal histórico precarga el input.
    await user.click(await screen.findByRole("button", { name: "7" }));
    expect(screen.getByLabelText("Dorsal nuevo")).toHaveValue(7);

    await user.selectOptions(screen.getByLabelText("Equipo destino"), "6");
    await user.click(screen.getByRole("button", { name: "Traspasar" }));

    await waitFor(() =>
      expect(bodyRecibido).toMatchObject({
        jugador_perfil_id: 1,
        inscripcion_origen_id: 5,
        inscripcion_destino_id: 6,
        dorsal_nuevo: 7,
      }),
    );
  });

  it("jugador sin membresía activa en este torneo: origen es Agencia Libre, sin chips de dorsal", async () => {
    mockBase();
    server.use(
      http.get(JUGADORES, ({ request }) => {
        const q = new URL(request.url).searchParams.get("q") ?? "";
        return HttpResponse.json(
          q.trim() === "" ? [] : [{ id: 1, nombre: "Carlos Pérez", cedula: "0900000001" }],
        );
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Nuevo traspaso" }));
    await user.type(await screen.findByLabelText("Jugador"), "Carlos");
    await user.click(await screen.findByRole("button", { name: "Elegir" }));

    expect(await screen.findByText("Agencia Libre")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "7" })).not.toBeInTheDocument();
  });

  // fixes-datos-traspasos-control-mesa-plan.md: anular ahora revierte de
  // verdad (jugador vuelve al origen) — el backend decide si todavía se
  // puede vía `puede_anularse`, el frontend solo lo respeta.
  it("anular llama a POST /traspasos/{id}/anular cuando puede_anularse es true", async () => {
    mockBase();
    server.use(
      http.get(TRASPASOS, () =>
        HttpResponse.json([
          {
            id: 1,
            jugador_perfil_id: 1,
            inscripcion_origen_id: 5,
            inscripcion_destino_id: 6,
            motivo: null,
            fecha_traspaso: "2026-02-01T10:00:00",
            estado: "Completado",
            puede_anularse: true,
          },
        ]),
      ),
    );
    let llamado = false;
    server.use(
      http.post(`${TRASPASOS}/1/anular`, () => {
        llamado = true;
        return HttpResponse.json({ id: 1, estado: "Anulado" });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "Anular" }));

    await waitFor(() => expect(llamado).toBe(true));
  });

  it("sin puede_anularse (el club destino ya jugó): el botón Anular no aparece", async () => {
    mockBase();
    server.use(
      http.get(TRASPASOS, () =>
        HttpResponse.json([
          {
            id: 1,
            jugador_perfil_id: 1,
            inscripcion_origen_id: 5,
            inscripcion_destino_id: 6,
            motivo: null,
            fecha_traspaso: "2026-02-01T10:00:00",
            estado: "Completado",
            puede_anularse: false,
          },
        ]),
      ),
    );
    renderPagina();

    await screen.findByText("Carlos Pérez");
    expect(screen.queryByRole("button", { name: "Anular" })).not.toBeInTheDocument();
  });
});
