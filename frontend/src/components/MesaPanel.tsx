import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { useNombrePorIdConFaltantes } from "../hooks/useFetchFaltantes";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import {
  type EventoPendiente,
  guardarEventoPendiente,
  leerEventoPendiente,
  limpiarEventoPendiente,
} from "../lib/colaOfflineEventos";
import { Cronometro } from "./Cronometro";
import { deriveEnCancha, deriveHistorialElegibilidad, deriveTitularSuplente, TIPOS, TIPO_ICONO, type PlantillaJugador, type TipoEvento } from "./eventos";
import { ModalSustitucion } from "./ModalSustitucion";

/** 3B-1 (docs/plans/cierre-backlog-todos-plan.md): distingue "no hay red"
 * de "el backend rechazó la request" — solo el primer caso debe encolarse
 * para reintentar solo, un 400/409 real (jugador ajeno al equipo, minuto
 * fuera de rango...) reintentado a ciegas nunca va a pasar y confundiría
 * más que un error inmediato. `fetch` tira `TypeError` cuando no llega a
 * conectar (a diferencia de un 4xx/5xx, que sí resuelve una Response) —
 * es la señal más confiable sin inventar un código de error propio. */
function esErrorDeRed(error: unknown): boolean {
  return error instanceof TypeError;
}

type EventoBody = {
  partidos_id: number;
  jugador_id: number;
  equipo_id: number;
  eventos_id: number;
  jugador_id_entra?: number | null;
  // Área 3 (modo-vivo-sustituciones-cierre-plan.md, T3/T22): opcional
  // porque ya no se pide a mano — el servidor lo calcula SIEMPRE desde el
  // cronómetro para el camino en vivo (que es el único que pasa por acá) e
  // ignora lo que se mande. Se deja de enviar directamente en vez de
  // mandar un valor que el backend va a descartar igual.
  minuto?: number;
};

const LIVE_POLL_MS = 5000;
// 3B-1: cada cuánto reintenta solo un evento en cola, además de cuando
// dispara el evento "online" del navegador — ver el efecto de reintento
// en MesaPanel para por qué hace falta el intervalo además del evento.
const INTERVALO_REINTENTO_MS = 15000;


/** Panel en vivo de un partido: marcador, cronómetro, carga de eventos y
 * timeline. Vive en `components/` y no en `pages/control-mesa/` a propósito
 * (gestionar-partido-alineaciones-plan.md, H6-eng): lo consume tanto la vista
 * de Control de Mesa como el módulo Árbitro, y una página de un módulo
 * importando de la carpeta de otro cementa una violación de frontera.
 *
 * `onVolver` es opcional: cuando va embebido en `GestionarPartido` la
 * navegación la maneja la página, no este componente.
 *
 * La convocatoria YA NO se edita acá — se mudó a `AlineacionEditor`, dentro de
 * la vista "Gestionar Partido". Este panel solo la CONSUME, para filtrar los
 * candidatos de `CargaEvento`.
 *
 * `onIrAConvocatoria` (C2a, docs/plans/cierre-pendientes-todos-plan.md):
 * acción primaria del empty state de `ModalSustitucion` cuando no hay
 * ningún elegible para entrar. `GestionarPartido` es hoy el único montaje
 * real de este panel (`MisPartidos.tsx`, Árbitro, navega a esa misma
 * ruta) y ya renderiza `AlineacionEditor` en la MISMA página — así que
 * "ir a Convocatoria" es scrollear ahí, no una navegación con round trip
 * que perdería el partido en curso. Opcional: sin la prop, el botón no
 * se muestra (mismo criterio que `onVolver`). */
