import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import { server } from "../test/msw-server";
import { createTestQueryClient } from "../test/test-utils";
import { limpiarEventoPendiente } from "../lib/colaOfflineEventos";
import { MesaPanel } from "./MesaPanel";

const PARTIDO_3 = "http://127.0.0.1:8000/api/v1/partidos/3";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const EVENTOS = "http://127.0.0.1:8000/api/v1/eventos";
const EVENTOS_PARTIDO = "http://127.0.0.1:8000/api/v1/eventos-partido";
const PLANTILLA_1 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/1/plantilla";
const PLANTILLA_2 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/2/plantilla";
const CONVOCADOS_3 = "http://127.0.0.1:8000/api/v1/partidos/3/convocados";
const CRONOMETRO_3 = "http://127.0.0.1:8000/api/v1/partidos/3/cronometro";
const TORNEO_1 = "http://127.0.0.1:8000/api/v1/torneos/1";

// Área 3 (modo-vivo-sustituciones-cierre-plan.md, T3): CargaEvento ahora
// depende de que <Cronometro> haya emitido un minuto (onMinutoActual) —
// sin este mock, la query de /cronometro queda sin handler
// (onUnhandledRequest: "error" en setup.ts) y "Confirmar" nunca se
// habilita. timestamp_real "ahora mismo" → minuto acumulado ≈ 0, un
// número real (no null), que es todo lo que hace falta para desbloquear
// el form.
const CRONOMETRO_EN_CURSO = {
  tipo_cronometro: "Periodos",
  cantidad_periodos: 2,
  duracion_periodo_minutos: 45,
  duracion_descanso_minutos: 15,
  partido_iniciado: true,
  partido_finalizado: false,
  periodo_abierto: 1,
  ultimo_periodo_cerrado: 0,
  en_pausa: false,
  acciones_permitidas: ["Pausa", "Fin_Periodo"],
  hitos: [
    {
      id: 1,
      tipo_hito: "Inicio_Partido",
      numero_periodo: null,
      timestamp_real: new Date().toISOString(),
      minuto_reloj: null,
      registrado_por: 42,
      fecha_registro: new Date().toISOString(),
    },
    {
      id: 2,
      tipo_hito: "Inicio_Periodo",
      numero_periodo: 1,
      timestamp_real: new Date().toISOString(),
      minuto_reloj: null,
      registrado_por: 42,
      fecha_registro: new Date().toISOString(),
    },
  ],
};

const SESSION_STORAGE_KEY = "score-app.session";

const PARTIDO_EN_CURSO = {
  id: 3,
  estado: "En curso",
  fecha_partido: "2026-02-05T16:00:00",
  torneo_id: 1,
  equipos_id_local: 1,
  equipos_id_visitante: 2,
  jornada: 1,
  arbitro_id: 42,
};

function sembrarSesion(rol: string = "Arbitro", username: string = "arbitro_test", id: number = 42) {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username, rol, id }));

}

