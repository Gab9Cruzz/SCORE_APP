import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import {
  deriveEnCancha,
  deriveHistorialElegibilidad,
  deriveTitularSuplente,
  TIPO_ICONO,
  type PlantillaJugador,
  type TipoEvento,
} from "../../components/eventos";
import {
  contarSlots,
  descartarSlotYReconciliar,
  reconciliarSlots,
  resolverTipoYEquipoDeSlot,
  type SlotGol,
} from "../../lib/reconciliarSlots";

/** Tipo de evento que el Quick Action Bar puede agregar (goles-por-marcador-
 * slots-plan.md, punto 2 del pedido) — Gol/Autogol NO están acá: esos se
 * cargan exclusivamente vía los slots del marcador (punto 1), nunca por
 * este camino, para no tener 2 formas distintas de registrar un gol. */
type TipoQuickBar = "Tarjeta Amarilla" | "Tarjeta Roja" | "Cambio";

interface OtroEventoLocal {
  id: string;
  tipo: TipoQuickBar;
  equipoId: number;
  jugadorId: number;
  jugadorIdEntra: number | null;
  minuto: string;
}

interface EventoTimelineResuelto {
  id: string;
  tipo: TipoEvento;
  equipoId: number;
  jugadorId: number;
  jugadorIdEntra: number | null;
  minuto: number;
  /** control-mesa-reactividad-playoffs-plan.md, Fase 3 §3/§6 (T6):
   * SOLO true para la previsualización client-side de la roja automática
   * por doble amarilla — nunca se agrega a `otrosEventos`, nunca se manda
   * al servidor (el servidor es el único que la inserta de verdad, ver
   * `reglas_tarjetas.py`). Distingue visualmente "esto lo cargó el
   * operador" de "esto lo infirió la app", y bloquea el botón "Quitar"
   * (no hay un evento propio que quitar — se quita sacando una de las 2
   * amarillas). */
  esAuto?: boolean;
}

/** "Cargar resultado directo" (control-mesa-centralizacion-fixture-plan.md,
 * Sección 5, Alternativa A) — cierra un partido 'Programado' de una sola
 * vez (goles/tarjetas/cambios + inicio y fin), sin pasar por el cronómetro
 * en vivo ni exponer `MesaPanel`. Carga TODOS los eventos en memoria y
 * los manda juntos a `POST /resultado-directo` — el backend orquesta
 * Inicio_Partido + N eventos + Fin_Partido en una sola transacción
 * atómica (PartidoService.registrar_resultado_directo).
 *
 * Reescrito en goles-por-marcador-slots-plan.md (reversión de D1, Gate
 * Final 2026-09-08 → 2026-09-09): el marcador genera slots de gol
 * obligatorios (jugador+minuto cada uno), una Quick Action Bar carga
 * tarjetas/cambios, y el timeline se muestra ascendente y reactivo. El
 * filtrado titular/suplente del Cambio degrada con gracia (D4: este modal
 * sigue sirviendo partidos sin convocatoria guardada) — ver
 * `sinConvocatoria` abajo. */
