import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { ModalSiguienteFase } from "./ModalSiguienteFase";

const TORNEO_ID = 30;
const POSICIONES_URL = `http://127.0.0.1:8000/api/v1/estadisticas/torneos/${TORNEO_ID}/posiciones`;
const CERRAR_URL = `http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}/cerrar`;
const PLAYOFFS_URL = `http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}/playoffs`;

function renderModal(props: Partial<Parameters<typeof ModalSiguienteFase>[0]> = {}) {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <ModalSiguienteFase
        torneoId={TORNEO_ID}
        accionesDisponibles={["cerrar_directo", "generar_playoffs"]}
        formatoEliminatoriaActual="Unico"
        clasificadosPorGrupoActual={2}
        onClose={vi.fn()}
        onCerrado={vi.fn()}
        onPlayoffsGenerados={vi.fn()}
        {...props}
      />
    </Wrapper>,
  );
}

describe("ModalSiguienteFase — exclusividad de los 2 caminos", () => {
  it("con los 2 caminos disponibles, muestra el paso 1 con ambas opciones", async () => {
    renderModal();
    expect(await screen.findByText("Configurar Siguiente Fase")).toBeInTheDocument();
    expect(screen.getByText("Terminar el torneo (campeones por tabla)")).toBeInTheDocument();
    expect(screen.getByText("Jugar Playoffs")).toBeInTheDocument();
  });

  it("con una sola acción disponible, el paso 1 se salta (D9)", async () => {
    server.use(http.get(POSICIONES_URL, () => HttpResponse.json([])));
    renderModal({ accionesDisponibles: ["cerrar_directo"] });
    expect(await screen.findByText("Cerrar torneo y coronar campeones")).toBeInTheDocument();
    expect(screen.queryByText("Configurar Siguiente Fase")).not.toBeInTheDocument();
  });

  it("elegir 'Jugar Playoffs' navega al paso de generar playoffs, con Volver", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByText("Jugar Playoffs"));
    expect(await screen.findByRole("heading", { name: "Generar Playoffs" })).toBeInTheDocument();
    expect(screen.getByText("Paso 2 de 2 · Playoffs")).toBeInTheDocument();
    await user.click(screen.getByText("← Volver"));
    expect(await screen.findByText("Configurar Siguiente Fase")).toBeInTheDocument();
  });
});

describe("ModalSiguienteFase — preview de podio (paso 2a)", () => {
  it("muestra los primeros 3 de la tabla con Pts/DG/GF", async () => {
    server.use(
      http.get(POSICIONES_URL, () =>
        HttpResponse.json([
          { equipo_id: 1, equipo: "Tigres", pj: 3, pts: 9, dg: 5, gf: 6 },
          { equipo_id: 2, equipo: "Leones", pj: 3, pts: 6, dg: 1, gf: 4 },
          { equipo_id: 3, equipo: "Osos", pj: 3, pts: 3, dg: -2, gf: 2 },
          { equipo_id: 4, equipo: "Águilas", pj: 3, pts: 0, dg: -4, gf: 1 },
        ]),
      ),
    );
    renderModal({ accionesDisponibles: ["cerrar_directo"] });
    expect(await screen.findByText(/1° Tigres/)).toBeInTheDocument();
    expect(screen.getByText(/2° Leones/)).toBeInTheDocument();
    expect(screen.getByText(/3° Osos/)).toBeInTheDocument();
    expect(screen.queryByText(/Águilas/)).not.toBeInTheDocument();
    expect(screen.getByText(/Pts 9 · DG 5 · GF 6/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Cerrar torneo y coronar a Tigres" })).toBeInTheDocument();
  });

  it("un empate en el podio ofrece reordenar con flechas, y el orden elegido viaja en orden_podio", async () => {
    server.use(
      http.get(POSICIONES_URL, () =>
        HttpResponse.json([
          { equipo_id: 1, equipo: "Tigres", pj: 3, pts: 6, dg: 2, gf: 4 },
          { equipo_id: 2, equipo: "Leones", pj: 3, pts: 6, dg: 2, gf: 4 },
          { equipo_id: 3, equipo: "Osos", pj: 3, pts: 3, dg: -2, gf: 2 },
        ]),
      ),
    );
    let cuerpoEnviado: { orden_podio?: number[] } | undefined;
    server.use(
      http.post(CERRAR_URL, async ({ request }) => {
        cuerpoEnviado = (await request.json()) as never;
        return HttpResponse.json({ id: TORNEO_ID, estado: "Finalizado" });
      }),
    );
    const user = userEvent.setup();
    renderModal({ accionesDisponibles: ["cerrar_directo"] });

    expect(await screen.findByText(/1° Tigres/)).toBeInTheDocument();
    // Los 2 equipos empatados muestran la nota — Osos (3er puesto, sin
    // empate) no.
    expect(screen.getAllByText(/Desempatado por orden manual/)).toHaveLength(2);

    // Baja a Tigres un puesto (Leones pasa a ser 1°).
    await user.click(screen.getByRole("button", { name: "Bajar a Tigres" }));
    expect(await screen.findByText(/1° Leones/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Cerrar torneo y coronar a Leones/ }));
    await waitFor(() => expect(cuerpoEnviado).toEqual({ orden_podio: [2, 1, 3] }));
  });
});

describe("ModalSiguienteFase — selector de formato de eliminatoria (paso 2b)", () => {
  it("muestra los 3 radios de formato, pre-cargado con el valor actual del torneo", async () => {
    renderModal({ accionesDisponibles: ["generar_playoffs"], formatoEliminatoriaActual: "Mixto" });
    expect(await screen.findByText("Único")).toBeInTheDocument();
    expect(screen.getByText("Ida y vuelta")).toBeInTheDocument();
    expect(screen.getByText("Mixto")).toBeInTheDocument();
    const radioMixto = screen.getByRole("radio", { name: /Mixto/ });
    expect(radioMixto).toBeChecked();
  });

  it("envía formato_eliminatoria y clasificados_por_grupo elegidos", async () => {
    let cuerpoEnviado: { clasificados_por_grupo?: number; formato_eliminatoria?: string } | undefined;
    server.use(
      http.post(PLAYOFFS_URL, async ({ request }) => {
        cuerpoEnviado = (await request.json()) as never;
        return HttpResponse.json({ id: 5, estado: "Pendiente" });
      }),
    );
    const user = userEvent.setup();
    renderModal({ accionesDisponibles: ["generar_playoffs"], formatoEliminatoriaActual: "Unico" });

    await user.click(await screen.findByRole("radio", { name: /^Ida y vuelta/ }));
    await user.click(screen.getByRole("button", { name: "Generar Playoffs" }));

    await waitFor(() =>
      expect(cuerpoEnviado).toEqual({ clasificados_por_grupo: 2, formato_eliminatoria: "Ida_Vuelta" }),
    );
  });
});