function montarMesaPanel(props: { onIrAConvocatoria?: () => void } = {}) {
  server.use(
    http.get(PARTIDO_3, () => HttpResponse.json(PARTIDO_EN_CURSO)),
    http.get(EQUIPOS, () =>
      HttpResponse.json([
        { id: 1, nombre: "Tiburones FC" },
        { id: 2, nombre: "Águilas del Sur" },
      ]),
    ),
    http.get(EVENTOS, () =>
      HttpResponse.json([
        { id: 1, nombre: "Gol", estado: "Activo" },
        { id: 3, nombre: "Tarjeta Roja", estado: "Activo" },
      ]),
    ),
    http.get(EVENTOS_PARTIDO, () => HttpResponse.json([])),
    http.get(PLANTILLA_1, () =>
      HttpResponse.json([
        { jugador_id: 5, jugador: "Andrés Vera", equipo_id: 1, equipo: "Tiburones FC", dorsal: 9, jugador_perfil_id: 50 },
      ]),
    ),
    http.get(PLANTILLA_2, () => HttpResponse.json([])),
    // 3B-2 (docs/plans/cierre-backlog-todos-plan.md): sin convocatoria
    // guardada — MesaPanel debe seguir ofreciendo toda la plantilla, ver
    // Convocatoria.tsx.
    http.get(CONVOCADOS_3, () => HttpResponse.json([])),
    http.get(CRONOMETRO_3, () => HttpResponse.json(CRONOMETRO_EN_CURSO)),
    http.get(TORNEO_1, () => HttpResponse.json({ id: 1, maximo_cambios_por_equipo: null, permite_cambios_ilimitados: false })),
  );
  sembrarSesion();
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MesaPanel partidoId={3} onIrAConvocatoria={props.onIrAConvocatoria} />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

/** Carga un Gol de Tiburones FC (Andrés Vera) — mismo flujo tap-a-tap que
 * un árbitro real, hasta el botón "Confirmar". El minuto ya no se tipea
 * (T3): sale del cronómetro en vivo (ver CRONOMETRO_EN_CURSO más arriba),
 * "Confirmar" espera a que <Cronometro> emita ese valor. */
async function cargarUnGol(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /Gol/ }));
  await user.click(screen.getByRole("button", { name: "Tiburones FC" }));
  await user.click(screen.getByRole("button", { name: /Andrés Vera/ }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirmar" })).toBeEnabled());
  await user.click(screen.getByRole("button", { name: "Confirmar" }));
}

describe("MesaPanel — offline-first (3B-1, docs/plans/cierre-backlog-todos-plan.md)", () => {
  beforeEach(() => {
    // Cola limpia entre tests — localStorage es compartido por todo el
    // entorno de tests, no se resetea solo entre `it()`.
    limpiarEventoPendiente(3);
  });

  it("un fallo de RED (no un rechazo del backend) encola el evento en vez de perderlo", async () => {
    server.use(http.post(EVENTOS_PARTIDO, () => HttpResponse.error()));
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");

    await cargarUnGol(user);

    expect(await screen.findByText(/todavía no se pudo enviar/)).toBeInTheDocument();
    // El form de carga se oculta mientras haya algo pendiente — un solo
    // slot de cola, no se pisa con un segundo evento.
    expect(screen.queryByText("Cargar evento")).not.toBeInTheDocument();
  });

  it("al reconectar, el evento encolado se envía solo y el form vuelve", async () => {
    server.use(http.post(EVENTOS_PARTIDO, () => HttpResponse.error()));
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");
    await cargarUnGol(user);
    await screen.findByText(/todavía no se pudo enviar/);

    let cuerpoRecibido: unknown;
    server.use(
      http.post(EVENTOS_PARTIDO, async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json({ id: 1, estado: "Registrado" }, { status: 201 });
      }),
    );

    window.dispatchEvent(new Event("online"));

    await waitFor(() => expect(cuerpoRecibido).toMatchObject({ jugador_id: 5, equipo_id: 1, eventos_id: 1 }));
    expect(await screen.findByText("Cargar evento")).toBeInTheDocument();
    expect(screen.queryByText(/todavía no se pudo enviar/)).not.toBeInTheDocument();
  });

  it("un rechazo REAL del backend (no de red) no se encola — el form muestra el error de siempre", async () => {
    server.use(
      http.post(EVENTOS_PARTIDO, () => HttpResponse.json({ detail: "El jugador no pertenece a ese equipo." }, { status: 400 })),
    );
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");

    await cargarUnGol(user);

    expect(await screen.findByText("El jugador no pertenece a ese equipo.")).toBeInTheDocument();
    // Sigue siendo el form normal, no el card de "pendiente" — un 400 no
    // es un problema de conexión.
    expect(screen.getByText("Cargar evento")).toBeInTheDocument();
  });

  it("'Descartar' saca el evento pendiente sin enviarlo", async () => {
    server.use(http.post(EVENTOS_PARTIDO, () => HttpResponse.error()));
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");
    await cargarUnGol(user);
    await screen.findByText(/todavía no se pudo enviar/);

    await user.click(screen.getByRole("button", { name: "Descartar" }));

    expect(await screen.findByText("Cargar evento")).toBeInTheDocument();
  });
});

