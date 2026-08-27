import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { server } from "../../test/msw-server";
import { createTestQueryClient, createWrapper } from "../../test/test-utils";
import { RegistroLoteAdminPage, type RegistroLoteAlcanceTorneo, type RegistroLotePreResuelto } from "./RegistroLoteAdmin";

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const VALIDAR = "http://127.0.0.1:8000/api/v1/plantillas/lote/validar";
const CONFIRMAR = "http://127.0.0.1:8000/api/v1/plantillas/lote/confirmar";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <RegistroLoteAdminPage />
    </Wrapper>,
  );
}

/** createWrapper() no deja fijar location.state — necesario para probar el
 * contexto que llega desde el modal "Agregar Equipo" (torneos-admin-plan.md,
 * Fase 2). MemoryRouter propio en vez de reusar el wrapper compartido. */
function renderPreResuelto(state: RegistroLotePreResuelto | RegistroLoteAlcanceTorneo) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[{ pathname: "/torneo-admin/plantillas/lote", state }]}>
        <RegistroLoteAdminPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function llenarFormulario(user: ReturnType<typeof userEvent.setup>) {
  // Espera a que /inscripciones (+ /torneos, /equipos) terminen de cargar
  // y el <select> deje de estar disabled — si no, selectOptions falla
  // porque la única <option> presente todavía es "Elegir...".
  await screen.findByText("Copa Ecotec 2026 — Tiburones FC");
  await user.selectOptions(screen.getByLabelText("Torneo — Equipo"), "1");
  await user.type(screen.getByLabelText("Fecha de inicio"), "2026-02-01");
  await user.type(screen.getByLabelText("Cédula fila 1"), "0900000099");
  await user.type(screen.getByLabelText("Nombre fila 1"), "Jugador Prueba");
  await user.type(screen.getByLabelText("Correo fila 1"), "prueba@example.com");
}