export function MesaPanel({
  partidoId,
  onVolver,
  onIrAConvocatoria,
}: {
  partidoId: number;
  onVolver?: () => void;
  onIrAConvocatoria?: () => void;
}) {
  const queryClient = useQueryClient();
  const { session } = useAuth();
  const online = useOnlineStatus();
  // 3B-1: se carga del localStorage al montar (no en un useEffect) para
  // que un refresh de página a mitad de un corte no pierda el evento que
  // ya se había guardado — mismo criterio que HITOS_PARTIDO (ver
  // Cronometro.tsx): el estado real vive afuera del componente, esto solo
  // lo refleja.
  const [pendiente, setPendiente] = useState<EventoPendiente | null>(() => leerEventoPendiente(partidoId));
  // Área 3 (T3): minuto emitido por <Cronometro>, ver su prop
  // `onMinutoActual`. `null` mientras no hay nada que mostrar (cronómetro
  // recién montado, todavía sin el primer tick, o el partido no arrancó).
  const [minutoActual, setMinutoActual] = useState<number | null>(null);

  const partidoQuery = useQuery({
    queryKey: ["partido", partidoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}", { params: { path: { partido_id: partidoId } } });
      if (error) throw error;
      return data;
    },
  });

  // Área 3 (T8): reglas de cambio del torneo — cuántos cambios permite por
  // equipo (para el contador "X/Y") y si permite reingresos. `staleTime`
  // largo: esto no cambia durante un partido.
  const torneoQuery = useQuery({
    queryKey: ["torneo", partidoQuery.data?.torneo_id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}", {
        params: { path: { torneo_id: partidoQuery.data!.torneo_id } },
      });
      if (error) throw error;
      return data;
    },
    enabled: partidoQuery.data != null,
    staleTime: 5 * 60 * 1000,
  });

  const equiposQuery = useQuery({
    queryKey: ["equipos-catalogo"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/equipos", { params: { query: { limit: 200 } } });
      if (error) throw error;
      return data;
    },
    staleTime: 5 * 60 * 1000,
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

  const eventosPartidoQuery = useQuery({
    queryKey: ["eventos-partido", partidoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eventos-partido", { params: { query: { partidos_id: partidoId } } });
      if (error) throw error;
      return data;
    },
    refetchInterval: LIVE_POLL_MS,
  });

  const equipoLocalId = partidoQuery.data?.equipos_id_local;
  const equipoVisitanteId = partidoQuery.data?.equipos_id_visitante;

  const plantillaLocalQuery = useQuery({
    queryKey: ["plantilla", equipoLocalId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: equipoLocalId as number } },
      });
      if (error) throw error;
      return data;
    },
    enabled: equipoLocalId != null,
  });

  const plantillaVisitanteQuery = useQuery({
    queryKey: ["plantilla", equipoVisitanteId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: equipoVisitanteId as number } },
      });
      if (error) throw error;
      return data;
    },
    enabled: equipoVisitanteId != null,
  });

  // 3B-2 (docs/plans/cierre-backlog-todos-plan.md): mismo queryKey que
  // Convocatoria.tsx (React Query dedupea el fetch solo) — acá se USA
  // para filtrar los candidatos de CargaEvento, allá se EDITA.
  const convocadosQuery = useQuery({
    queryKey: ["convocados", partidoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/convocados", {
        params: { path: { partido_id: partidoId } },
      });
      if (error) throw error;
      return data as { jugador_perfil_id: number; titular: boolean }[];
    },
  });
  // Sin convocatoria guardada = sin filtrar (toda la plantilla vigente
  // sigue siendo candidata, comportamiento de siempre) — es estrictamente
  // opt-in, ver el comentario de Convocatoria.tsx.
  const perfilesConvocados = useMemo(
    () => new Set((convocadosQuery.data ?? []).map((c) => c.jugador_perfil_id)),
    [convocadosQuery.data],
  );
  // Área 3 (T4): alineación en vivo — quiénes son titulares AHORA (según la
  // convocatoria guardada), para ofrecer el tap "Sacar" por jugador.
  const titularesPerfilIds = useMemo(
    () => new Set((convocadosQuery.data ?? []).filter((c) => c.titular).map((c) => c.jugador_perfil_id)),
    [convocadosQuery.data],
  );
  const plantillaLocalFiltrada = useMemo(
    () =>
      perfilesConvocados.size === 0
        ? (plantillaLocalQuery.data ?? [])
        : (plantillaLocalQuery.data ?? []).filter((j) => perfilesConvocados.has(j.jugador_perfil_id)),
    [plantillaLocalQuery.data, perfilesConvocados],
  );
  const plantillaVisitanteFiltrada = useMemo(
    () =>
      perfilesConvocados.size === 0
        ? (plantillaVisitanteQuery.data ?? [])
        : (plantillaVisitanteQuery.data ?? []).filter((j) => perfilesConvocados.has(j.jugador_perfil_id)),
    [plantillaVisitanteQuery.data, perfilesConvocados],
  );

  const equipoNombreBase = useMemo(
    () => new Map((equiposQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equiposQuery.data],
  );
  // Bug 2 (D2, parte B): resolución dirigida — mismo criterio que
  // ControlDeMesaPage, para el equipo local/visitante de este partido.
  const equipoNombre = useNombrePorIdConFaltantes("/api/v1/equipos", equipoNombreBase, [equipoLocalId, equipoVisitanteId]);
  const eventoIdPorNombre = useMemo(
    () => new Map((eventosCatalogoQuery.data ?? []).map((e) => [e.nombre, e.id])),
    [eventosCatalogoQuery.data],
  );
  const eventoNombrePorId = useMemo(
    () => new Map((eventosCatalogoQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [eventosCatalogoQuery.data],
  );

  const eventosRegistrados = (eventosPartidoQuery.data ?? []).filter((e) => e.estado === "Registrado");

  // Área 3 (T8): contador "cambios usados X/Y" — SIEMPRE derivado de la
  // timeline real (no un useState local que se resetearía al refrescar la
  // página, Sección 5 del plan: "sub-ingeniería a vigilar"). Solo se
  // muestra cuando el torneo tiene un tope configurado.
  const cambiosUsadosPorEquipo = useMemo(() => {
    const conteo = new Map<number, number>();
    for (const e of eventosRegistrados) {
      if (eventoNombrePorId.get(e.eventos_id) === "Cambio") {
        conteo.set(e.equipo_id, (conteo.get(e.equipo_id) ?? 0) + 1);
      }
    }
    return conteo;
  }, [eventosRegistrados, eventoNombrePorId]);
  const maximoCambios = torneoQuery.data?.maximo_cambios_por_equipo ?? null;

  // goles-por-marcador-slots-plan.md, Fase 3 Eng (corrección 4): 1 sola
  // fuente para ambos ejes (historial de la timeline + titular/suplente de
  // la convocatoria), compartida por los 3 call-sites de más abajo
  // (alineación en vivo "Sacar", ModalSustitucion "Entra", CargaEvento) —
  // antes cada uno tenía su propio cálculo, divergente (hallazgo 1 del
  // plan: CargaEvento no distinguía titular/suplente en absoluto).
  const { salidosOExpulsados, yaEntraron } = useMemo(
    () => deriveHistorialElegibilidad(eventosRegistrados, eventoNombrePorId),
    [eventosRegistrados, eventoNombrePorId],
  );
  const plantillaCompleta = useMemo(
    () => [...(plantillaLocalQuery.data ?? []), ...(plantillaVisitanteQuery.data ?? [])],
    [plantillaLocalQuery.data, plantillaVisitanteQuery.data],
  );
  // Ambos sets vacíos = sin convocatoria guardada para este partido (D4,
  // `partido.py:170-179`) — cada call-site que los usa muestra la
  // plantilla completa + un aviso en vez de asumir un filtrado que no
  // puede cumplir.
  const { titulares: titularesJugadorIds, suplentes: suplentesJugadorIds } = useMemo(
    // control-mesa-reactividad-playoffs-plan.md, Fase 3 §2: `perfilesConvocados`
    // (TODAS las filas convocadas, ya calculado arriba) en vez de solo
    // titularesPerfilIds — antes un jugador del club nunca convocado a
    // este partido igual caía en `suplentes` (filtrado estricto de
    // suplentes, mismo bug que ModalResultadoDirecto.tsx).
    () => deriveTitularSuplente(perfilesConvocados, titularesPerfilIds, plantillaCompleta),
    [perfilesConvocados, titularesPerfilIds, plantillaCompleta],
  );
  const sinConvocatoria = perfilesConvocados.size === 0;
  // Fase 3 §1 ("estado mutante en cambios"): quién está en cancha AHORA —
  // titulares vigentes MÁS suplentes que ya entraron por un Cambio
  // registrado — para que "Sacar"/"Sale" ofrezca también a un suplente que
  // entró hace un rato, no solo a los titulares originales.
  const enCanchaJugadorIds = useMemo(
    () => deriveEnCancha(titularesJugadorIds, salidosOExpulsados, yaEntraron),
    [titularesJugadorIds, salidosOExpulsados, yaEntraron],
  );

  // Marcador calculado como vw_goles_acreditados: Gol suma al equipo del
  // jugador, Autogol suma al rival. Se recalcula en cada refetch — no hay
  // estado de marcador guardado aparte.
  const marcador = useMemo(() => {
    let local = 0;
    let visitante = 0;
    for (const e of eventosRegistrados) {
      const tipo = eventoNombrePorId.get(e.eventos_id);
      if (tipo !== "Gol" && tipo !== "Autogol") continue;
      const acreditadoLocal = tipo === "Autogol" ? e.equipo_id !== equipoLocalId : e.equipo_id === equipoLocalId;
      if (acreditadoLocal) local += 1;
      else visitante += 1;
    }
    return { local, visitante };
  }, [eventosRegistrados, eventoNombrePorId, equipoLocalId]);

  // Desempate de eliminatoria: tiempo extra y penales (docs/plans/
  // desempate-tiempo-extra-penales-plan.md, Fase 1, SPEC-REVIEW S12/D-Q2)
  // — reemplaza la derivación de cliente que había acá
  // (`ronda_nombre != null && marcador.local === marcador.visitante`),
  // que no distinguía ida de vuelta (bug: una IDA empatada pedía
  // desempate igual) ni sabía cuándo el torneo es 'Corrido'.
  // `elegible_desempate` (calculado en el servidor) ya resuelve las dos:
  // Eliminación no-Corrido, y NUNCA una ida. `goles_previos_global_*` son
  // los goles YA JUGADOS de la ida (si este partido es la vuelta), cruzados
  // a la orientación local/visitante de este partido — sumados al marcador
  // en vivo arman el GLOBAL real de la llave.
  const globalLocal = marcador.local + (partidoQuery.data?.goles_previos_global_local ?? 0);
  const globalVisitante = marcador.visitante + (partidoQuery.data?.goles_previos_global_visitante ?? 0);
  const requiereDesempate = !!partidoQuery.data?.elegible_desempate && globalLocal === globalVisitante;

  // D1 (docs/plans/cierre-pendientes-todos-plan.md) — un solo patrón de
  // estado pending, global: mientras cualquiera de las dos mutaciones de
  // evento está en curso, la región aria-live anuncia "Guardando…";
  // al terminar, muestra la confirmación con el contenido del evento
  // (antes no había NINGUNA confirmación de éxito — Design Fase 2, Pass 2,
  // GAP CRÍTICO). `null` = nada que anunciar todavía.
  const [ultimaConfirmacion, setUltimaConfirmacion] = useState<string | null>(null);

  function nombreDorsalPorId(id: number): string {
    const j = plantillaCompleta.find((p) => p.jugador_id === id);
    return j ? `${j.dorsal != null ? `#${j.dorsal} ` : ""}${j.jugador}` : `#${id}`;
  }

  function describirEventoConfirmado(body: EventoBody, minuto: number): string {
    const tipoNombre = eventoNombrePorId.get(body.eventos_id) ?? "Evento";
    if (tipoNombre === "Cambio" && body.jugador_id_entra != null) {
      return `Cambio registrado: sale ${nombreDorsalPorId(body.jugador_id)}, entra ${nombreDorsalPorId(body.jugador_id_entra)} (${minuto}')`;
    }
    return `${tipoNombre} registrado: ${nombreDorsalPorId(body.jugador_id)} (${minuto}')`;
  }

  const mutation = useMutation({
    mutationFn: async (body: EventoBody) => {
      const { data, error } = await api.POST("/api/v1/eventos-partido", { body });
      if (error) throw error;
      return data;
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["eventos-partido", partidoId] });
      setUltimaConfirmacion(describirEventoConfirmado(variables, data.minuto));
    },
  });

  // 3B-1: mensaje del intento de FLUSH automático (al reconectar) — no
  // reusa `mutation.error`, que es de la última mutación disparada
  // (podría quedar mostrando un fallo de un flush viejo sobre el form de
  // carga normal, que es una mutación distinta en el tiempo aunque
  // comparta el mismo hook). `null` = sin error que mostrar.
  const [errorPendiente, setErrorPendiente] = useState<string | null>(null);

  // Área 3 (T4): jugador titular tocado en la alineación en vivo — abre
  // ModalSustitucion. `null` = modal cerrado. Ver Sección 4 del plan:
  // cerrar sin elegir reemplazo no debe persistir nada, por eso esto vive
  // en un estado propio (no en el de CargaEvento) y solo se llama a
  // `onSubmit` cuando el operador confirma un elegible.
  const [sustituyendoA, setSustituyendoA] = useState<PlantillaJugador | null>(null);
  const sustitucion = useMutation({
    mutationFn: async (body: EventoBody) => {
      const { data, error } = await api.POST("/api/v1/eventos-partido", { body });
      if (error) throw error;
      return data;
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["eventos-partido", partidoId] });
      setSustituyendoA(null);
      setUltimaConfirmacion(describirEventoConfirmado(variables, data.minuto));
    },
  });

  // D1: única fuente de la región aria-live de zona secundaria — "Guardando…"
  // mientras cualquiera de las dos mutaciones está en curso, si no la
  // última confirmación de éxito.
  const estadoEnvio = mutation.isPending || sustitucion.isPending ? "Guardando…" : ultimaConfirmacion;

  /** Reemplaza el `onSubmit={(body) => mutation.mutate(body)}` directo
   * que tenía este panel: intenta la carga normal, y si falla
   * específicamente por falta de red (no por un rechazo real del
   * backend — ver esErrorDeRed), la guarda para reintentar sola al
   * reconectar en vez de perderla.
   *
   * Devuelve si CargaEvento debe resetear el form (`true`) o quedarse en
   * la pantalla de confirmación mostrando el error (`false`) — cargado
   * con éxito Y encolado para enviar solo son los dos casos "true": en
   * ninguno de los dos el admin tiene algo más que hacer con ESTE
   * formulario. Solo un rechazo real del backend (ni red ni éxito)
   * amerita dejarlo abierto. */
  async function manejarSubmitEvento(body: EventoBody): Promise<boolean> {
    try {
      await mutation.mutateAsync(body);
      return true;
    } catch (error) {
      if (esErrorDeRed(error)) {
        guardarEventoPendiente(partidoId, body);
        setPendiente(leerEventoPendiente(partidoId));
        return true;
      }
      // No es de red: mutation.error ya queda seteado (mutateAsync
      // relanza la excepción) y CargaEvento lo muestra — se queda abierto.
      return false;
    }
  }

  /** Intenta enviar lo que está en la cola — la llama tanto el efecto de
   * reconexión (automático) como el botón "Reintentar ahora" (manual, por
   * si el admin sabe que ya hay señal antes de que el navegador se entere). */
  async function flushPendiente(body: EventoBody) {
    try {
      await mutation.mutateAsync(body);
      limpiarEventoPendiente(partidoId);
      setPendiente(null);
      setErrorPendiente(null);
    } catch (error) {
      if (!esErrorDeRed(error)) {
        limpiarEventoPendiente(partidoId);
        setPendiente(null);
        setErrorPendiente(apiErrorMessage(error, "El evento pendiente no se pudo guardar — cargalo de nuevo."));
      }
      // Sigue siendo de red: queda tal cual en la cola, sin marcar error
      // (todavía no es un fallo definitivo, es "seguimos sin conexión").
    }
  }

  // Reintento automático de lo pendiente: el evento "online" del
  // navegador (rápido cuando SÍ dispara) + un intervalo de respaldo — un
  // wifi de cancha que sigue "conectado" pero intermitente no siempre
  // dispara online/offline, así que atarse solo a ese evento dejaría la
  // cola sin reintentar hasta el próximo "Reintentar ahora" manual. No
  // depende de `online` (el estado del hook, para el banner) — la fuente
  // de verdad de si YA hay señal es el resultado real del POST, no lo que
  // el navegador cree.
  useEffect(() => {
    if (!pendiente) return;
    const { guardadoEn: _guardadoEn, ...body } = pendiente;
    const intentar = () => void flushPendiente(body);
    const intervalo = setInterval(intentar, INTERVALO_REINTENTO_MS);
    window.addEventListener("online", intentar);
    return () => {
      clearInterval(intervalo);
      window.removeEventListener("online", intentar);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendiente]);

  // Corrección de minuto de un evento ya cargado (gestion-avanzada-
  // equipos-control-mesa-plan.md, Entregable 3 — "cargué un gol en el
  // minuto 23 pero fue en el 32"). Caso DISTINTO de corregir un Hito de
  // tiempo (eso vive en Cronometro.tsx): esto es la timeline de eventos
  // que ya existía en este panel.
  const corregirMinutoEvento = useMutation({
    mutationFn: async ({ id, minuto }: { id: number; minuto: number }) => {
      const { data, error } = await api.PATCH("/api/v1/eventos-partido/{evento_partido_id}", {
        params: { path: { evento_partido_id: id } },
        body: { minuto },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["eventos-partido", partidoId] }),
  });

  if (partidoQuery.isLoading) return <div className="page"><p>Cargando partido...</p></div>;
  if (partidoQuery.isError || !partidoQuery.data) {
    return (
      <div className="page">
        {onVolver && <button type="button" onClick={onVolver}>← Volver</button>}
        <p className="error-text">No se pudo cargar el partido.</p>
      </div>
    );
  }

  const partido = partidoQuery.data;
  // Motor de Formatos: un partido de bracket puede nacer con uno o los
  // dos equipos sin definir todavía ("Ganador Partido N", TBD hasta que
  // el partido anterior termine) — no hay nada que cargar acá hasta
  // entonces.
  if (partido.equipos_id_local == null || partido.equipos_id_visitante == null) {
    return (
      <div className="page">
        {onVolver && <button type="button" className="link-button" onClick={onVolver}>← Volver a la lista</button>}
        <p className="muted">Este partido todavía no tiene los dos equipos definidos — esperá a que termine el partido anterior del bracket.</p>
      </div>
    );
  }
  const nombreLocal = equipoNombre.get(partido.equipos_id_local) ?? `Equipo #${partido.equipos_id_local}`;
  const nombreVisitante = equipoNombre.get(partido.equipos_id_visitante) ?? `Equipo #${partido.equipos_id_visitante}`;

  return (
    <div className="page mesa">
      {onVolver && <button type="button" className="link-button" onClick={onVolver}>← Volver a la lista</button>}

      {/* D1 (docs/plans/cierre-pendientes-todos-plan.md) — 3 zonas fijas:
          primaria (marcador + estado, lo que el mesero mira sin tocar,
          sticky a 375px), secundaria (cronómetro + carga de evento +
          alineación en vivo, donde el pulgar trabaja) y terciaria
          (timeline). Wireframe de referencia:
          ~/.gstack/projects/Score-App/designs/mesa-panel-3-zonas-20260917/
          wireframe-zonas.html (375px y ≥1000px). Puro layout — sin
          cambios de comportamiento, `index.css` activa la grilla de 2
          columnas recién en el mismo ≥1000px que ya usa el
          drag-and-drop de AlineacionEditor (decisión activa del
          2026-09-08), no un breakpoint nuevo. */}
      <div className="mesa-zonas">
        <div className="mesa-zona-primaria">
          <div className="marcador">
            <div className="marcador__equipo"><span>{nombreLocal}</span></div>
            <div className="marcador__score">{marcador.local} - {marcador.visitante}</div>
            <div className="marcador__equipo"><span>{nombreVisitante}</span></div>
          </div>
          <div className="marcador__estado">
            <span className={`badge badge--${partido.estado.replace(" ", "-").toLowerCase()}`}>{partido.estado}</span>
            <span className="muted">operando como {session?.username} ({session?.rol})</span>
          </div>

          {/* 3B-1 (docs/plans/cierre-backlog-todos-plan.md, offline-first en
              Control de Mesa, alcance reducido): indicador de "sin conexión"
              — informativo aunque no haya nada pendiente todavía, para que el
              árbitro sepa POR QUÉ un evento nuevo se va a encolar en vez de
              entrar directo. */}
          {!online && (
            <p className="muted mesa-offline-aviso">
              🔌 Sin conexión — los eventos se guardan en este dispositivo y se envían solos al reconectar.
            </p>
          )}
          {errorPendiente && <p className="error-text">{errorPendiente}</p>}
        </div>

        <div className="mesa-zona-secundaria">
          {/* mostrarInicio={false} (H-10 del plan): el arranque del partido es UNA
              sola acción y vive en la barra de "Gestionar Partido". Sin esto habría
              dos botones ▶ en la misma pantalla con efectos distintos — el del
              cronómetro dispara Inicio_Partido + Inicio_Periodo(1), el otro solo el
              primero, y el operador se quedaría con el reloj parado en 00:00.

              Cronómetro entero en zona secundaria, no partido entre zonas: es
              un solo componente con controles fuertemente acoplados entre sí
              (Pausa, Fin de Período, Fin de Partido, cierre forzado), no
              seguro de separar sin un refactor propio fuera del alcance de
              D1. La obligación de sticky nombra solo .marcador +
              .marcador__estado, no Cronómetro completo. */}
          <Cronometro
            partidoId={partidoId}
            equipoLocalId={partido.equipos_id_local}
            equipoVisitanteId={partido.equipos_id_visitante}
            nombreLocal={nombreLocal}
            nombreVisitante={nombreVisitante}
            mostrarInicio={false}
            onMinutoActual={setMinutoActual}
            requiereDesempate={requiereDesempate}
            metodoDesempateAplicable={partidoQuery.data?.metodo_desempate_aplicable}
            esEliminacion={partido.ronda_nombre != null}
            metodoDesempateEliminatoriaTorneo={torneoQuery.data?.metodo_desempate_eliminatoria}
            esVuelta={partido.partido_ida_id != null}
            globalLocal={globalLocal}
            globalVisitante={globalVisitante}
          />

          {/* D1: un solo patrón de estado pending para todas las fases
              reorganizadas (obligación global, no una decisión por fase) —
              control deshabilitado (ya lo hacía) + esta región aria-live
              anunciando "Guardando…" y, después, la confirmación de éxito
              con el contenido del evento. Antes no había NINGUNA
              confirmación de éxito visible (Design Fase 2, Pass 2: "GAP
              CRÍTICO"). */}
          {estadoEnvio && (
            <p className="mesa-confirmacion" aria-live="polite">{estadoEnvio}</p>
          )}

          {/* 3A-8 (docs/plans/cierre-backlog-todos-plan.md, EC-C): antes, la
              única protección contra cargar un evento en un partido que no
              arrancó vivía en el filtro de la lista de ControlDeMesaPage — acá
              en MesaPanel, embebido también en MisPartidos.tsx (Árbitro), no
              había nada. El backend ya rechaza el POST (EventoPartidoService),
              esto es la versión visible: mismo criterio que el guard del
              service — solo 'En curso' habilita carga nueva. 'Finalizado'
              sigue mostrando la timeline con corrección de minuto habilitada
              más abajo (EC-15), no se toca acá. */}
          {partido.estado === "En curso" ? (
        pendiente ? (
          // Un solo slot de cola (ver colaOfflineEventos.ts) — mientras
          // haya algo pendiente, el form de carga se oculta en vez de
          // dejar que un segundo evento pise al primero en el mismo slot.
          <section className="card">
            <p className="muted">
              Hay un evento cargado el {new Date(pendiente.guardadoEn).toLocaleTimeString("es-AR")} que todavía no
              se pudo enviar{online ? "" : " (sin conexión)"}.
            </p>
            <div className="confirmar-evento__acciones">
              <button
                type="button"
                className="link-button"
                onClick={() => {
                  limpiarEventoPendiente(partidoId);
                  setPendiente(null);
                  setErrorPendiente(null);
                }}
              >
                Descartar
              </button>
              <button
                type="button"
                disabled={mutation.isPending}
                onClick={() => {
                  const { guardadoEn: _guardadoEn, ...body } = pendiente;
                  void flushPendiente(body);
                }}
              >
                {mutation.isPending ? "Enviando..." : "Reintentar ahora"}
              </button>
            </div>
          </section>
        ) : (
          <CargaEvento
            partidoId={partidoId}
            equipoLocalId={partido.equipos_id_local}
            equipoVisitanteId={partido.equipos_id_visitante}
            nombreLocal={nombreLocal}
            nombreVisitante={nombreVisitante}
            // 3B-2: filtrada por convocatoria si hay una guardada — ver
            // el comentario de perfilesConvocados más arriba.
            plantillaLocal={plantillaLocalFiltrada}
            plantillaVisitante={plantillaVisitanteFiltrada}
            eventosRegistrados={eventosRegistrados}
            eventoIdPorNombre={eventoIdPorNombre}
            eventoNombrePorId={eventoNombrePorId}
            minutoActual={minutoActual}
            onSubmit={manejarSubmitEvento}
            submitting={mutation.isPending}
            submitError={mutation.isError ? apiErrorMessage(mutation.error) : null}
          />
        )
      ) : (
        <section className="card">
          <p className="muted">
            {partido.estado === "Programado"
              ? "El partido todavía no arrancó — usá \"Empezar Partido\" antes de cargar eventos."
              : `No se pueden cargar eventos nuevos: el partido está "${partido.estado}".`}
          </p>
        </section>
      )}

      {/* Área 3 (T4): alineación en vivo — tocar un titular abre
          ModalSustitucion ("¿Por quién ingresa?"). Zona secundaria del
          wireframe de dos columnas por equipo (Design Fase 2, Pass 1),
          mismo patrón visual que AlineacionEditor (Titulares/Suplentes
          lado a lado). Solo con el partido en curso: antes de arrancar no
          hay "sale/entra" que registrar. */}
      {partido.estado === "En curso" && (
        <section className="card alineacion-en-vivo">
          <h2>Alineación en vivo</h2>
          {/* C2a (docs/plans/cierre-pendientes-todos-plan.md): sin
              convocatoria guardada, `enCanchaJugadorIds` sale VACÍO por
              diseño (deriveTitularSuplente, ver su docstring) — antes eso
              dejaba esta lista siempre vacía y sin ningún "Sacar" posible,
              el punto de entrada roto que D4 pretendía cubrir para
              "resultado directo" pero que este camino en vivo no tenía.
              El caption avisa que se cayó al fallback. */}
          {sinConvocatoria && (
            <p className="muted">Sin convocatoria guardada — mostrando plantilla completa.</p>
          )}
          <div className="alineacion-en-vivo__equipos">
            {(
              [
                [partido.equipos_id_local, nombreLocal, plantillaLocalFiltrada],
                [partido.equipos_id_visitante, nombreVisitante, plantillaVisitanteFiltrada],
              ] as const
            ).map(([equipoId, nombre, plantillaEquipo]) => {
              // Fix (goles-por-marcador-slots-plan.md, Fase 1, hallazgo 3):
              // antes no excluía `salidosOExpulsados` — un titular YA
              // sustituido (o expulsado) seguía apareciendo acá con botón
              // "Sacar", permitiendo una segunda "salida" del mismo
              // jugador sin aviso (el backend ahora sí lo rechaza,
              // `reglas_cambio.validar_reglas_cambio`, pero esta lista no
              // debía ni ofrecerlo).
              //
              // `enCanchaJugadorIds` (Fase 3 §1, estado mutante), no solo
              // `titularesJugadorIds`: un suplente que ya entró por un
              // Cambio debe aparecer acá con botón "Sacar" para un cambio
              // posterior, sin esperar a recargar la página.
              //
              // C2a: sin convocatoria, `enCanchaJugadorIds` no distingue
              // nada (sale vacío) — el fallback ofrece la PLANTILLA
              // COMPLETA del equipo (menos quien ya salió/fue expulsado),
              // porque el sistema genuinamente no sabe quién es titular;
              // mismo criterio de confianza en el operador que D4 ya usa
              // para "resultado directo" sin alineación.
              const candidatosSalida = sinConvocatoria
                ? plantillaEquipo.filter((j) => !salidosOExpulsados.has(j.jugador_id))
                : plantillaEquipo.filter(
                    (j) => enCanchaJugadorIds.has(j.jugador_id) && !salidosOExpulsados.has(j.jugador_id),
                  );
              return (
                <div key={equipoId}>
                  <h3>{nombre}</h3>
                  {maximoCambios != null && (
                    <p className="muted">Cambios usados: {cambiosUsadosPorEquipo.get(equipoId) ?? 0}/{maximoCambios}</p>
                  )}
                  {candidatosSalida.length === 0 ? (
                    <p className="muted">Sin nadie en cancha marcado en la convocatoria.</p>
                  ) : (
                    <ul className="alineacion-lista">
                      {candidatosSalida.map((j) => (
                        <li key={j.jugador_id}>
                          <span>{j.dorsal != null ? `#${j.dorsal} ` : ""}{j.jugador}</span>
                          <button type="button" className="link-button" onClick={() => setSustituyendoA(j)}>
                            Sacar
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}
        </div>

        <div className="mesa-zona-terciaria">
      {sustituyendoA && (() => {
        const plantillaEquipoSaliente =
          sustituyendoA.equipo_id === partido.equipos_id_local ? plantillaLocalFiltrada : plantillaVisitanteFiltrada;
        // Fix (goles-por-marcador-slots-plan.md, Fase 1, hallazgo 2): antes
        // `elegibles` era la plantilla completa (menos sale/salidos/ya
        // entraron) — un titular en cancha que nunca salió podía aparecer
        // como candidato a "Entra". Este flujo se dispara tocando un
        // titular EN LA LISTA DE ARRIBA — desde C2a esa lista puede venir
        // del fallback sin convocatoria (`sinConvocatoria`), así que acá
        // se replica el mismo fallback: sin convocatoria no hay
        // `suplentesJugadorIds` que filtrar (sale vacío por diseño), así
        // que los candidatos a "Entra" son la plantilla completa menos
        // quien ya sale, salió o fue expulsado, o ya entró.
        const elegibles = sinConvocatoria
          ? plantillaEquipoSaliente.filter(
              (j) =>
                j.jugador_id !== sustituyendoA.jugador_id &&
                !salidosOExpulsados.has(j.jugador_id) &&
                !yaEntraron.has(j.jugador_id),
            )
          : plantillaEquipoSaliente.filter(
              (j) =>
                suplentesJugadorIds.has(j.jugador_id) &&
                !salidosOExpulsados.has(j.jugador_id) &&
                !yaEntraron.has(j.jugador_id),
            );
        return (
          <ModalSustitucion
            jugadorSale={sustituyendoA}
            elegibles={elegibles}
            confirmando={sustitucion.isPending}
            error={sustitucion.isError ? apiErrorMessage(sustitucion.error) : null}
            onCancelar={() => setSustituyendoA(null)}
            onIrAConvocatoria={onIrAConvocatoria}
            onConfirmar={(entraId) =>
              sustitucion.mutate({
                partidos_id: partidoId,
                jugador_id: sustituyendoA.jugador_id,
                equipo_id: sustituyendoA.equipo_id,
                eventos_id: eventoIdPorNombre.get("Cambio") as number,
                jugador_id_entra: entraId,
              })
            }
          />
        );
      })()}

      <section className="card">
        <h2>Eventos cargados</h2>
        {eventosRegistrados.length === 0 && <p>Todavía no hay eventos.</p>}
        {corregirMinutoEvento.isError && <p className="error-text">{apiErrorMessage(corregirMinutoEvento.error)}</p>}
        {eventosRegistrados.length > 0 && (
          <ul className="eventos-timeline">
            {/* T7 (Área 2) + goles-por-marcador-slots-plan.md (Gate Final,
                Alternativa D): el backend ya devuelve ordenado cronológicamente
                (ORDER BY minuto, id — EventoPartidoRepository.list) y se
                renderiza tal cual, ascendente — el usuario eligió esto
                explícitamente en el gate ("el orden siempre debe ser de
                menor a mayor"), revirtiendo el `.reverse()` que antes
                mostraba lo más reciente arriba. */}
            {eventosRegistrados.map((e) => {
              const plantillaTodos = [...(plantillaLocalQuery.data ?? []), ...(plantillaVisitanteQuery.data ?? [])];
              const jugador = plantillaTodos.find((j) => j.jugador_id === e.jugador_id);
              const jugadorEntra = e.jugador_id_entra != null ? plantillaTodos.find((j) => j.jugador_id === e.jugador_id_entra) : undefined;
              const nombreDorsal = (j: PlantillaJugador | undefined, id: number) =>
                j ? `${j.dorsal != null ? `#${j.dorsal} ` : ""}${j.jugador}` : `#${id}`;
              return (
                <EventoTimelineFila
                  key={e.id}
                  evento={e}
                  tipoIcono={TIPO_ICONO[eventoNombrePorId.get(e.eventos_id) as TipoEvento] ?? eventoNombrePorId.get(e.eventos_id) ?? ""}
                  esCambio={eventoNombrePorId.get(e.eventos_id) === "Cambio"}
                  // Fase 1/2 (Timeline visual): nombre de jugador + equipo
                  // en todo hito — antes esta fila no mostraba el equipo.
                  equipoNombre={equipoNombre.get(e.equipo_id) ?? `#${e.equipo_id}`}
                  jugadorNombre={nombreDorsal(jugador, e.jugador_id)}
                  jugadorEntraNombre={e.jugador_id_entra != null ? nombreDorsal(jugadorEntra, e.jugador_id_entra) : null}
                  onCorregir={(minuto) => corregirMinutoEvento.mutate({ id: e.id, minuto })}
                  corrigiendo={corregirMinutoEvento.isPending}
                />
              );
            })}
          </ul>
        )}
      </section>
        </div>
      </div>
    </div>
  );
}


/** Fila de la timeline de eventos con corrección de minuto inline —
 * mismo patrón de ícono de lápiz que Cronometro.tsx usa para sus Hitos,
 * pero es un control DISTINTO (PATCH /eventos-partido/{id}, no
 * /partidos/{id}/hitos/{id}): son dos problemas distintos según el plan
 * ("cargué un gol en el minuto 23 pero fue en el 32" vs. "presioné Fin
 * del 1er Tiempo tarde"). */
function EventoTimelineFila(props: {
  evento: EventoPartidoRow;
  tipoIcono: string;
  esCambio: boolean;
  equipoNombre: string;
  jugadorNombre: string;
  jugadorEntraNombre: string | null;
  onCorregir: (minuto: number) => void;
  corrigiendo: boolean;
}) {
  const { evento, tipoIcono, esCambio, equipoNombre, jugadorNombre, jugadorEntraNombre, onCorregir, corrigiendo } = props;
  const [editando, setEditando] = useState(false);
  const [minuto, setMinuto] = useState(String(evento.minuto));
  const ariaLabel = esCambio
    ? `Minuto ${evento.minuto}, cambio, ${equipoNombre}, sale ${jugadorNombre}, entra ${jugadorEntraNombre ?? ""}`
    : `Minuto ${evento.minuto}, ${equipoNombre}, ${jugadorNombre}`;

  return (
    <li aria-label={editando ? undefined : ariaLabel}>
      {editando ? (
        <>
          <input
            type="number"
            aria-label="Corregir minuto del evento"
            value={minuto}
            onChange={(e) => setMinuto(e.target.value)}
            style={{ width: "3.5rem" }}
            autoFocus
          />
          <button
            type="button"
            disabled={corrigiendo}
            onClick={() => {
              if (minuto !== "") onCorregir(Number(minuto));
              setEditando(false);
            }}
          >
            Guardar
          </button>
          <button type="button" className="link-button" onClick={() => setEditando(false)}>
            Cancelar
          </button>
        </>
      ) : (
        <>
          <span className="eventos-timeline__minuto" aria-hidden="true">
            {evento.minuto}'
          </span>
          <span aria-hidden="true">{tipoIcono}</span>
          <div className="eventos-timeline__detalle" aria-hidden="true">
            <span>{equipoNombre}</span>
            {esCambio ? (
              <span className="muted">
                Sale: {jugadorNombre} <span aria-hidden="true">➔</span> Entra: {jugadorEntraNombre}
              </span>
            ) : (
              <span className="muted">{jugadorNombre}</span>
            )}
          </div>
          <button
            type="button"
            className="link-button"
            aria-label={`Corregir minuto de ${jugadorNombre}`}
            onClick={() => setEditando(true)}
          >
            ✏️
          </button>
        </>
      )}
    </li>
  );
}



interface EventoPartidoRow {
  id: number;
  jugador_id: number;
  jugador_id_entra: number | null;
  equipo_id: number;
  eventos_id: number;
  estado: string;
  minuto: number;
}

// C2b (docs/plans/cierre-pendientes-todos-plan.md): "Cambio" ya NO es un
// tipo elegible acá — el camino vivo es ModalSustitucion, disparado desde
// "Sacar" en Alineación en vivo (con el fallback sin convocatoria de C2a).
// Filtrado en vez de tocar `TIPOS`/`TipoEvento` (eventos.ts): ese tipo
// sigue siendo válido en el resto del sistema (catálogo de eventos,
// timeline, ModalResultadoDirecto), esto es solo la grilla de ESTE form.
const TIPOS_CARGA_EVENTO = TIPOS.filter((t) => t !== "Cambio");

function CargaEvento(props: {
  partidoId: number;
  equipoLocalId: number;
  equipoVisitanteId: number;
  nombreLocal: string;
  nombreVisitante: string;
  plantillaLocal: PlantillaJugador[];
  plantillaVisitante: PlantillaJugador[];
  eventosRegistrados: EventoPartidoRow[];
  eventoIdPorNombre: Map<string, number>;
  eventoNombrePorId: Map<number, string>;
  /** Área 3 (T3): emitido por <Cronometro> — `null` mientras no hay nada
   * que mostrar. El submit queda deshabilitado hasta que llega un valor
   * real (Sección 1 del plan: "deshabilitar botón hasta que Cronometro
   * emita el primer tick", no enviar un evento con minuto adivinado). */
  minutoActual: number | null;
  /** `true` = se resetea el form (carga exitosa O ya se encoló para
   * enviar sola — ver manejarSubmitEvento); `false` = se queda en la
   * pantalla de confirmación mostrando `submitError`, para que el
   * jugador/equipo ya elegidos no se pierdan si el admin solo necesita
   * reintentar. */
  onSubmit: (body: EventoBody) => Promise<boolean>;
  submitting: boolean;
  submitError: string | null;
}) {
  const [tipo, setTipo] = useState<TipoEvento | null>(null);
  const [equipoId, setEquipoId] = useState<number | null>(null);
  const [sale, setSale] = useState<number | null>(null);

  function reset() {
    setTipo(null);
    setEquipoId(null);
    setSale(null);
  }

  const plantillaEquipo = equipoId === props.equipoLocalId ? props.plantillaLocal : props.plantillaVisitante;

  const { salidosOExpulsados } = deriveHistorialElegibilidad(props.eventosRegistrados, props.eventoNombrePorId);

  // Toda la plantilla convocada, menos quien ya salió/fue expulsado — sin
  // distinción titular/suplente (no aplica: un suplente que ya ingresó
  // también puede marcar un gol). Antes esta lista tenía un par
  // `disponiblesParaSalirCambio`/`disponiblesParaEntrar` con la variante
  // titular/suplente — retirado con "Cambio" en C2b, ModalSustitucion es
  // el único camino que necesita esa distinción.
  const disponiblesParaSalir = plantillaEquipo.filter((j) => !salidosOExpulsados.has(j.jugador_id));

  async function handleConfirmar() {
    if (!tipo || !equipoId || sale === null || props.minutoActual === null) return;
    // Espera el resultado antes de resetear — un `reset()` inmediato (sin
    // esperar) le hacía desaparecer la pantalla de confirmación (y con
    // ella `submitError`) apenas se hacía clic, así que un rechazo real
    // del backend nunca se llegaba a ver: el form ya había vuelto al
    // primer paso antes de que la respuesta volviera.
    const exito = await props.onSubmit({
      partidos_id: props.partidoId,
      jugador_id: sale,
      equipo_id: equipoId,
      eventos_id: props.eventoIdPorNombre.get(tipo) as number,
      jugador_id_entra: null,
      // Sin `minuto`: el servidor lo calcula siempre para este camino (en
      // vivo) — ver el comentario de EventoBody.minuto.
    });
    if (exito) reset();
  }

  const puedeConfirmar = tipo !== null && equipoId !== null && sale !== null && props.minutoActual !== null;

  return (
    <section className="card carga-evento">
      <h2>Cargar evento</h2>

      {!tipo && (
        <div className="tap-grid">
          {TIPOS_CARGA_EVENTO.map((t) => (
            <button key={t} type="button" className="tap-button" onClick={() => setTipo(t)}>
              <span className="tap-button__icon">{TIPO_ICONO[t]}</span>
              {t}
            </button>
          ))}
        </div>
      )}

      {tipo && !equipoId && (
        <div className="tap-grid">
          <button type="button" className="tap-button" onClick={() => setEquipoId(props.equipoLocalId)}>
            {props.nombreLocal}
          </button>
          <button type="button" className="tap-button" onClick={() => setEquipoId(props.equipoVisitanteId)}>
            {props.nombreVisitante}
          </button>
          <button type="button" className="link-button" onClick={reset}>← {tipo}</button>
        </div>
      )}

      {tipo && equipoId && sale === null && (
        <div className="tap-grid">
          {disponiblesParaSalir.map((j) => (
            <button key={j.jugador_id} type="button" className="tap-button" onClick={() => setSale(j.jugador_id)}>
              {j.dorsal ? `#${j.dorsal} ` : ""}{j.jugador}
            </button>
          ))}
          {disponiblesParaSalir.length === 0 && <p>No hay jugadores disponibles en la plantilla.</p>}
          <button type="button" className="link-button" onClick={() => setEquipoId(null)}>← Cambiar equipo</button>
        </div>
      )}

      {tipo && equipoId && sale !== null && (
        <div className="confirmar-evento">
          {/* Área 3 (T3): ya no se pide a mano — el minuto sale del
              cronómetro en vivo (mismo dato que va a calcular el servidor,
              ver EventoPartidoService._minuto_en_vivo). Sin input: mostrarlo
              como editable invitaría a "corregirlo" antes de mandar, y el
              servidor lo va a ignorar igual. */}
          <p className="carga-evento__minuto">
            {props.minutoActual !== null
              ? <>Minuto <strong>{props.minutoActual}'</strong> (del cronómetro)</>
              : "Esperando el cronómetro…"}
          </p>
          {props.submitError && <p className="error-text">{props.submitError}</p>}
          <div className="confirmar-evento__acciones">
            <button type="button" onClick={reset} className="link-button">Cancelar</button>
            <button type="button" onClick={handleConfirmar} disabled={!puedeConfirmar || props.submitting}>
              {props.submitting ? "Guardando..." : "Confirmar"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