// D1 (docs/plans/cierre-pendientes-todos-plan.md): antes NINGUNA carga de
// evento mostraba confirmación de éxito (Design Fase 2, Pass 2, GAP
// CRÍTICO — "la pantalla se ve muerta"). Región aria-live única para
// "Guardando…" y, después, el contenido del evento confirmado.
describe("MesaPanel — confirmación aria-live de éxito (D1)", () => {
  beforeEach(() => {
    limpiarEventoPendiente(3);
  });

  it("tras cargar un Gol con éxito, la región aria-live muestra la confirmación con jugador y minuto", async () => {
    server.use(
      http.post(EVENTOS_PARTIDO, async ({ request }) => {
        const body = (await request.json()) as { minuto?: number };
        return HttpResponse.json({ id: 1, estado: "Registrado", minuto: body.minuto ?? 12 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");

    await cargarUnGol(user);

    expect(await screen.findByText(/Gol registrado: #9 Andrés Vera/)).toBeInTheDocument();
  });
});

// C2a (docs/plans/cierre-pendientes-todos-plan.md): sin convocatoria
// guardada, `enCanchaJugadorIds` sale vacío por diseño (deriveTitularSuplente)
// — antes eso dejaba "Alineación en vivo" siempre vacía, sin ningún
// "Sacar" posible: un partido sin convocatoria (D4, resultado directo)
// arrancado en vivo no tenía forma de cargar un Cambio salvo por el
// camino viejo de CargaEvento (retirado en C2b). Estos dos tests son el
// test automatizado compañero del gate de C2a (obligación E10 de la
// revisión eng): la lista de fallback renderiza con su caption, y un
// Cambio enviado desde ella produce el mismo body de POST que el camino
// con convocatoria. montarMesaPanel() ya mockea CONVOCADOS_3 en `[]`
// (sin convocatoria) para TODO este archivo.
describe("MesaPanel — alineación en vivo sin convocatoria (C2a)", () => {
  beforeEach(() => {
    limpiarEventoPendiente(3);
  });

  function plantillaDosJugadores() {
    return HttpResponse.json([
      { jugador_id: 5, jugador: "Andrés Vera", equipo_id: 1, equipo: "Tiburones FC", dorsal: 9, jugador_perfil_id: 50 },
      { jugador_id: 6, jugador: "Bruno Ríos", equipo_id: 1, equipo: "Tiburones FC", dorsal: 10, jugador_perfil_id: 51 },
    ]);
  }

  it("muestra la plantilla completa con el caption de fallback, no la lista vacía de siempre", async () => {
    montarMesaPanel();
    // Después de montar: montarMesaPanel() registra sus propios handlers
    // por default (incluido PLANTILLA_1 con un solo jugador) y MSW
    // resuelve por el ÚLTIMO handler registrado — un override de acá
    // ANTES de montar quedaría tapado por el default.
    server.use(http.get(PLANTILLA_1, plantillaDosJugadores));

    expect(
      await screen.findByText("Sin convocatoria guardada — mostrando plantilla completa."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Andrés Vera/)).toBeInTheDocument();
    expect(screen.getByText(/Bruno Ríos/)).toBeInTheDocument();
    // El otro equipo (Águilas del Sur, PLANTILLA_2) sí sigue vacío de
    // verdad — ese es el caso legítimo del empty state, no el que C2a
    // corrige (que era Tiburones FC con plantilla, mostrando "vacío" por
    // filtrar contra una convocatoria que no existe).
    const filaAguilas = screen.getByRole("heading", { name: "Águilas del Sur", level: 3 }).closest("div");
    if (!filaAguilas) throw new Error("No se encontró la sección de Águilas del Sur");
    expect(within(filaAguilas).getByText("Sin nadie en cancha marcado en la convocatoria.")).toBeInTheDocument();
  });

  it("un Cambio cargado desde ModalSustitucion sin convocatoria produce el mismo body que con convocatoria", async () => {
    const user = userEvent.setup();
    montarMesaPanel();
    let bodyRecibido: unknown;
    server.use(
      http.get(PLANTILLA_1, plantillaDosJugadores),
      http.get(EVENTOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Gol", estado: "Activo" },
          { id: 3, nombre: "Tarjeta Roja", estado: "Activo" },
          { id: 4, nombre: "Cambio", estado: "Activo" },
        ]),
      ),
      http.post(EVENTOS_PARTIDO, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1, estado: "Registrado" }, { status: 201 });
      }),
    );

    await screen.findByText("Sin convocatoria guardada — mostrando plantilla completa.");
    const filaAndres = screen.getByText(/Andrés Vera/).closest("li");
    if (!filaAndres) throw new Error("No se encontró la fila de Andrés Vera");
    await user.click(within(filaAndres).getByRole("button", { name: "Sacar" }));

    await user.click(await screen.findByRole("button", { name: /Bruno Ríos/ }));

    await waitFor(() =>
      expect(bodyRecibido).toMatchObject({
        partidos_id: 3,
        jugador_id: 5,
        equipo_id: 1,
        eventos_id: 4,
        jugador_id_entra: 6,
      }),
    );
  });

  it("ModalSustitucion sin ningún elegible ofrece 'Ir a Convocatoria', que scrollea al editor en la misma página", async () => {
    // El default de montarMesaPanel() ya deja PLANTILLA_1 con un solo
    // jugador — al "Sacar"lo no queda nadie más para "Entra", ni siquiera
    // con el fallback de C2a.
    const user = userEvent.setup();
    // `onIrAConvocatoria` simula lo que GestionarPartido conecta de
    // verdad (scroll a #convocatoria-editor en la misma página) — acá
    // solo se prueba que MesaPanel/ModalSustitucion lo invocan.
    let scrolleoAConvocatoria = false;
    montarMesaPanel({ onIrAConvocatoria: () => { scrolleoAConvocatoria = true; } });

    const filaAndres = await screen.findByText(/Andrés Vera/);
    const li = filaAndres.closest("li");
    if (!li) throw new Error("No se encontró la fila de Andrés Vera");
    await user.click(within(li).getByRole("button", { name: "Sacar" }));

    await user.click(await screen.findByRole("button", { name: "Ir a Convocatoria" }));
    expect(scrolleoAConvocatoria).toBe(true);
  });
});

// C2b (docs/plans/cierre-pendientes-todos-plan.md): retiro del camino
// viejo de "Cambio" dentro de CargaEvento — ModalSustitucion (arriba) es
// el único camino que queda para registrar un Cambio en vivo.
describe("MesaPanel — CargaEvento sin la opción Cambio (C2b)", () => {
  beforeEach(() => {
    limpiarEventoPendiente(3);
  });

  it("la grilla de 'Cargar evento' no ofrece Cambio como tipo", async () => {
    montarMesaPanel();
    await screen.findByText("Cargar evento");

    expect(screen.getByRole("button", { name: /Gol/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Autogol/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tarjeta Amarilla/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tarjeta Roja/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^🔄 Cambio$/ })).not.toBeInTheDocument();
  });
});

// control-mesa-centralizacion-fixture-plan.md, ítem 1/2: RBAC scoping +
