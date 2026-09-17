import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api, apiErrorMessage } from "../api/client";
import {
  consecuenciaCortaDesempate,
  etiquetaReglaDesempate,
  type MetodoDesempateEliminatoriaOTorneo,
} from "../lib/desempate";

const TICK_MS = 1000;
const POLL_MS = 5000;

type TipoHito = "Inicio_Partido" | "Inicio_Periodo" | "Fin_Periodo" | "Pausa" | "Reanudacion" | "Fin_Partido";
// Área 4 (T6/T13): picklist de motivo de cierre forzado — ver el
// comentario grande en app/schemas/hito_partido.py (backend) para por qué
// no es texto libre.
type MotivoCierre = "Clima" | "Incidente" | "Lesion_Grave" | "Orden_Seguridad" | "Otro";

const MOTIVOS_CIERRE: { valor: MotivoCierre; etiqueta: string }[] = [
  { valor: "Clima", etiqueta: "Clima" },
  { valor: "Incidente", etiqueta: "Incidente" },
  { valor: "Lesion_Grave", etiqueta: "Lesión grave" },
  { valor: "Orden_Seguridad", etiqueta: "Orden de seguridad" },
  { valor: "Otro", etiqueta: "Otro" },
];
const MOTIVO_ETIQUETA: Record<MotivoCierre, string> = Object.fromEntries(
  MOTIVOS_CIERRE.map((m) => [m.valor, m.etiqueta]),
) as Record<MotivoCierre, string>;

interface HitoRow {
  id: number;
  tipo_hito: TipoHito;
  numero_periodo: number | null;
  timestamp_real: string;
  minuto_reloj: number | null;
  forzado?: boolean;
  motivo_cierre?: MotivoCierre | null;
  motivo_cierre_detalle?: string | null;
}

// Área 4 (T17): mismo valor que backend/app/services/hito_partido.py::VENTANA_DESHACER_SEGUNDOS
// — solo se usa acá para mostrar el countdown; la ventana REAL y
// autoritativa la valida el servidor en /deshacer-cierre-forzado.
const VENTANA_DESHACER_SEGUNDOS = 5;

interface EstadoCronometro {
  tipo_cronometro: "Periodos" | "Corrido";
  cantidad_periodos: number | null;
  duracion_periodo_minutos: number | null;
  duracion_descanso_minutos: number | null;
  partido_iniciado: boolean;
  partido_finalizado: boolean;
  periodo_abierto: number | null;
  ultimo_periodo_cerrado: number;
  en_pausa: boolean;
  acciones_permitidas: TipoHito[];
  hitos: HitoRow[];
}

const NOMBRES_PERIODO = ["1er Tiempo", "2do Tiempo", "3er Tiempo", "4to Tiempo", "5to Tiempo", "6to Tiempo"];
const nombrePeriodo = (n: number) => NOMBRES_PERIODO[n - 1] ?? `${n}º Tiempo`;

/** Duración transcurrida del segmento ABIERTO ahora mismo (el período en
 * curso para 'Periodos', todo el partido para 'Corrido'), recalculada
 * desde Timestamp_Real de los Hitos — nunca un contador que se acumula
 * sólo (Design Fase 2, Flujo 5 del plan: "no un setInterval que se
 * desincroniza al perder foco"). Resta el tiempo pausado, mismo criterio
 * que vw_duracion_partido del lado del backend. */
function calcularElapsedMs(estado: EstadoCronometro, nowMs: number): number {
  let inicioSegmento: number | null = null;
  if (estado.tipo_cronometro === "Corrido") {
    const ini = estado.hitos.find((h) => h.tipo_hito === "Inicio_Partido");
    inicioSegmento = ini ? new Date(ini.timestamp_real).getTime() : null;
  } else if (estado.periodo_abierto != null) {
    const ini = estado.hitos.find((h) => h.tipo_hito === "Inicio_Periodo" && h.numero_periodo === estado.periodo_abierto);
    inicioSegmento = ini ? new Date(ini.timestamp_real).getTime() : null;
  }
  if (inicioSegmento == null) return 0;

  const relevantes = estado.hitos
    .filter((h) => (h.tipo_hito === "Pausa" || h.tipo_hito === "Reanudacion") && new Date(h.timestamp_real).getTime() >= inicioSegmento!)
    .sort((a, b) => new Date(a.timestamp_real).getTime() - new Date(b.timestamp_real).getTime());

  let runningSince: number | null = inicioSegmento;
  let accumulated = 0;
  for (const h of relevantes) {
    const t = new Date(h.timestamp_real).getTime();
    if (h.tipo_hito === "Pausa") {
      if (runningSince != null) {
        accumulated += t - runningSince;
        runningSince = null;
      }
    } else if (runningSince == null) {
      runningSince = t;
    }
  }
  if (runningSince != null) accumulated += Math.max(0, nowMs - runningSince);
  return accumulated;
}