describe("RegistroLoteAdminPage", () => {
  beforeEach(() => {
    server.use(
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Tiburones FC" }])),
      http.get(TORNEOS, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 1, equipo_id: 1 }])),
    );
  });

  it("valida y muestra la fila en Válidos", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(VALIDAR, () =>
        HttpResponse.json({
          validos: [
            {
              fila_index: 0,
              cedula: "0900000099",
              nombre: "Jugador Prueba",
              correo_electronico: "prueba@example.com",
              dorsal: null,
              jugador_id: null,
            },
          ],
          invalidos: [],
        }),
      ),
    );
    renderPagina();
    await llenarFormulario(user);
    await user.click(screen.getByRole("button", { name: "Validar" }));

    expect(await screen.findByText("✅ Válidos (1)")).toBeInTheDocument();
    expect(screen.getByText("Jugador Prueba")).toBeInTheDocument();
    expect(screen.queryByText(/Inválidos/)).not.toBeInTheDocument();
  });

  it("una fila inválida muestra el motivo y no bloquea Confirmar si hay válidos", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(VALIDAR, () =>
        HttpResponse.json({
          validos: [
            {
              fila_index: 0,
              cedula: "0900000099",
              nombre: "Jugador Prueba",
              correo_electronico: "prueba@example.com",
              dorsal: null,
              jugador_id: null,
            },
          ],
          invalidos: [
            { fila_index: 1, cedula: "0900000001", nombre: "Carlos Pérez", motivo: "Ya juega en Tiburones FC este torneo — usa Traspasos en Plantillas para moverlo" },
          ],
        }),
      ),
    );
    renderPagina();
    await llenarFormulario(user);
    await user.click(screen.getByRole("button", { name: "Validar" }));

    expect(await screen.findByText("⚠️ Inválidos (1)")).toBeInTheDocument();
    expect(screen.getByText(/Ya juega en Tiburones FC/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar" })).not.toBeDisabled();
  });

  it("confirmar con éxito parcial vuelve a mostrar los rechazados", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(VALIDAR, () =>
        HttpResponse.json({
          validos: [
            {
              fila_index: 0,
              cedula: "0900000099",
              nombre: "Jugador Prueba",
              correo_electronico: "prueba@example.com",
              dorsal: null,
              jugador_id: null,
            },
          ],
          invalidos: [],
        }),
      ),
      http.post(CONFIRMAR, () =>
        HttpResponse.json({
          insertados: [],
          rechazados: [
            { fila_index: 0, cedula: "0900000099", nombre: "Jugador Prueba", motivo: "Otro admin registró este dato justo antes — revisar e intentar de nuevo." },
          ],
        }),
      ),
    );
    renderPagina();
    await llenarFormulario(user);
    await user.click(screen.getByRole("button", { name: "Validar" }));
    await screen.findByText("✅ Válidos (1)");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText("0 de 1 jugador(es) registrado(s).")).toBeInTheDocument();
    expect(screen.getByText(/Otro admin registró/)).toBeInTheDocument();
  });

  it("éxito total muestra el mensaje de confirmación", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(VALIDAR, () =>
        HttpResponse.json({
          validos: [
            {
              fila_index: 0,
              cedula: "0900000099",
              nombre: "Jugador Prueba",
              correo_electronico: "prueba@example.com",
              dorsal: null,
              jugador_id: null,
            },
          ],
          invalidos: [],
        }),
      ),
      http.post(CONFIRMAR, () =>
        HttpResponse.json({
          insertados: [{ id: 1 }],
          rechazados: [],
        }),
      ),
    );
    renderPagina();
    await llenarFormulario(user);
    await user.click(screen.getByRole("button", { name: "Validar" }));
    await screen.findByText("✅ Válidos (1)");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(screen.getByText("1 jugador(es) registrado(s).")).toBeInTheDocument());
  });

  it("con contexto pre-resuelto (modal Agregar Equipo) no pide Torneo — Equipo ni Fecha", async () => {
    renderPreResuelto({
      inscripcionTorneoId: 5,
      contexto: "Halcones FC — Liga Relámpago Ed. 2",
      volverA: "/torneo-admin/torneos/2",
    });

    expect(await screen.findByText("Halcones FC — Liga Relámpago Ed. 2")).toBeInTheDocument();
    expect(screen.queryByLabelText("Torneo — Equipo")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Fecha de inicio")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
  });

  it("con contexto pre-resuelto: éxito total ofrece volver al torneo, no a Plantillas", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(VALIDAR, () =>
        HttpResponse.json({
          validos: [
            {
              fila_index: 0,
              cedula: "0900000099",
              nombre: "Jugador Prueba",
              correo_electronico: "prueba@example.com",
              dorsal: null,
              jugador_id: null,
            },
          ],
          invalidos: [],
        }),
      ),
      http.post(CONFIRMAR, () => HttpResponse.json({ insertados: [{ id: 1 }], rechazados: [] })),
    );
    renderPreResuelto({
      inscripcionTorneoId: 5,
      contexto: "Halcones FC — Liga Relámpago Ed. 2",
      volverA: "/torneo-admin/torneos/2",
    });

    await screen.findByText("Halcones FC — Liga Relámpago Ed. 2");
    await user.type(screen.getByLabelText("Cédula fila 1"), "0900000099");
    await user.type(screen.getByLabelText("Nombre fila 1"), "Jugador Prueba");
    await user.type(screen.getByLabelText("Correo fila 1"), "prueba@example.com");
    await user.click(screen.getByRole("button", { name: "Validar" }));
    await screen.findByText("✅ Válidos (1)");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByRole("button", { name: "Volver al Torneo" })).toBeInTheDocument();
  });

  it("con alcance de torneo (sin equipo pre-resuelto): pide solo Equipo, ya filtrado por torneo_id", async () => {
    server.use(
      http.get(INSCRIPCIONES, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("torneo_id")).toBe("20");
        return HttpResponse.json([{ id: 5, torneo_id: 20, equipo_id: 1 }]);
      }),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
    );
    renderPreResuelto({ torneoId: 20, volverA: "/torneo-admin/torneos/20/plantillas" });

    expect(await screen.findByLabelText("Equipo")).toBeInTheDocument();
    expect(screen.queryByLabelText("Torneo — Equipo")).not.toBeInTheDocument();
    expect(await screen.findByText("Halcones FC")).toBeInTheDocument();
  });
});