export function ModalResultadoDirecto(props: {
  partido: { id: number; equipos_id_local: number; equipos_id_visitante: number };
  nombreEquipo: Map<number, string>;
  onClose: () => void;
  onGuardado: () => void;
}) {
  const { partido, nombreEquipo, onClose, onGuardado } = props;
  const nombreLocal = nombreEquipo.get(partido.equipos_id_local) ?? `Equipo #${partido.equipos_id_local}`;
  const nombreVisitante = nombreEquipo.get(partido.equipos_id_visitante) ?? `Equipo #${partido.equipos_id_visitante}`;

  // tipo_cronometro decide si hace falta pedir un ganador manual (torneos
  // 'Corrido', sin marcador de goles) — mismo endpoint que ya usa el
  // cronómetro en vivo, no hace falta uno nuevo.
  const cronometroQuery = useQuery({
    queryKey: ["cronometro", partido.id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/cronometro", {
        params: { path: { partido_id: partido.id } },
      });
      if (error) throw error;
      return data;
    },
  });
  const esCorrido = cronometroQuery.data?.tipo_cronometro === "Corrido";

  const plantillaLocalQuery = useQuery({
    queryKey: ["plantilla", partido.equipos_id_local],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: partido.equipos_id_local } },
      });
      if (error) throw error;
      return data;
    },
  });
  const plantillaVisitanteQuery = useQuery({
    queryKey: ["plantilla", partido.equipos_id_visitante],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: partido.equipos_id_visitante } },
      });
      if (error) throw error;
      return data;
    },
  });
  const eventosCatalogoQuery = useQuery({
    queryKey: ["eventos-catalogo"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eventos", {});
      if (error) throw error;
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
  const eventoIdPorNombre = useMemo(
    () => new Map((eventosCatalogoQuery.data ?? []).map((e) => [e.nombre, e.id])),
    [eventosCatalogoQuery.data],
  );
  const eventoNombrePorId = useMemo(
    () => new Map((eventosCatalogoQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [eventosCatalogoQuery.data],
  );

  // goles-por-marcador-slots-plan.md, Fase 1 (Premisa D4-alcance): esta
  // convocatoria puede no existir — D4 (`partido.py:170-179`) sigue
  // vigente, este modal sirve partidos sin alineación registrada. Cuando
  // no hay una, `deriveTitularSuplente` devuelve ambos sets vacíos y todo
  // acá degrada con gracia a la plantilla completa (mismo comportamiento
  // que antes de este plan).
  const convocadosQuery = useQuery({
    queryKey: ["convocados", partido.id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/convocados", {
        params: { path: { partido_id: partido.id } },
      });
      if (error) throw error;
      return data as { jugador_perfil_id: number; titular: boolean }[];
    },
  });
  const titularesPerfilIds = useMemo(
    () => new Set((convocadosQuery.data ?? []).filter((c) => c.titular).map((c) => c.jugador_perfil_id)),
    [convocadosQuery.data],
  );
  // control-mesa-reactividad-playoffs-plan.md, Fase 3 §2: TODAS las filas
  // convocadas (titular+suplente), no solo las titulares — deriveTitularSuplente
  // las necesita para distinguir "convocado como suplente" de "nunca
  // convocado a este partido" (el bug de filtrado estricto de suplentes).
  const convocadosPerfilIds = useMemo(
    () => new Set((convocadosQuery.data ?? []).map((c) => c.jugador_perfil_id)),
    [convocadosQuery.data],
  );
  const plantillaCombinada: PlantillaJugador[] = useMemo(
    () => [...(plantillaLocalQuery.data ?? []), ...(plantillaVisitanteQuery.data ?? [])],
    [plantillaLocalQuery.data, plantillaVisitanteQuery.data],
  );
  const { titulares: titularesJugadorIds, suplentes: suplentesJugadorIds } = useMemo(
    () => deriveTitularSuplente(convocadosPerfilIds, titularesPerfilIds, plantillaCombinada),
    [convocadosPerfilIds, titularesPerfilIds, plantillaCombinada],
  );
  const sinConvocatoria = convocadosPerfilIds.size === 0;
  const equipoIdDelJugador = useMemo(() => {
    const mapa = new Map(plantillaCombinada.map((j) => [j.jugador_id, j.equipo_id]));
    return (jugadorId: number) => mapa.get(jugadorId);
  }, [plantillaCombinada]);

  // --- Slots de gol (punto 1 del pedido) -----------------------------------
  const [slots, setSlots] = useState<SlotGol[]>([]);
  const [pendienteConfirmar, setPendienteConfirmar] = useState<{ lado: "local" | "visitante"; candidatos: SlotGol[] } | null>(null);
  const [candidatoElegido, setCandidatoElegido] = useState<string | null>(null);
  const idCounter = useRef(0);
  const crearId = () => {
    idCounter.current += 1;
    return `slot-${idCounter.current}`;
  };
  // Autofocus (0D, expansión aceptada): el slot recién agregado por el
  // input de marcador recibe el foco, para que cargar varios goles seguidos
  // no requiera tocar el mouse entre uno y el siguiente. Un ref (no
  // estado) para no disparar un render extra solo para consumir esta señal
  // de una sola vez — se resuelve en el `ref` callback del `<select>`, en
  // el momento en que el elemento nuevo se monta.
  const focoSlotIdRef = useRef<string | null>(null);
  const selectRefs = useRef<Map<string, HTMLSelectElement>>(new Map());

  const marcadorLocal = contarSlots(slots, "local");
  const marcadorVisitante = contarSlots(slots, "visitante");
  const slotsLlenosLocal = slots.filter((s) => s.lado === "local" && s.jugadorId !== null && s.minuto !== "").length;
  const slotsLlenosVisitante = slots.filter((s) => s.lado === "visitante" && s.jugadorId !== null && s.minuto !== "").length;

  // El objetivo de marcador pedido queda en un ref (no en el estado del
  // modal) porque `reconciliarSlots` ya lo devolvió una vez con
  // `pendienteConfirmar` — no hace falta pedirle al operador que lo
  // vuelva a escribir, y evita otro round-trip de estado.
  const marcadorLocalObjetivoRef = useRef(0);
  const marcadorVisitanteObjetivoRef = useRef(0);

  function cambiarMarcador(lado: "local" | "visitante", valor: string) {
    const n = Number(valor);
    if (valor === "" || !Number.isInteger(n) || n < 0) return;
    const resultado = reconciliarSlots(slots, lado, n, crearId);
    if (resultado.pendienteConfirmar) {
      // Se guarda el objetivo pedido (no hace falta pedírselo de nuevo al
      // operador cuando confirme cuál slot descartar).
      if (lado === "local") marcadorLocalObjetivoRef.current = n;
      else marcadorVisitanteObjetivoRef.current = n;
      setPendienteConfirmar(resultado.pendienteConfirmar);
      setCandidatoElegido(resultado.pendienteConfirmar.candidatos.at(-1)?.id ?? null);
      return;
    }
    const idsPrevios = new Set(slots.map((s) => s.id));
    setSlots(resultado.slots);
    const nuevo = resultado.slots.find((s) => !idsPrevios.has(s.id));
    if (nuevo) focoSlotIdRef.current = nuevo.id;
  }

  function confirmarDescarte() {
    if (!pendienteConfirmar || candidatoElegido == null) return;
    const marcadorObjetivo = pendienteConfirmar.lado === "local" ? marcadorLocalObjetivoRef.current : marcadorVisitanteObjetivoRef.current;
    const resultado = descartarSlotYReconciliar(slots, candidatoElegido, pendienteConfirmar.lado, marcadorObjetivo, crearId);
    setSlots(resultado.slots);
    // Puede hacer falta descartar más de 1 (bajar el marcador en 2 de una
    // vez) — si `reconciliarSlots` todavía pide confirmación, se sigue
    // encadenando; si no, se cierra el modal.
    setPendienteConfirmar(resultado.pendienteConfirmar);
    setCandidatoElegido(resultado.pendienteConfirmar?.candidatos.at(-1)?.id ?? null);
  }

  function cancelarReconciliacion() {
    // Escape hatch (Design Fase 2, Pass 3): revierte al marcador anterior
    // — CERO slots se tocan. Como el input está controlado por
    // `contarSlots(slots, lado)`, simplemente cerrar el modal ya lo hace.
    setPendienteConfirmar(null);
    setCandidatoElegido(null);
  }

  function actualizarSlot(id: string, cambios: Partial<Pick<SlotGol, "jugadorId" | "minuto">>) {
    setSlots((prev) => prev.map((s) => (s.id === id ? { ...s, ...cambios } : s)));
  }

  // --- Quick Action Bar (punto 2 del pedido) -------------------------------
  const [otrosEventos, setOtrosEventos] = useState<OtroEventoLocal[]>([]);
  const [accionQuickBar, setAccionQuickBar] = useState<TipoQuickBar | null>(null);
  const [qbEquipoId, setQbEquipoId] = useState<number | null>(null);
  const [qbJugadorId, setQbJugadorId] = useState<number | null>(null);
  const [qbJugadorIdEntra, setQbJugadorIdEntra] = useState<number | null>(null);
  const [qbMinuto, setQbMinuto] = useState("");

  function resetQuickBar() {
    setAccionQuickBar(null);
    setQbEquipoId(null);
    setQbJugadorId(null);
    setQbJugadorIdEntra(null);
    setQbMinuto("");
  }

  const plantillaQb = qbEquipoId === partido.equipos_id_local ? (plantillaLocalQuery.data ?? []) : (plantillaVisitanteQuery.data ?? []);

  // Historial de ESTE batch local (todavía sin guardar) — mismo helper
  // compartido que Modo en Vivo, extendido acá con los eventos locales en
  // vez de `eventosRegistrados` del servidor (0E, Fase 1: para un partido
  // 'Programado' la timeline del servidor está vacía por definición — el
  // historial que importa es el que se está construyendo en memoria).
  //
  // TODOS los otrosEventos (no solo Cambio, corrección Fase 3 §1 del plan
  // control-mesa-reactividad-playoffs-plan.md): deriveHistorialElegibilidad
  // ya distingue "Tarjeta Roja" de "Cambio" internamente (ver su
  // implementación) — filtrar acá a solo Cambio antes de llamarla dejaba
  // afuera las expulsiones por roja cargadas en este mismo batch,
  // inconsistente con MesaPanel.tsx (que le pasa TODOS los eventos
  // registrados sin filtrar).
  const { salidosOExpulsados, yaEntraron } = useMemo(
    () =>
      deriveHistorialElegibilidad(
        otrosEventos.map((e) => ({
          jugador_id: e.jugadorId,
          jugador_id_entra: e.jugadorIdEntra,
          eventos_id: eventoIdPorNombre.get(e.tipo) ?? -1,
        })),
        eventoNombrePorId,
      ),
    [otrosEventos, eventoIdPorNombre, eventoNombrePorId],
  );

  // "Estado mutante en cambios" (Fase 3 §1): quién está en cancha AHORA,
  // incluyendo suplentes que ya entraron en un Cambio anterior de este
  // mismo batch — sin esto, un suplente recién ingresado no podía volver a
  // salir en un Cambio posterior de la misma carga.
  const enCanchaJugadorIds = useMemo(
    () => deriveEnCancha(titularesJugadorIds, salidosOExpulsados, yaEntraron),
    [titularesJugadorIds, salidosOExpulsados, yaEntraron],
  );

  const qbCandidatosSale =
    accionQuickBar === "Cambio"
      ? plantillaQb.filter((j) => (sinConvocatoria || enCanchaJugadorIds.has(j.jugador_id)) && !salidosOExpulsados.has(j.jugador_id))
      : // Cherry-pick auto-aprobado (Fase 1, 0D-1): mismo guard de
        // ya-expulsado que Cambio — un jugador ya expulsado/salido en este
        // batch no debería poder recibir OTRA tarjeta.
        plantillaQb.filter((j) => !salidosOExpulsados.has(j.jugador_id));
  // `!yaEntraron.has(...)` es la validación temprana del batch local (0D,
  // expansión aceptada): un jugador que ya entró en OTRO Cambio de esta
  // misma carga nunca aparece acá como opción — no hace falta un mensaje
  // de error después de elegirlo, porque no se lo puede elegir dos veces.
  const qbCandidatosEntra = plantillaQb.filter(
    (j) =>
      j.jugador_id !== qbJugadorId &&
      !salidosOExpulsados.has(j.jugador_id) &&
      !yaEntraron.has(j.jugador_id) &&
      (sinConvocatoria || suplentesJugadorIds.has(j.jugador_id)),
  );
  function agregarOtroEvento() {
    if (accionQuickBar == null || qbEquipoId == null || qbJugadorId == null || qbMinuto === "") return;
    if (accionQuickBar === "Cambio" && qbJugadorIdEntra == null) return;
    setOtrosEventos((prev) => [
      ...prev,
      {
        id: crearId(),
        tipo: accionQuickBar,
        equipoId: qbEquipoId,
        jugadorId: qbJugadorId,
        jugadorIdEntra: accionQuickBar === "Cambio" ? qbJugadorIdEntra : null,
        minuto: qbMinuto,
      },
    ]);
    resetQuickBar();
  }

  // --- Timeline (punto 4 del pedido) ---------------------------------------
  // Ascendente (Gate Final, Alternativa D — el usuario eligió esto
  // explícitamente: "el orden siempre debe ser de menor a mayor"), reactivo
  // a cada inserción (se recalcula en cada render, no hay estado de orden
  // aparte que pueda desincronizarse).
  // Previsualización de la roja automática por doble amarilla (Fase 3 §3,
  // §6/T6) — SOLO para render, nunca se agrega a `otrosEventos`: el
  // servidor es el único que inserta el evento real (`reglas_tarjetas.py`).
  // Insertarla acá también duplicaría la roja (el batch se procesa en el
  // ORDEN de envío, no por minuto — ver el comentario largo en
  // reglas_tarjetas.py). Dedup client-side simplificado y más conservador
  // que el del servidor: si YA hay una Tarjeta Roja para ese jugador en
  // `otrosEventos` (en cualquier posición, no solo antes), no se previsualiza
  // ninguna — evita mostrarle al operador una "auto" fantasma cuando ya
  // cargó la suya a mano.
  const previewsRojaAuto: EventoTimelineResuelto[] = useMemo(() => {
    const amarillasPorJugador = new Map<number, OtroEventoLocal[]>();
    const jugadoresConRojaManual = new Set<number>();
    for (const e of otrosEventos) {
      if (e.tipo === "Tarjeta Roja") jugadoresConRojaManual.add(e.jugadorId);
      if (e.tipo === "Tarjeta Amarilla") {
        const lista = amarillasPorJugador.get(e.jugadorId) ?? [];
        lista.push(e);
        amarillasPorJugador.set(e.jugadorId, lista);
      }
    }
    const previews: EventoTimelineResuelto[] = [];
    for (const [jugadorId, amarillas] of amarillasPorJugador) {
      if (amarillas.length < 2 || jugadoresConRojaManual.has(jugadorId)) continue;
      const segunda = amarillas[1]; // orden de carga — mismo criterio que el servidor
      previews.push({
        id: `auto-roja-${jugadorId}`,
        tipo: "Tarjeta Roja",
        equipoId: segunda.equipoId,
        jugadorId,
        jugadorIdEntra: null,
        minuto: Number(segunda.minuto) || 0,
        esAuto: true,
      });
    }
    return previews;
  }, [otrosEventos]);

  const eventosTimeline: EventoTimelineResuelto[] = useMemo(() => {
    const deSlots: EventoTimelineResuelto[] = slots
      .filter((s) => s.jugadorId !== null && s.minuto !== "")
      .map((s) => {
        const resuelto = resolverTipoYEquipoDeSlot(s, partido.equipos_id_local, partido.equipos_id_visitante, equipoIdDelJugador);
        return {
          id: s.id,
          tipo: resuelto!.tipo,
          equipoId: resuelto!.equipoId,
          jugadorId: s.jugadorId as number,
          jugadorIdEntra: null,
          minuto: Number(s.minuto),
        };
      });
    const deOtros: EventoTimelineResuelto[] = otrosEventos.map((e) => ({
      id: e.id,
      tipo: e.tipo,
      equipoId: e.equipoId,
      jugadorId: e.jugadorId,
      jugadorIdEntra: e.jugadorIdEntra,
      minuto: Number(e.minuto),
    }));
    return [...deSlots, ...deOtros, ...previewsRojaAuto].sort((a, b) => a.minuto - b.minuto);
  }, [slots, otrosEventos, previewsRojaAuto, partido.equipos_id_local, partido.equipos_id_visitante, equipoIdDelJugador]);

  // Fase 1/2: nombre de jugador en el timeline — antes solo mostraba
  // ícono+equipo+minuto, nunca el jugador (gap de verificación real, no
  // cosmético: es el último punto de chequeo antes de un guardado que
  // cierra el partido).
  const jugadorPorId = useMemo(() => new Map(plantillaCombinada.map((j) => [j.jugador_id, j])), [plantillaCombinada]);
  function nombreJugadorConDorsal(jugadorId: number): string {
    const j = jugadorPorId.get(jugadorId);
    if (!j) return `#${jugadorId}`;
    return `${j.dorsal != null ? `#${j.dorsal} ` : ""}${j.jugador}`;
  }

  const [ganadorCorridoId, setGanadorCorridoId] = useState<number | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const eventosSlots = slots.map((s) => {
        const resuelto = resolverTipoYEquipoDeSlot(s, partido.equipos_id_local, partido.equipos_id_visitante, equipoIdDelJugador)!;
        return {
          jugador_id: s.jugadorId as number,
          equipo_id: resuelto.equipoId,
          eventos_id: eventoIdPorNombre.get(resuelto.tipo) as number,
          jugador_id_entra: null,
          minuto: Number(s.minuto),
        };
      });
      const eventosOtros = otrosEventos.map((e) => ({
        jugador_id: e.jugadorId,
        equipo_id: e.equipoId,
        eventos_id: eventoIdPorNombre.get(e.tipo) as number,
        jugador_id_entra: e.jugadorIdEntra,
        minuto: Number(e.minuto),
      }));
      const body = {
        eventos: [...eventosSlots, ...eventosOtros],
        ganador_corrido_id: esCorrido ? ganadorCorridoId : undefined,
      };
      const { data, error } = await api.POST("/api/v1/partidos/{partido_id}/resultado-directo", {
        params: { path: { partido_id: partido.id } },
        body,
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: onGuardado,
  });

  const todosLosSlotsCompletos = slots.every((s) => s.jugadorId !== null && s.minuto !== "");
  const puedeGuardar = todosLosSlotsCompletos && (!esCorrido || ganadorCorridoId !== null) && pendienteConfirmar === null;

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-label={`Cargar resultado directo — ${nombreLocal} vs ${nombreVisitante}`}
    >
      <div className="modal-panel" style={{ maxWidth: 640 }}>
        <h2>Cargar resultado directo</h2>
        <p className="muted">
          {nombreLocal} vs {nombreVisitante} — cierra el partido sin usar el cronómetro en vivo.
        </p>

        {/* Zona primaria: marcador. Autofocus en el primer input (Design
            Fase 2, Pass 1/3 — "confianza, dato que ya sabe"). */}
        <div className="marcador-input-fila">
          <span>{nombreLocal}</span>
          <input
            type="number"
            min={0}
            max={99}
            autoFocus
            aria-label={`Goles ${nombreLocal}`}
            value={marcadorLocal}
            onChange={(e) => cambiarMarcador("local", e.target.value)}
          />
          <span>—</span>
          <input
            type="number"
            min={0}
            max={99}
            aria-label={`Goles ${nombreVisitante}`}
            value={marcadorVisitante}
            onChange={(e) => cambiarMarcador("visitante", e.target.value)}
          />
          <span>{nombreVisitante}</span>
        </div>
        {slots.length > 0 && (
          <p className="muted marcador-contador-parcial">
            Goles cargados: {slotsLlenosLocal} de {marcadorLocal} ({nombreLocal}) · {slotsLlenosVisitante} de {marcadorVisitante} (
            {nombreVisitante})
          </p>
        )}

        {/* Zona secundaria: slots de gol, 2 columnas. */}
        {slots.length > 0 && (
          <div className="slots-columnas">
            {(
              [
                ["local", nombreLocal, partido.equipos_id_local] as const,
                ["visitante", nombreVisitante, partido.equipos_id_visitante] as const,
              ]
            ).map(([lado, nombre]) => (
              <div key={lado}>
                <h3>{nombre}</h3>
                <ul className="slots-lista">
                  {slots
                    .filter((s) => s.lado === lado)
                    .map((s, i) => (
                      <li key={s.id} className="slot-gol-fila">
                        <span aria-hidden="true">⚽</span>
                        <select
                          ref={(el) => {
                            if (el) {
                              selectRefs.current.set(s.id, el);
                              if (focoSlotIdRef.current === s.id) {
                                el.focus();
                                focoSlotIdRef.current = null;
                              }
                            } else {
                              selectRefs.current.delete(s.id);
                            }
                          }}
                          aria-label={`Goleador, ${nombre} #${i + 1}`}
                          value={s.jugadorId ?? ""}
                          onChange={(e) => actualizarSlot(s.id, { jugadorId: e.target.value ? Number(e.target.value) : null })}
                        >
                          <option value="">Elegir jugador...</option>
                          <optgroup label={nombreLocal}>
                            {(plantillaLocalQuery.data ?? []).map((j) => (
                              <option key={j.jugador_id} value={j.jugador_id}>
                                {j.dorsal ? `#${j.dorsal} ` : ""}{j.jugador}
                              </option>
                            ))}
                          </optgroup>
                          <optgroup label={nombreVisitante}>
                            {(plantillaVisitanteQuery.data ?? []).map((j) => (
                              <option key={j.jugador_id} value={j.jugador_id}>
                                {j.dorsal ? `#${j.dorsal} ` : ""}{j.jugador}
                              </option>
                            ))}
                          </optgroup>
                        </select>
                        <input
                          type="number"
                          min={0}
                          max={130}
                          aria-label={`Minuto, ${nombre} #${i + 1}`}
                          value={s.minuto}
                          onChange={(e) => actualizarSlot(s.id, { minuto: e.target.value })}
                        />
                        {s.jugadorId !== null && s.minuto !== "" && <span className="slot-gol-fila__check">✓</span>}
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {/* Modal de reconciliación (Design Fase 2, Pass 3) — nunca un
            borrado silencioso: sugiere el más reciente, siempre con
            escape hatch. */}
        {pendienteConfirmar && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-reconciliacion-titulo">
            <div className="modal-panel">
              <h2 id="modal-reconciliacion-titulo">
                Bajaste el marcador — hay {pendienteConfirmar.candidatos.length} goles cargados
              </h2>
              <p className="muted">¿Cuál descartás?</p>
              <div className="modal-panel__checklist">
                {pendienteConfirmar.candidatos.map((c) => {
                  const jugador = plantillaCombinada.find((j) => j.jugador_id === c.jugadorId);
                  return (
                    <label key={c.id} className="modal-panel__equipo-fila">
                      <input
                        type="radio"
                        name="candidato-descartar"
                        checked={candidatoElegido === c.id}
                        onChange={() => setCandidatoElegido(c.id)}
                      />
                      {jugador?.dorsal ? `#${jugador.dorsal} ` : ""}
                      {jugador?.jugador ?? `#${c.jugadorId}`} — min {c.minuto}
                    </label>
                  );
                })}
              </div>
              <div className="resource-form__actions">
                <button type="button" className="link-button" onClick={cancelarReconciliacion}>
                  Cancelar — mantener marcador anterior
                </button>
                <button type="button" disabled={candidatoElegido == null} onClick={confirmarDescarte}>
                  Descartar seleccionado
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Zona terciaria: Quick Action Bar. */}
        <section className="card">
          <h2>Eventos adicionales</h2>
          {sinConvocatoria && (
            <p className="banner-info-persistente" aria-live="polite">
              Sin convocatoria guardada para este partido — no se puede distinguir titular de suplente. Mostrando el
              plantel completo.
            </p>
          )}
          {!accionQuickBar && (
            <div className="tap-grid">
              {(["Tarjeta Amarilla", "Tarjeta Roja", "Cambio"] as TipoQuickBar[]).map((t) => (
                <button key={t} type="button" className="tap-button" onClick={() => setAccionQuickBar(t)}>
                  <span className="tap-button__icon">{TIPO_ICONO[t]}</span>
                  {t}
                </button>
              ))}
            </div>
          )}
          {accionQuickBar && (
            <div className="resource-form">
              <label>
                Equipo
                <select
                  value={qbEquipoId ?? ""}
                  onChange={(e) => {
                    setQbEquipoId(e.target.value ? Number(e.target.value) : null);
                    setQbJugadorId(null);
                    setQbJugadorIdEntra(null);
                  }}
                >
                  <option value="">Elegir...</option>
                  <option value={partido.equipos_id_local}>{nombreLocal}</option>
                  <option value={partido.equipos_id_visitante}>{nombreVisitante}</option>
                </select>
              </label>
              {qbEquipoId != null && (
                <label>
                  {accionQuickBar === "Cambio" ? "Sale (en cancha)" : "Jugador"}
                  <select value={qbJugadorId ?? ""} onChange={(e) => setQbJugadorId(e.target.value ? Number(e.target.value) : null)}>
                    <option value="">Elegir...</option>
                    {qbCandidatosSale.map((j) => (
                      <option key={j.jugador_id} value={j.jugador_id}>
                        {j.dorsal ? `#${j.dorsal} ` : ""}
                        {j.jugador}
                        {sinConvocatoria && accionQuickBar === "Cambio" ? " (sin datos de alineación)" : ""}
                      </option>
                    ))}
                  </select>
                  {accionQuickBar === "Cambio" && !sinConvocatoria && qbCandidatosSale.length === 0 && (
                    <p className="muted">No hay nadie en cancha disponible para salir en este equipo.</p>
                  )}
                </label>
              )}
              {accionQuickBar === "Cambio" && qbJugadorId != null && (
                <label>
                  Entra (solo suplentes)
                  <select value={qbJugadorIdEntra ?? ""} onChange={(e) => setQbJugadorIdEntra(e.target.value ? Number(e.target.value) : null)}>
                    <option value="">Elegir...</option>
                    {qbCandidatosEntra.map((j) => (
                      <option key={j.jugador_id} value={j.jugador_id}>
                        {j.dorsal ? `#${j.dorsal} ` : ""}
                        {j.jugador}
                        {sinConvocatoria ? " (sin datos de alineación)" : ""}
                      </option>
                    ))}
                  </select>
                  {!sinConvocatoria && qbCandidatosEntra.length === 0 && (
                    <p className="muted">
                      No hay suplentes disponibles para entrar (todos ya entraron o fueron expulsados). Sumá un
                      suplente desde la convocatoria del partido si llegó alguien tarde.
                    </p>
                  )}
                </label>
              )}
              <label>
                Minuto
                <input type="number" min={0} max={130} value={qbMinuto} onChange={(e) => setQbMinuto(e.target.value)} />
              </label>
              <div className="resource-form__actions">
                <button type="button" className="link-button" onClick={resetQuickBar}>
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={agregarOtroEvento}
                  disabled={
                    qbEquipoId == null ||
                    qbJugadorId == null ||
                    qbMinuto === "" ||
                    (accionQuickBar === "Cambio" && qbJugadorIdEntra == null)
                  }
                >
                  + Agregar
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Zona cuaternaria: timeline ascendente. */}
        <section className="card">
          <h2>Timeline</h2>
          {eventosTimeline.length === 0 && <p className="muted">Sin eventos cargados todavía — 0-0 también es un resultado válido.</p>}
          {eventosTimeline.length > 0 && (
            <ul className="eventos-timeline">
              {eventosTimeline.map((e) => {
                const nombreEq = nombreEquipo.get(e.equipoId) ?? `#${e.equipoId}`;
                const nombreJ = nombreJugadorConDorsal(e.jugadorId);
                const nombreEntra = e.jugadorIdEntra != null ? nombreJugadorConDorsal(e.jugadorIdEntra) : null;
                // Fase 1/2: aria-label agrupado en el <li> (no spans
                // sueltos) — un screen reader lee "minuto X, tipo, equipo,
                // jugador" de una vez, en vez de fragmentos desconectados.
                const ariaLabel =
                  e.tipo === "Cambio"
                    ? `Minuto ${e.minuto}, cambio, ${nombreEq}, sale ${nombreJ}, entra ${nombreEntra ?? ""}`
                    : `Minuto ${e.minuto}, ${e.tipo.toLowerCase()}, ${nombreEq}, ${nombreJ}${e.esAuto ? ", automática por doble amarilla" : ""}`;
                return (
                  <li key={e.id} aria-label={ariaLabel} className={e.esAuto ? "eventos-timeline__fila--auto" : undefined}>
                    <span className="eventos-timeline__minuto" aria-hidden="true">
                      {e.minuto}'
                    </span>
                    <span aria-hidden="true">{TIPO_ICONO[e.tipo]}</span>
                    <div className="eventos-timeline__detalle" aria-hidden="true">
                      {/* Formato pedido para Cambio: "[Equipo] | Sale: A ➔
                          Entra: B", en 2 líneas (Design Fase 2 — un string
                          único de 45-60+ caracteres se parte feo en
                          celular a 360-400px). */}
                      <span>{nombreEq}</span>
                      {e.tipo === "Cambio" ? (
                        <span className="muted">
                          Sale: {nombreJ} <span aria-hidden="true">➔</span> Entra: {nombreEntra}
                        </span>
                      ) : (
                        <span className="muted">
                          {nombreJ}
                          {e.esAuto && <span className="eventos-timeline__badge-auto"> · auto</span>}
                        </span>
                      )}
                    </div>
                    {(e.tipo === "Tarjeta Amarilla" || e.tipo === "Tarjeta Roja" || e.tipo === "Cambio") && !e.esAuto ? (
                      <button
                        type="button"
                        className="link-button"
                        aria-label={`Quitar ${e.tipo.toLowerCase()} de ${nombreJ}`}
                        onClick={() => setOtrosEventos((prev) => prev.filter((o) => o.id !== e.id))}
                      >
                        Quitar
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {esCorrido && (
          <label>
            Ganador
            <select
              value={ganadorCorridoId ?? ""}
              onChange={(e) => setGanadorCorridoId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Elegir...</option>
              <option value={partido.equipos_id_local}>{nombreLocal}</option>
              <option value={partido.equipos_id_visitante}>{nombreVisitante}</option>
            </select>
          </label>
        )}

        {mutation.isError && <p className="error-text">{apiErrorMessage(mutation.error)}</p>}
        {!todosLosSlotsCompletos && slots.length > 0 && (
          <p className="muted">Completá jugador y minuto de todos los goles antes de guardar.</p>
        )}
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={onClose}>
            Cancelar
          </button>
          <button type="button" disabled={!puedeGuardar || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending ? "Guardando..." : "Guardar resultado"}
          </button>
        </div>
      </div>
    </div>
  );
}