function formatearMMSS(ms: number): string {
  const totalSeg = Math.floor(ms / 1000);
  const mm = Math.floor(totalSeg / 60);
  const ss = totalSeg % 60;
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

/** Componente de Cronómetro (gestion-avanzada-equipos-control-mesa-plan.md,
 * Flujo 5) — dos variantes elegidas por Tipo_Cronometro del torneo, la
 * mesa nunca pregunta cuál usar. Embebido en MesaPanel de ControlDeMesa.tsx. */
export function Cronometro(props: {
  partidoId: number;
  equipoLocalId: number;
  equipoVisitanteId: number;
  nombreLocal: string;
  nombreVisitante: string;
  onFinalizado?: () => void;
  /** Si el partido no arrancó, ¿este componente muestra su propio botón de
   * inicio? (gestionar-partido-alineaciones-plan.md, H-10).
   *
   * `false` cuando va embebido en "Gestionar Partido", que ya tiene el botón
   * "Empezar Partido" en su barra de acciones. Sin esto habría dos botones ▶
   * en la misma pantalla con efectos distintos, y el operador podría tocar el
   * que deja el reloj parado. Default `true` para no cambiar el
   * comportamiento de ningún otro consumidor. */
  mostrarInicio?: boolean;
  /** Área 3 (modo-vivo-sustituciones-cierre-plan.md, T3): emite el minuto
   * ACUMULADO del partido en cada tick (o `null` mientras no hay nada que
   * mostrar — sin `Inicio_Partido` o con el partido finalizado), para que
   * `MesaPanel`/`CargaEvento` dejen de pedirlo a mano. Es una lectura
   * aproximada para la UI (suma la duración CONFIGURADA de los períodos ya
   * cerrados, no su duración real con paradas) — el valor que de verdad se
   * persiste lo calcula el servidor desde los Hitos
   * (app/services/minuto_partido.py), con precisión real; esto solo evita
   * que el operador tipee un número a ciegas. */
  onMinutoActual?: (minuto: number | null) => void;
  /** Fase 0 de cierre-fase-regular-llaves-playoffs-plan.md (Finding 1):
   * `true` cuando este partido es de fase Eliminación Y el marcador de
   * goles está empatado — sin UI para esto, ningún partido de bracket
   * empatado se podía cerrar (el trigger lo rechaza pidiendo
   * Ganador_Desempate_ID). Calculado por el padre (MesaPanel ya conoce
   * `ronda_nombre`/marcador), no acá — este componente no tiene visión de
   * goles. Ignorado en un torneo 'Corrido' (ya tiene su propio flujo
   * "¿Quién ganó?" arriba). */
  requiereDesempate?: boolean;
  /** Desempate de eliminatoria: tiempo extra y penales (docs/plans/
   * desempate-tiempo-extra-penales-plan.md, D6/§8, D-D1) — la regla
   * CONCRETA que rige a ESTE partido (`PARTIDOS.Metodo_Desempate_Aplicable`,
   * snapshoteada al arrancar). `'Penales_Directo'` promueve el paso de
   * tanda de penales en vez del radio manual de siempre; cualquier otro
   * valor (incluido `undefined`/`null`, torneos de siempre) mantiene el
   * radio "¿quién avanza?" sin cambios visibles. */
  metodoDesempateAplicable?: "Manual" | "Penales_Directo" | "Tiempo_Extra_Penales" | null;
  /** D-D8: chip de regla vigente — `true` cuando este partido es de fase
   * Eliminación (`ronda_nombre != null`), para saber si hay algo que
   * mostrar. Sin esto el chip no podría distinguir "Manual porque el
   * torneo no es de eliminación" de "Manual porque el operador lo
   * eligió" — los dos leerían igual desde `metodoDesempateAplicable`. */
  esEliminacion?: boolean;
  /** D-D8/D6: antes de que el partido arranque, `metodoDesempateAplicable`
   * todavía es `null` (recién se snapshotea en Inicio_Partido) — el chip
   * usa la regla ACTUAL del torneo como preview mientras tanto (§11-bis:
   * "siempre hay regla"). Incluye `'Penales_Salvo_Final'`, que
   * `metodoDesempateAplicable` nunca puede tener (ya se resuelve a un
   * método concreto al snapshotear). */
  metodoDesempateEliminatoriaTorneo?: MetodoDesempateEliminatoriaOTorneo;
  /** D-D8: `true` cuando este partido es la VUELTA de una llave — el chip
   * suma el GLOBAL (`globalLocal`/`globalVisitante`, ya calculados por el
   * padre igual que `requiereDesempate`), porque eso es lo que está
   * realmente en juego, no el marcador suelto de esta pierna. */
  esVuelta?: boolean;
  globalLocal?: number;
  globalVisitante?: number;
}) {
  const {
    partidoId,
    equipoLocalId,
    equipoVisitanteId,
    nombreLocal,
    nombreVisitante,
    onFinalizado,
    mostrarInicio = true,
    onMinutoActual,
    requiereDesempate = false,
    metodoDesempateAplicable,
    esEliminacion = false,
    metodoDesempateEliminatoriaTorneo,
    esVuelta = false,
    globalLocal,
    globalVisitante,
  } = props;
  const queryClient = useQueryClient();
  const [now, setNow] = useState(() => Date.now());
  const [historialAbierto, setHistorialAbierto] = useState(false);
  const [eligiendoGanador, setEligiendoGanador] = useState(false);
  const [ganadorElegido, setGanadorElegido] = useState<number | null>(null);
  // Desempate manual (Fase 0, Finding 1) — mismo patrón que eligiendoGanador/
  // ganadorElegido de arriba, estado propio porque es un flujo de
  // confirmación distinto (aplica a 'Periodos', no a 'Corrido').
  const [eligiendoDesempate, setEligiendoDesempate] = useState(false);
  const [desempateElegido, setDesempateElegido] = useState<number | null>(null);
  // Desempate de eliminatoria: tiempo extra y penales (D-D1/§9, fase 2) —
  // paso de tanda de penales, promovido en el cronómetro EN VIVO cuando
  // `metodoDesempateAplicable === 'Penales_Directo'`. Steppers, no un
  // radio (D-D4/D-D7): arrancan en 0, el ganador SIEMPRE lo deriva el
  // servidor de la tanda (nunca lo manda este componente) — ver
  // `derivar_ganador_desde_penales` (backend/app/services/desempate.py).
  const [eligiendoPenales, setEligiendoPenales] = useState(false);
  const [penalesLocal, setPenalesLocal] = useState(0);
  const [penalesVisitante, setPenalesVisitante] = useState(0);
  // D-A1/D-D5: escape hatch a Manual desde un torneo configurado con
  // Penales_Directo — permitido a propósito (logueado del lado del
  // servidor, métrica 3), pero con fricción: una hoja de confirmación
  // antes de saltar al radio manual de siempre, para que no sea el
  // camino de menor resistencia.
  const [escapandoAManual, setEscapandoAManual] = useState(false);
  // Área 4 (T6): confirmación del cierre forzado — separado de
  // `eligiendoGanador` (son dos flujos de confirmación distintos, aunque
  // ambos terminan en Fin_Partido).
  const [confirmandoForzado, setConfirmandoForzado] = useState(false);
  const [motivoCierre, setMotivoCierre] = useState<MotivoCierre | null>(null);
  const [motivoDetalle, setMotivoDetalle] = useState("");

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(id);
  }, []);

  const estadoQuery = useQuery({
    queryKey: ["cronometro", partidoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/cronometro", {
        params: { path: { partido_id: partidoId } },
      });
      if (error) throw error;
      return data as EstadoCronometro;
    },
    refetchInterval: POLL_MS,
  });

  const registrar = useMutation({
    mutationFn: async (body: {
      tipo_hito: TipoHito;
      numero_periodo?: number;
      ganador_corrido_id?: number;
      ganador_desempate_id?: number;
      metodo_desempate?: "Tiempo_Extra" | "Penales" | "Manual";
      penales_local?: number;
      penales_visitante?: number;
      forzado?: boolean;
      motivo_cierre?: MotivoCierre;
      motivo_cierre_detalle?: string;
    }) => {
      const { data, error } = await api.POST("/api/v1/partidos/{partido_id}/hitos", {
        params: { path: { partido_id: partidoId } },
        body,
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cronometro", partidoId] });
      queryClient.invalidateQueries({ queryKey: ["partido", partidoId] });
    },
  });

  // Área 4 (T17): deshacer un cierre forzado dentro de la ventana de
  // gracia — autoritativo en el SERVIDOR (ver
  // HitoPartidoService.deshacer_fin_forzado), esto solo dispara el POST.
  const deshacer = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/partidos/{partido_id}/deshacer-cierre-forzado", {
        params: { path: { partido_id: partidoId } },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cronometro", partidoId] });
      queryClient.invalidateQueries({ queryKey: ["partido", partidoId] });
    },
  });

  const corregirHito = useMutation({
    mutationFn: async ({ hitoId, minuto }: { hitoId: number; minuto: number }) => {
      const { data, error } = await api.PATCH("/api/v1/partidos/{partido_id}/hitos/{hito_id}", {
        params: { path: { partido_id: partidoId, hito_id: hitoId } },
        body: { minuto_reloj: minuto },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cronometro", partidoId] }),
  });

  // T3: minuto acumulado aproximado, emitido en cada tick — ver el
  // comentario del prop `onMinutoActual` más arriba. Calculado ANTES de
  // los `return` de carga/error de abajo: los hooks no pueden ser
  // condicionales, así que esto usa `estadoQuery.data` directo (puede ser
  // `undefined` mientras carga) en vez de la variable `estado` angosta que
  // se declara después.
  const minutoActual = useMemo(() => {
    const e = estadoQuery.data;
    if (!e || !e.partido_iniciado || e.partido_finalizado) return null;
    const previos = e.tipo_cronometro === "Periodos" ? (e.ultimo_periodo_cerrado ?? 0) * (e.duracion_periodo_minutos ?? 0) : 0;
    return previos + Math.floor(calcularElapsedMs(e, now) / 60000);
  }, [estadoQuery.data, now]);

  useEffect(() => {
    onMinutoActual?.(minutoActual);
  }, [minutoActual, onMinutoActual]);

  // Área 4 (T17/T25): la ventana de deshacer se deriva 100% de los Hitos
  // que ya vinieron en `GET /cronometro` (Timestamp_Real del último
  // Fin_Partido forzado + VENTANA_DESHACER_SEGUNDOS) — nunca de un timer
  // local ni de localStorage. Por eso el countdown es correcto tras
  // recargar la página a mitad de la ventana (Eng Fase 3, test
  // especificado) sin ningún estado propio del cliente.
  const ultimoHito = estadoQuery.data?.hitos?.at(-1) ?? null;
  const cierreForzado =
    ultimoHito?.tipo_hito === "Fin_Partido" && ultimoHito.forzado ? ultimoHito : null;
  const deshacerHastaMs = cierreForzado ? new Date(cierreForzado.timestamp_real).getTime() + VENTANA_DESHACER_SEGUNDOS * 1000 : null;
  const segundosRestantes = deshacerHastaMs != null ? Math.ceil((deshacerHastaMs - now) / 1000) : null;
  const dentroDeVentanaDeshacer = segundosRestantes != null && segundosRestantes > 0;

  if (estadoQuery.isLoading) return <section className="card cronometro"><p>Cargando cronómetro...</p></section>;
  if (estadoQuery.isError || !estadoQuery.data) {
    return (
      <section className="card cronometro">
        <p className="error-text">No se pudo cargar el cronómetro (¿el torneo tiene configuración de tiempos?).</p>
      </section>
    );
  }
  const estado = estadoQuery.data;

  if (estado.partido_finalizado) {
    onFinalizado?.();
  }

  const elapsedMs = calcularElapsedMs(estado, now);
  const corriendo = !estado.en_pausa && (estado.tipo_cronometro === "Corrido" ? estado.partido_iniciado : estado.periodo_abierto != null);

  function accion(tipo: TipoHito, extra?: Record<string, unknown>) {
    registrar.mutate({ tipo_hito: tipo, ...extra } as never);
  }

  // Botón "Iniciar 1er Tiempo": un solo toque arranca el partido Y el
  // primer período (Inicio_Partido + Inicio_Periodo(1)) — el vocabulario
  // de HITOS_PARTIDO distingue los dos hitos (necesario para
  // vw_duracion_partido y la sincronización de PARTIDOS.Estado), pero la
  // mesa no necesita dos toques para lo que el árbitro percibe como una
  // sola acción.
  async function iniciarPrimerTiempo() {
    await registrar.mutateAsync({ tipo_hito: "Inicio_Partido" } as never);
    await registrar.mutateAsync({ tipo_hito: "Inicio_Periodo", numero_periodo: 1 } as never);
  }

  // Botón "Fin del Partido" en el último período: espejo de
  // iniciarPrimerTiempo, mismo motivo. El backend (HitoPartidoService.
  // _calcular_estado) solo habilita "Fin_Partido" en acciones_permitidas
  // DESPUÉS de que el último período quedó cerrado (Periodo_Abierto is
  // None) — es la misma regla que decide qué botones mostrar acá, así que
  // mandar "Fin_Partido" mientras el período todavía está abierto se
  // rechaza con 400 ("hitos válidos ahora: Pausa, Fin_Periodo"). Un solo
  // toque de mesa cierra el período Y el partido (Fin_Periodo + Fin_Partido),
  // sin exponerle al árbitro los dos hitos por separado.
  async function finalizarUltimoPeriodoYPartido() {
    await registrar.mutateAsync({ tipo_hito: "Fin_Periodo", numero_periodo: estado.periodo_abierto ?? undefined } as never);
    await registrar.mutateAsync({ tipo_hito: "Fin_Partido" } as never);
  }

  // Desempate manual (Fase 0, Finding 1): mismo espejo, con el ganador
  // elegido viajando en el propio Hito Fin_Partido — fn_validar_partido_
  // eliminacion_desempate lo exige antes de dejar pasar el UPDATE a
  // Estado='Finalizado' que este Hito dispara.
  async function finalizarUltimoPeriodoYPartidoConDesempate(ganadorId: number) {
    await registrar.mutateAsync({ tipo_hito: "Fin_Periodo", numero_periodo: estado.periodo_abierto ?? undefined } as never);
    await registrar.mutateAsync({ tipo_hito: "Fin_Partido", ganador_desempate_id: ganadorId } as never);
  }

  // Desempate de eliminatoria: tiempo extra y penales (D-D1/§9, fase 2) —
  // mismo espejo, con la tanda viajando en el propio Hito Fin_Partido. El
  // ganador NO viaja acá: fn_validar_forma_desempate lo deriva de la
  // tanda del lado del servidor (D-D4).
  async function finalizarUltimoPeriodoYPartidoConPenales(local: number, visitante: number) {
    await registrar.mutateAsync({ tipo_hito: "Fin_Periodo", numero_periodo: estado.periodo_abierto ?? undefined } as never);
    await registrar.mutateAsync({
      tipo_hito: "Fin_Partido",
      metodo_desempate: "Penales",
      penales_local: local,
      penales_visitante: visitante,
    } as never);
  }

  const esUltimoPeriodo = estado.cantidad_periodos != null && estado.periodo_abierto === estado.cantidad_periodos;

  let contenido: ReactNode;

  if (estado.partido_finalizado) {
    // Design Fase 2, Pass 2: estado de éxito explícito tras un cierre
    // forzado, no un badge genérico indistinguible de un cierre normal —
    // el propio Hito ya audita bracket/estado, esto solo lo hace visible.
    contenido = (
      <div className="cronometro__estado-final">
        <p className="badge badge--finalizado">Partido finalizado</p>
        {cierreForzado && !dentroDeVentanaDeshacer && (
          <p className="muted">
            Cerrado por "Fin de Partido forzado" — motivo: {MOTIVO_ETIQUETA[cierreForzado.motivo_cierre as MotivoCierre] ?? cierreForzado.motivo_cierre}
            {cierreForzado.motivo_cierre_detalle ? ` (${cierreForzado.motivo_cierre_detalle})` : ""}.
          </p>
        )}
      </div>
    );
  } else if (!estado.partido_iniciado) {
    contenido = mostrarInicio ? (
      <button
        type="button"
        className="cronometro__boton-iniciar"
        disabled={registrar.isPending}
        onClick={estado.tipo_cronometro === "Corrido" ? () => accion("Inicio_Partido") : iniciarPrimerTiempo}
      >
        ▶ Iniciar {estado.tipo_cronometro === "Corrido" ? "Partido" : nombrePeriodo(1)}
      </button>
    ) : (
      // El arranque lo maneja "Gestionar Partido" (H-10). Acá solo se explica
      // el estado, para que el cronómetro en 00:00 no parezca un bug.
      <p className="muted">El partido todavía no arrancó.</p>
    );
  } else if (estado.tipo_cronometro === "Periodos" && estado.periodo_abierto == null && !esUltimoPeriodoCerradoFinal(estado)) {
    // Entretiempo: el período recién terminado ya cerró, el siguiente no
    // arrancó todavía.
    const siguiente = estado.ultimo_periodo_cerrado + 1;
    contenido = (
      <div>
        <p className="cronometro__label">Entretiempo</p>
        <button type="button" disabled={registrar.isPending} onClick={() => accion("Inicio_Periodo", { numero_periodo: siguiente })}>
          ▶ Iniciar {nombrePeriodo(siguiente)}
        </button>
      </div>
    );
  } else if (eligiendoGanador) {
    contenido = (
      <div>
        <p className="cronometro__label">¿Quién ganó?</p>
        <label className="cronometro__radio">
          <input type="radio" checked={ganadorElegido === equipoLocalId} onChange={() => setGanadorElegido(equipoLocalId)} />
          {nombreLocal}
        </label>
        <label className="cronometro__radio">
          <input type="radio" checked={ganadorElegido === equipoVisitanteId} onChange={() => setGanadorElegido(equipoVisitanteId)} />
          {nombreVisitante}
        </label>
        {registrar.isError && <p className="error-text">{apiErrorMessage(registrar.error)}</p>}
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={() => setEligiendoGanador(false)}>
            Cancelar
          </button>
          <button
            type="button"
            disabled={ganadorElegido == null || registrar.isPending}
            onClick={() => accion("Fin_Partido", { ganador_corrido_id: ganadorElegido })}
          >
            Confirmar
          </button>
        </div>
      </div>
    );
  } else if (eligiendoDesempate) {
    // Desempate manual (Fase 0, Finding 1): el marcador de goles terminó
    // empatado en un partido de fase Eliminación — el sistema registra
    // QUIÉN avanza, no CÓMO (penales/tiempo extra/decisión arbitral),
    // mismo nivel de detalle que el resto de TRASPASOS.Motivo.
    contenido = (
      <div>
        <p className="cronometro__label">Empate en el marcador — ¿quién avanza?</p>
        <label className="cronometro__radio">
          <input type="radio" checked={desempateElegido === equipoLocalId} onChange={() => setDesempateElegido(equipoLocalId)} />
          {nombreLocal}
        </label>
        <label className="cronometro__radio">
          <input
            type="radio"
            checked={desempateElegido === equipoVisitanteId}
            onChange={() => setDesempateElegido(equipoVisitanteId)}
          />
          {nombreVisitante}
        </label>
        {registrar.isError && <p className="error-text">{apiErrorMessage(registrar.error)}</p>}
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={() => setEligiendoDesempate(false)}>
            Cancelar
          </button>
          <button
            type="button"
            disabled={desempateElegido == null || registrar.isPending}
            onClick={() => void finalizarUltimoPeriodoYPartidoConDesempate(desempateElegido as number)}
          >
            {registrar.isPending ? "Cerrando..." : "Confirmar y finalizar"}
          </button>
        </div>
      </div>
    );
  } else if (escapandoAManual) {
    // D-A1/D-D5: hoja de confirmación antes de saltar del flujo de
    // penales al radio manual — nombra lo que implica cerrar así, con un
    // confirmar de estilo destructivo (mismo criterio visual que el
    // cierre forzado, más abajo).
    contenido = (
      <div className="cierre-forzado-confirmar">
        <p className="cierre-forzado-confirmar__titulo">Cerrar sin la tanda de penales</p>
        <p className="muted">
          Este torneo define por penales. Si cerrás acá, elegís vos quién avanza y queda registrado así.
        </p>
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={() => setEscapandoAManual(false)}>
            Volver a la tanda
          </button>
          <button
            type="button"
            className="boton-cierre-forzado"
            onClick={() => {
              setEscapandoAManual(false);
              setEligiendoDesempate(true);
            }}
          >
            Elegir manualmente
          </button>
        </div>
      </div>
    );
  } else if (eligiendoPenales) {
    // Desempate de eliminatoria: tiempo extra y penales (D-D1/§9, D-D4,
    // D-D7, fase 2) — steppers con NOMBRE DE EQUIPO (nunca "Local"/
    // "Visitante": D-D4 — en una vuelta el encabezado muestra el GLOBAL,
    // que cruza localía). Confirmar deshabilitado mientras estén iguales
    // (una tanda no puede terminar empatada) — mensaje inline al empatar.
    const empatados = penalesLocal === penalesVisitante;
    const ganadorNombre = penalesLocal > penalesVisitante ? nombreLocal : nombreVisitante;
    contenido = (
      <div>
        <p className="cronometro__label">Tanda de penales</p>
        <div className="cronometro__penales-steppers">
          <label>
            {nombreLocal}
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={30}
              value={penalesLocal}
              onChange={(e) => setPenalesLocal(Math.max(0, Math.min(30, Number(e.target.value) || 0)))}
            />
          </label>
          <label>
            {nombreVisitante}
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={30}
              value={penalesVisitante}
              onChange={(e) => setPenalesVisitante(Math.max(0, Math.min(30, Number(e.target.value) || 0)))}
            />
          </label>
        </div>
        {empatados && <p className="muted">Una tanda de penales no puede terminar empatada.</p>}
        {!empatados && (
          <p className="muted">
            Penales {penalesLocal}-{penalesVisitante} — avanza {ganadorNombre}.
          </p>
        )}
        {registrar.isError && <p className="error-text">{apiErrorMessage(registrar.error)}</p>}
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={() => setEligiendoPenales(false)}>
            Cancelar
          </button>
          <button
            type="button"
            disabled={empatados || registrar.isPending}
            onClick={() => void finalizarUltimoPeriodoYPartidoConPenales(penalesLocal, penalesVisitante)}
          >
            {registrar.isPending ? "Cerrando..." : "Confirmar y finalizar"}
          </button>
        </div>
      </div>
    );
  } else {
    // Corriendo o pausado — período abierto (Periodos) o partido en
    // marcha (Corrido).
    const label = estado.tipo_cronometro === "Corrido" ? "Tiempo de partido" : nombrePeriodo(estado.periodo_abierto ?? 1);
    const puedeFinalizarPeriodos = estado.tipo_cronometro === "Periodos" && estado.acciones_permitidas.includes("Fin_Periodo");
    const puedeFinalizarPartido = estado.acciones_permitidas.includes("Fin_Partido");
    contenido = (
      <div>
        <p className="cronometro__label">{label}</p>
        <p className={`cronometro__tiempo ${estado.en_pausa ? "cronometro__tiempo--pausado" : ""}`}>
          {corriendo || estado.en_pausa ? "▶ " : ""}
          {formatearMMSS(elapsedMs)}
        </p>
        <div className="cronometro__acciones">
          {estado.en_pausa ? (
            <button type="button" className="cronometro__pausar" disabled={registrar.isPending} onClick={() => accion("Reanudacion")}>
              ▶ Reanudar
            </button>
          ) : (
            estado.acciones_permitidas.includes("Pausa") && (
              <button type="button" disabled={registrar.isPending} onClick={() => accion("Pausa")}>
                ⏸ Pausar
              </button>
            )
          )}
          {puedeFinalizarPeriodos && (
            <button
              type="button"
              disabled={registrar.isPending}
              onClick={() => {
                if (!esUltimoPeriodo) {
                  accion("Fin_Periodo", { numero_periodo: estado.periodo_abierto ?? undefined });
                } else if (requiereDesempate && metodoDesempateAplicable === "Penales_Directo") {
                  // D-D1 (fase 2): este torneo define por penales directos
                  // — el botón promueve la tanda en vez del radio manual.
                  setEligiendoPenales(true);
                } else if (requiereDesempate) {
                  // Fase 0 (Finding 1): el marcador está empatado y este
                  // partido es de fase Eliminación — el botón deshabilita
                  // ANTES del intento en vez de fallar después (Design
                  // review): pide el desempate en vez de finalizar directo.
                  setEligiendoDesempate(true);
                } else {
                  finalizarUltimoPeriodoYPartido();
                }
              }}
            >
              {esUltimoPeriodo
                ? requiereDesempate && metodoDesempateAplicable === "Penales_Directo"
                  ? "Ir a penales"
                  : "Fin del Partido"
                : `Fin ${label}`}
            </button>
          )}
          {/* D-A1/F8: las dos acciones quedan permitidas a propósito — "Ir
              a penales" es la primaria, esto es el escape secundario (con
              fricción, ver escapandoAManual más arriba), nunca escondido. */}
          {puedeFinalizarPeriodos && esUltimoPeriodo && requiereDesempate && metodoDesempateAplicable === "Penales_Directo" && (
            <button type="button" className="link-button" disabled={registrar.isPending} onClick={() => setEscapandoAManual(true)}>
              Finalizar por decisión (sin penales)
            </button>
          )}
          {estado.tipo_cronometro === "Corrido" && puedeFinalizarPartido && (
            <button type="button" disabled={registrar.isPending} onClick={() => setEligiendoGanador(true)}>
              Finalizar partido
            </button>
          )}
        </div>
      </div>
    );
  }

  // D-D8: chip de regla vigente. `metodoDesempateAplicable` (ya
  // snapshoteado al arrancar) manda; antes de Inicio_Partido se
  // previsualiza con la regla ACTUAL del torneo. Oculto si esto no es un
  // partido de Eliminación, o si ninguna de las dos fuentes resolvió nada.
  const reglaEfectiva = metodoDesempateAplicable ?? metodoDesempateEliminatoriaTorneo ?? null;
  const etiquetaRegla = esEliminacion ? etiquetaReglaDesempate(reglaEfectiva) : null;
  let chipRegla: string | null = null;
  if (etiquetaRegla) {
    chipRegla = etiquetaRegla;
    if (esVuelta && globalLocal != null && globalVisitante != null) {
      const consecuencia = consecuenciaCortaDesempate(reglaEfectiva);
      const empatadoEnGlobal = globalLocal === globalVisitante;
      chipRegla = `Global ${globalLocal}-${globalVisitante}${
        empatadoEnGlobal && consecuencia ? ` — si termina así, ${consecuencia}` : ""
      } · ${etiquetaRegla}`;
    }
  }

  return (
    <section className="card cronometro">
      {/* Área 4 (T17/T25): banner de deshacer — SIEMPRE lo primero que se
          ve mientras la ventana está abierta (Design Fase 2, Pass 3:
          alto contraste, countdown visible, `aria-live="assertive"` para
          que un lector de pantalla no pueda "perderse" el estado más
          crítico de seguridad de toda la feature, ver Pass 6). El cierre
          YA ES FIRME desde el insert (Eng Fase 3) — este banner comunica
          una ventana de gracia real del servidor, no una cuenta regresiva
          de la que dependa que el partido se cierre. */}
      {dentroDeVentanaDeshacer && (
        <div className="banner-deshacer-cierre" role="alert" aria-live="assertive">
          <p>
            Partido cerrado por "Fin de Partido forzado"
            {cierreForzado?.motivo_cierre && ` — ${MOTIVO_ETIQUETA[cierreForzado.motivo_cierre]}`}
            {cierreForzado?.motivo_cierre_detalle ? ` (${cierreForzado.motivo_cierre_detalle})` : ""}.
            Podés deshacerlo en los próximos {segundosRestantes}s.
          </p>
          {deshacer.isError && <p className="error-text">{apiErrorMessage(deshacer.error)}</p>}
          <button type="button" disabled={deshacer.isPending} onClick={() => deshacer.mutate()}>
            {deshacer.isPending ? "Deshaciendo..." : "DESHACER"}
          </button>
        </div>
      )}

      {/* D-D8: chip de regla vigente — persistente, para que el operador
          sepa qué pasa al final del partido sin esperar a que un botón le
          cambie de texto en el minuto 90. `metodoDesempateAplicable` (ya
          snapshoteado) manda; antes de Inicio_Partido se previsualiza con
          la regla ACTUAL del torneo (§11-bis: "siempre hay regla", puede
          seguir cambiando hasta que arranque, D6/§8). Oculto entero si no
          es un partido de Eliminación o si no hay ninguna regla que leer
          — nunca un valor inventado. */}
      {chipRegla && (
        <p className="cronometro__chip-regla">
          {chipRegla}
        </p>
      )}

      {registrar.isError && !eligiendoGanador && !confirmandoForzado && <p className="error-text">{apiErrorMessage(registrar.error)}</p>}
      {contenido}

      {/* Área 4 (T6): override global — botón fijo, visualmente separado
          del flujo normal de cierre (Design Fase 2, Pass 1: "descubribilidad
          de emergencia > prolijidad visual"), habilitado en CUALQUIER
          `acciones_permitidas` mientras el partido esté iniciado y no
          finalizado (a diferencia de "Fin del Partido"/"Finalizar partido"
          de arriba, que respetan el gate normal). */}
      {estado.partido_iniciado && !estado.partido_finalizado && !dentroDeVentanaDeshacer && (
        confirmandoForzado ? (
          <div className="cierre-forzado-confirmar">
            <p className="cierre-forzado-confirmar__titulo">Finalizar partido (forzado) — confirmá el motivo</p>
            <div className="tap-grid" role="radiogroup" aria-label="Motivo del cierre forzado">
              {MOTIVOS_CIERRE.map((m) => (
                <button
                  key={m.valor}
                  type="button"
                  role="radio"
                  aria-checked={motivoCierre === m.valor}
                  className={`tap-button${motivoCierre === m.valor ? " tap-button--activo" : ""}`}
                  onClick={() => setMotivoCierre(m.valor)}
                >
                  {m.etiqueta}
                </button>
              ))}
            </div>
            {motivoCierre === "Otro" && (
              <label>
                Detalle
                <input
                  type="text"
                  maxLength={200}
                  value={motivoDetalle}
                  onChange={(e) => setMotivoDetalle(e.target.value)}
                  autoFocus
                />
              </label>
            )}
            {registrar.isError && <p className="error-text">{apiErrorMessage(registrar.error)}</p>}
            <div className="resource-form__actions">
              <button type="button" className="link-button" onClick={() => { setConfirmandoForzado(false); setMotivoCierre(null); setMotivoDetalle(""); }}>
                Cancelar
              </button>
              <button
                type="button"
                disabled={
                  motivoCierre == null ||
                  (motivoCierre === "Otro" && motivoDetalle.trim() === "") ||
                  registrar.isPending
                }
                onClick={() =>
                  registrar.mutate({
                    tipo_hito: "Fin_Partido",
                    forzado: true,
                    motivo_cierre: motivoCierre as MotivoCierre,
                    ...(motivoCierre === "Otro" ? { motivo_cierre_detalle: motivoDetalle.trim() } : {}),
                  } as never, {
                    onSuccess: () => { setConfirmandoForzado(false); setMotivoCierre(null); setMotivoDetalle(""); },
                  })
                }
              >
                Confirmar cierre forzado
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="boton-cierre-forzado"
            aria-label="Finalizar partido (forzado) — cierre de emergencia, distinto del cierre normal"
            onClick={() => setConfirmandoForzado(true)}
          >
            Finalizar partido (forzado)
          </button>
        )
      )}

      <button type="button" className="link-button" onClick={() => setHistorialAbierto((v) => !v)}>
        {historialAbierto ? "▲ Ocultar historial de hitos" : "▼ Historial de hitos"}
      </button>
      {historialAbierto && (
        <HistorialHitos hitos={estado.hitos} onCorregir={(hitoId, minuto) => corregirHito.mutate({ hitoId, minuto })} />
      )}
    </section>
  );
}

/** El último período ya cerró Y es el último configurado — no hay
 * entretiempo que mostrar, el botón pasa a decir "Fin del Partido" en la
 * rama de "corriendo" (mismo botón, label calculado — ver el plan). */
function esUltimoPeriodoCerradoFinal(estado: EstadoCronometro): boolean {
  return estado.cantidad_periodos != null && estado.ultimo_periodo_cerrado >= estado.cantidad_periodos;
}

const NOMBRE_HITO: Record<TipoHito, string> = {
  Inicio_Partido: "Inicio del partido",
  Inicio_Periodo: "Inicio de período",
  Fin_Periodo: "Fin de período",
  Pausa: "Pausa",
  Reanudacion: "Reanudación",
  Fin_Partido: "Fin del partido",
};

/** Panel colapsable de hitos, con corrección de minuto (Flujo 5: "un
 * ícono de lápiz junto al hito, no en el cronómetro principal, para no
 * invitar a tocarlo por accidente"). */
function HistorialHitos(props: { hitos: HitoRow[]; onCorregir: (hitoId: number, minuto: number) => void }) {
  const [editando, setEditando] = useState<number | null>(null);
  const [minuto, setMinuto] = useState("");

  return (
    <ul className="hito-historial">
      {[...props.hitos].reverse().map((h) => (
        <li key={h.id}>
          <span>
            {NOMBRE_HITO[h.tipo_hito]}
            {h.numero_periodo != null && ` (${nombrePeriodo(h.numero_periodo)})`}
          </span>
          <span className="muted">{new Date(h.timestamp_real).toLocaleTimeString("es-AR")}</span>
          {editando === h.id ? (
            <>
              <input
                type="number"
                aria-label="Corregir minuto"
                value={minuto}
                onChange={(e) => setMinuto(e.target.value)}
                style={{ width: "4rem" }}
                autoFocus
              />
              <button
                type="button"
                onClick={() => {
                  if (minuto !== "") props.onCorregir(h.id, Number(minuto));
                  setEditando(null);
                }}
              >
                Guardar
              </button>
              <button type="button" className="link-button" onClick={() => setEditando(null)}>
                Cancelar
              </button>
            </>
          ) : (
            <>
              <span>{h.minuto_reloj != null ? `${h.minuto_reloj}'` : "—"}</span>
              <button
                type="button"
                className="link-button"
                aria-label="Corregir minuto de este hito"
                onClick={() => {
                  setEditando(h.id);
                  setMinuto(h.minuto_reloj != null ? String(h.minuto_reloj) : "");
                }}
              >
                ✏️
              </button>
            </>
          )}
        </li>
      ))}
      {props.hitos.length === 0 && <p className="muted">Sin hitos todavía.</p>}
    </ul>
  );
}
