import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { MesaPanel } from "../../components/MesaPanel";
import { useEmpezarPartido } from "../../components/useEmpezarPartido";
import { useNombrePorIdConFaltantes } from "../../hooks/useFetchFaltantes";
import { useOnlineStatus } from "../../hooks/useOnlineStatus";
import { AccionWalkoverMesa } from "./AccionWalkoverMesa";
import { AlineacionEditor } from "./AlineacionEditor";
import { EditorFechaPartido } from "./EditorFechaPartido";
import { ModalResultadoDirecto } from "./ModalResultadoDirecto";
import {
  type JugadorPlantilla,
  type Seleccion,
  hayCambios,
  seleccionDesdeConvocados,
  seleccionInicial,
} from "./alineacion";

/** Distingue "no hay red" de "el backend rechazó la request" — mismo criterio
 * que `MesaPanel`: `fetch` tira `TypeError` cuando no llega a conectar, un
 * 4xx/5xx real sí resuelve una Response. Sin esto, un error de red produce
 * basura al pasarlo por `apiErrorMessage`. */
function esErrorDeRed(error: unknown): boolean {
  return error instanceof TypeError;
}

function claveBorrador(partidoId: number) {
  return `alineacionBorrador:${partidoId}`;
}

interface ConvocadoRow {
  id: number;
  jugador_perfil_id: number;
  titular: boolean;
  fecha_modificacion?: string | null;
}

/** Vista inmersiva de UN partido: convocatoria, alineación y las dos acciones
 * de ejecución.
 *
 * Es una RUTA y no un panel por `useState` a propósito: el panel viejo no tenía
 * URL, así que el botón Atrás del navegador salía del módulo entero y un
 * refresh en pleno partido devolvía al operador a la lista. También es lo que
 * rompe el deadlock que motivó todo este trabajo: antes, para llegar a la
 * convocatoria había que entrar al panel, y al panel solo se entraba con el
 * partido ya empezado — pero para empezarlo hacía falta la convocatoria.
 */
export function GestionarPartidoPage() {
  const { partidoId } = useParams<{ partidoId: string }>();
  const id = Number(partidoId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const online = useOnlineStatus();

  const [seleccion, setSeleccion] = useState<Seleccion | null>(null);
  const [equipoActivo, setEquipoActivo] = useState<"local" | "visitante">("local");
  const [resultadoDirectoAbierto, setResultadoDirectoAbierto] = useState(false);
  const [borradorDisponible, setBorradorDisponible] = useState(false);

  const partidoQuery = useQuery({
    queryKey: ["partido", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}", {
        params: { path: { partido_id: id } },
      });
      if (error) throw error;
      return data;
    },
    enabled: Number.isFinite(id),
  });
  const partido = partidoQuery.data;

  // Cierre de Fase Regular + Llaves + Playoffs (Fase E4/D8, Design
  // review — CRÍTICO): los controles de carga se deshabilitan ANTES del
  // intento, nunca fallan después — un operador que toca "Empezar
  // Partido"/"Cargar resultado directo" en un torneo cerrado tiene que
  // ver el control ya bloqueado, no un 400 crudo del trigger. En la
  // práctica `cerrado` (partido.estado Finalizado/Cancelado) ya cubre
  // casi todos los casos (cerrar_torneo exige que TODOS los partidos de
  // la fase ya estén terminados) — el hueco real es un partido creado a
  // mano DESPUÉS del cierre (el guard de escritura no bloquea el INSERT,
  // solo el UPDATE), que quedaría "Programado" para siempre sin este chequeo.
  const torneoQuery = useQuery({
    queryKey: ["torneo", partido?.torneo_id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}", {
        params: { path: { torneo_id: partido!.torneo_id } },
      } as never);
      if (error) throw error;
      return data as { estado: string; fecha_cierre: string | null };
    },
    enabled: partido != null,
  });
  const torneoCerrado = torneoQuery.data?.estado === "Finalizado";

  const convocadosQuery = useQuery({
    queryKey: ["convocados", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/convocados", {
        params: { path: { partido_id: id } },
      });
      if (error) throw error;
      return data as ConvocadoRow[];
    },
    enabled: Number.isFinite(id),
  });

  // El veredicto de arranque lo calcula y publica el backend: el frontend no
  // reimplementa la regla. Antes existía `useTitularesCompletos`, una réplica
  // client-side de la misma validación que corría 6 queries POR FILA del
  // dashboard y podía divergir del servidor (botón habilitado, POST rechazado).
  // Es un endpoint propio y autenticado, no un campo de `/cronometro`: ese es
  // público y se pollea cada 5s de forma anónima.
  const preflightQuery = useQuery({
    queryKey: ["preflight-inicio", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/preflight-inicio", {
        params: { path: { partido_id: id } },
      } as never);
      if (error) throw error;
      return data as {
        minimo_para_iniciar: number;
        maximo_titulares: number;
        titulares_por_equipo: { equipo_id: number; nombre: string; titulares: number }[];
        puede_iniciar: boolean;
        motivo_bloqueo: string | null;
        partido_iniciado: boolean;
      };
    },
    enabled: Number.isFinite(id),
  });

  const cronometroQuery = useQuery({
    queryKey: ["cronometro", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/cronometro", {
        params: { path: { partido_id: id } },
      });
      if (error) throw error;
      return data as { tipo_cronometro: "Periodos" | "Corrido"; partido_iniciado: boolean };
    },
    enabled: Number.isFinite(id),
  });

  // Plantilla por `/estadisticas/equipos/{id}/plantilla?torneo_id=`, NO por
  // `GET /plantillas` (H2-eng del plan): `/plantillas` devuelve
  // `JugadorEquipoOut`, que no trae el NOMBRE del jugador ni `equipo_id`, y
  // además incluye las filas Traspasado/Inactivo del roster. Alimentar el
  // editor con eso daba una lista de jugadores sin nombre, con bajas y
  // traspasados adentro, y con el mismo `jugador_perfil_id` repetido en los
  // dos equipos cuando había un traspaso entre ellos (keys de React
  // duplicadas). `torneo_id` acota al roster de ESTE torneo.
  const equipoLocalId = partido?.equipos_id_local;
  const equipoVisitanteId = partido?.equipos_id_visitante;

  const plantillaLocalQuery = useQuery({
    queryKey: ["plantilla-equipo", equipoLocalId, partido?.torneo_id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: equipoLocalId as number }, query: { torneo_id: partido!.torneo_id } },
      } as never);
      if (error) throw error;
      return data as unknown as JugadorPlantilla[];
    },
    enabled: equipoLocalId != null && partido != null,
  });
  const plantillaVisitanteQuery = useQuery({
    queryKey: ["plantilla-equipo", equipoVisitanteId, partido?.torneo_id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: equipoVisitanteId as number }, query: { torneo_id: partido!.torneo_id } },
      } as never);
      if (error) throw error;
      return data as unknown as JugadorPlantilla[];
    },
    enabled: equipoVisitanteId != null && partido != null,
  });

  const equiposQuery = useQuery({
    queryKey: ["equipos-mesa"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/equipos", { params: { query: { limit: 200 } } } as never);
      if (error) throw error;
      return data as { id: number; nombre: string }[];
    },
    staleTime: 5 * 60 * 1000,
  });
  const nombreEquipoBase = useMemo(
    () => new Map((equiposQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equiposQuery.data],
  );
  const nombreEquipo = useNombrePorIdConFaltantes(
    "/api/v1/equipos",
    nombreEquipoBase,
    partido ? [partido.equipos_id_local, partido.equipos_id_visitante] : [],
  );
  const nombreTorneo = useNombrePorIdConFaltantes(
    "/api/v1/torneos",
    new Map<number, string>(),
    partido ? [partido.torneo_id] : [],
  );

  const plantillaCompleta = useMemo(
    () => [...(plantillaLocalQuery.data ?? []), ...(plantillaVisitanteQuery.data ?? [])],
    [plantillaLocalQuery.data, plantillaVisitanteQuery.data],
  );

  const guardada = useMemo(
    () => seleccionDesdeConvocados(convocadosQuery.data ?? []),
    [convocadosQuery.data],
  );

  /** Las dos plantillas ya resolvieron (con datos o con error). Un equipo sin
   * definir no cuenta: su query nunca corre. */
  const plantillasResueltas =
    (equipoLocalId == null || !plantillaLocalQuery.isPending) &&
    (equipoVisitanteId == null || !plantillaVisitanteQuery.isPending);

  // Inicialización: borrador local si hay, si no lo guardado, si no el default
  // invertido (toda la plantilla convocada, el operador destilda ausentes).
  //
  // La condición es "las plantillas RESOLVIERON", no "la plantilla tiene
  // filas": con `plantillaCompleta.length === 0` un roster vacío dejaba
  // `seleccion` en null para siempre y el editor —que se renderiza solo si
  // `seleccion != null`— no aparecía nunca, ni siquiera para decir que el
  // roster estaba vacío.
  useEffect(() => {
    if (seleccion != null || !plantillasResueltas || convocadosQuery.data == null) return;
    try {
      const crudo = localStorage.getItem(claveBorrador(id));
      if (crudo) {
        const entradas = JSON.parse(crudo) as [number, boolean][];
        setSeleccion(new Map(entradas));
        setBorradorDisponible(true);
        return;
      }
    } catch {
      // localStorage puede fallar (modo privado, cuota): no es motivo para no
      // poder armar la alineación.
    }
    setSeleccion(seleccionInicial(convocadosQuery.data, plantillaCompleta));
  }, [seleccion, plantillasResueltas, plantillaCompleta, convocadosQuery.data, id]);

  const cambiosSinGuardar = seleccion != null && hayCambios(guardada, seleccion);

  // Persistir el borrador en cada movimiento: la ruta nueva hace que el botón
  // Atrás, el swipe de borde de iOS o un bloqueo de pantalla puedan sacar al
  // operador de la vista, y sin esto perdería la alineación armada de memoria.
  useEffect(() => {
    if (seleccion == null) return;
    try {
      if (cambiosSinGuardar) localStorage.setItem(claveBorrador(id), JSON.stringify([...seleccion]));
      else localStorage.removeItem(claveBorrador(id));
    } catch {
      /* sin borrador local; el resto sigue funcionando */
    }
  }, [seleccion, cambiosSinGuardar, id]);

  // Protección de trabajo sin guardar.
  //
  // El plan pedía `useBlocker` de react-router, pero NO se puede usar acá:
  // `useBlocker` exige un data router (`createBrowserRouter`) y la app monta
  // `BrowserRouter` (main.tsx), así que tirar de él rompería la pantalla en
  // producción, no solo en los tests. Migrar toda la app a data router es un
  // cambio de otra escala y de otro alcance.
  //
  // Lo que sí cubre los casos reales, sin tocar el router:
  //  - `beforeunload` para refresh, cerrar pestaña y salir del sitio;
  //  - confirmación explícita en el botón "Volver", que es navegación propia;
  //  - y sobre todo el borrador en localStorage, que es la red de seguridad de
  //    verdad: si el operador igual se va (un link de la nav, el gesto de atrás
  //    del sistema), al volver a la pantalla se le ofrece retomar lo que había
  //    armado. Nada se pierde en silencio.
  useEffect(() => {
    if (!cambiosSinGuardar) return;
    const alSalir = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", alSalir);
    return () => window.removeEventListener("beforeunload", alSalir);
  }, [cambiosSinGuardar]);

  function volverALista() {
    if (cambiosSinGuardar && !window.confirm("Tenés la alineación sin guardar. ¿Salir igual? Queda guardada en este dispositivo.")) {
      return;
    }
    navigate("/control-de-mesa");
  }

  const version = useMemo(() => {
    const fechas = (convocadosQuery.data ?? [])
      .map((c) => c.fecha_modificacion)
      .filter((f): f is string => !!f)
      .sort();
    return fechas.length ? fechas[fechas.length - 1] : null;
  }, [convocadosQuery.data]);

  const guardar = useMutation({
    mutationFn: async () => {
      const convocados = [...(seleccion ?? new Map())].map(([jugador_perfil_id, titular]) => ({
        jugador_perfil_id,
        titular,
      }));
      const { data, error } = await api.PUT("/api/v1/partidos/{partido_id}/convocados", {
        params: { path: { partido_id: id } },
        body: { convocados, version },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      try {
        localStorage.removeItem(claveBorrador(id));
      } catch {
        /* ignorado */
      }
      setBorradorDisponible(false);
      queryClient.invalidateQueries({ queryKey: ["convocados", id] });
      queryClient.invalidateQueries({ queryKey: ["preflight-inicio", id] });
    },
  });

  const sumarTardio = useMutation({
    mutationFn: async (perfilId: number) => {
      const { data, error } = await api.POST("/api/v1/partidos/{partido_id}/convocados", {
        params: { path: { partido_id: id } },
        body: { jugador_perfil_id: perfilId, titular: false },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["convocados", id] });
      // La selección local se re-sincroniza con lo guardado: el alta aditiva ya
      // quedó persistida, no es un cambio pendiente.
      setSeleccion(null);
    },
  });

  const empezar = useEmpezarPartido(Number.isFinite(id) ? id : null);

  if (!Number.isFinite(id)) return <div className="page"><p className="error-text">Partido inválido.</p></div>;
  if (partidoQuery.isLoading) return <div className="page"><p>Cargando partido…</p></div>;
  if (partidoQuery.isError || !partido) {
    return (
      <div className="page">
        <button type="button" className="link-button" onClick={volverALista}>
          ← Volver a la lista
        </button>
        <p className="error-text">No se pudo cargar el partido.</p>
        <button type="button" onClick={() => partidoQuery.refetch()}>Reintentar</button>
      </div>
    );
  }

  const enCurso = cronometroQuery.data?.partido_iniciado ?? preflightQuery.data?.partido_iniciado ?? false;
  const cerrado = partido.estado === "Finalizado" || partido.estado === "Cancelado";
  // Bloqueo efectivo para las acciones de escritura — ver el comentario
  // grande más arriba sobre por qué `cerrado` (a nivel partido) no
  // alcanza para el caso borde de un partido creado DESPUÉS del cierre.
  const bloqueado = cerrado || torneoCerrado;
  const sinRival = partido.equipos_id_local == null || partido.equipos_id_visitante == null;
  const nombreLocal =
    partido.equipos_id_local != null ? nombreEquipo.get(partido.equipos_id_local) ?? `#${partido.equipos_id_local}` : "?";
  const nombreVisitante =
    partido.equipos_id_visitante != null
      ? nombreEquipo.get(partido.equipos_id_visitante) ?? `#${partido.equipos_id_visitante}`
      : "?";

  const plantillaActivaQuery = equipoActivo === "local" ? plantillaLocalQuery : plantillaVisitanteQuery;
  const plantillaActiva = plantillaActivaQuery.data ?? [];
  const preflight = preflightQuery.data;
  const minimo = preflight?.minimo_para_iniciar ?? 0;
  // Área 1 (T2): sin preflight cargado todavía, un tope en 0 bloquearía
  // cualquier movimiento a Titulares — Infinity es el "sin restricción
  // conocida todavía" correcto acá (a diferencia de `minimo`, donde 0 sí
  // es el default seguro).
  const maximo = preflight?.maximo_titulares ?? Number.POSITIVE_INFINITY;

  function titularesDe(equipoId: number | null | undefined): number | null {
    if (equipoId == null) return null;
    return preflight?.titulares_por_equipo.find((t) => t.equipo_id === equipoId)?.titulares ?? null;
  }

  return (
    <div className="page gestionar-partido">
      <div className="gestionar-partido__header">
        <button type="button" className="link-button" onClick={volverALista}>
          ← Volver
        </button>
        <div>
          <h1>
            {nombreLocal} vs {nombreVisitante}
          </h1>
          {/* El torneo en el header: la vista es deep-linkeable, así que sin
              esto un operador que abre un link guardado no sabe de qué torneo
              es el partido. */}
          <p className="muted">
            {nombreTorneo.get(partido.torneo_id) ?? `Torneo #${partido.torneo_id}`} ·{" "}
            {new Date(partido.fecha_partido).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}
          </p>
        </div>
        <span className={`badge badge--${partido.estado.replace(" ", "-").toLowerCase()}`}>{partido.estado}</span>
      </div>

      {!online && <p className="muted mesa-offline-aviso">Sin conexión — lo que armes se guarda en este dispositivo.</p>}

      {torneoCerrado && (
        <p className="banner-info-persistente" aria-live="polite">
          Torneo cerrado
          {torneoQuery.data?.fecha_cierre ? ` el ${new Date(torneoQuery.data.fecha_cierre).toLocaleDateString("es-AR")}` : ""} —
          los resultados están bloqueados.
        </p>
      )}

      {borradorDisponible && cambiosSinGuardar && (
        <div className="card">
          <p>Tenés una alineación sin guardar en este dispositivo.</p>
          <button type="button" onClick={() => guardar.mutate()}>Retomar y guardar</button>
          <button
            type="button"
            className="link-button"
            onClick={() => {
              try {
                localStorage.removeItem(claveBorrador(id));
              } catch {
                /* ignorado */
              }
              setBorradorDisponible(false);
              setSeleccion(seleccionInicial(convocadosQuery.data ?? [], plantillaCompleta));
            }}
          >
            Descartar
          </button>
        </div>
      )}

      {/* Banda de modo: sin una señal persistente el operador no sabe si el
          reloj corre, y edita creyendo que no afecta nada. */}
      {enCurso && (
        <div className="banda-en-curso">
          <strong>Partido en curso</strong> — el cronómetro sigue corriendo. Solo podés sumar suplentes.
        </div>
      )}

      {sinRival ? (
        <p className="muted">
          Este partido todavía no tiene los dos equipos definidos — esperá a que termine el partido anterior del bracket.
        </p>
      ) : cerrado ? (
        <p className="muted">Este partido está {partido.estado.toLowerCase()} — la alineación quedó cerrada.</p>
      ) : torneoCerrado ? (
        <p className="muted">El torneo está cerrado — la alineación quedó bloqueada.</p>
      ) : (
        <>
          <div className="selector-equipo" role="tablist">
            {(["local", "visitante"] as const).map((lado) => {
              const equipoId = lado === "local" ? partido.equipos_id_local : partido.equipos_id_visitante;
              const n = titularesDe(equipoId);
              return (
                <button
                  key={lado}
                  type="button"
                  role="tab"
                  aria-selected={equipoActivo === lado}
                  className={equipoActivo === lado ? "selector-equipo__tab selector-equipo__tab--activo" : "selector-equipo__tab"}
                  onClick={() => setEquipoActivo(lado)}
                >
                  {lado === "local" ? nombreLocal : nombreVisitante}
                  {n != null && minimo > 0 ? ` ${n}/${minimo}` : ""}
                </button>
              );
            })}
          </div>

          {/* Un fallo de carga tiene que VERSE. Antes el editor se renderizaba
              solo con `seleccion != null` y no había ninguna otra rama: si
              `GET /convocados` fallaba (por ejemplo con la migración 25 sin
              aplicar, que era el caso real), `seleccion` quedaba en null y la
              pantalla mostraba el header, las pestañas de equipo y nada más —
              indistinguible de "todavía está cargando". El error se lee por
              query, así que un equipo que falla no se lleva puesto al otro. */}
          {convocadosQuery.isError ? (
            <div className="card">
              <p className="error-text">No se pudo cargar la convocatoria de este partido.</p>
              <button type="button" onClick={() => convocadosQuery.refetch()}>
                Reintentar
              </button>
            </div>
          ) : plantillaActivaQuery.isError ? (
            <div className="card">
              <p className="error-text">
                No se pudo cargar la plantilla de {equipoActivo === "local" ? nombreLocal : nombreVisitante}.
              </p>
              <button type="button" onClick={() => plantillaActivaQuery.refetch()}>
                Reintentar
              </button>
            </div>
          ) : seleccion == null ? (
            <p className="muted">Cargando plantilla…</p>
          ) : (
            <AlineacionEditor
              plantilla={plantillaActiva}
              seleccion={seleccion}
              onCambiar={setSeleccion}
              minimo={minimo}
              maximo={maximo}
              enCurso={enCurso}
              onSumarTardio={(perfilId) => sumarTardio.mutate(perfilId)}
              sumandoTardio={sumarTardio.isPending}
            />
          )}

          {guardar.isError && (
            <p className="error-text">
              {esErrorDeRed(guardar.error)
                ? "Sin conexión — no se perdió nada, reintentá cuando vuelva la señal."
                : apiErrorMessage(guardar.error)}
            </p>
          )}
          {sumarTardio.isError && <p className="error-text">{apiErrorMessage(sumarTardio.error)}</p>}

          {!enCurso && (
            <div className="confirmar-evento__acciones">
              <button type="button" disabled={!cambiosSinGuardar || guardar.isPending} onClick={() => guardar.mutate()}>
                {guardar.isPending ? "Guardando…" : online ? "Guardar alineación" : "Guardar cuando vuelva la señal"}
              </button>
            </div>
          )}
        </>
      )}

      {!bloqueado && !sinRival && (
        <div className="gestionar-partido__acciones">
          {!enCurso && (
            <>
              {/* aria-disabled + describedby en vez de `disabled`: un botón
                  deshabilitado no es focusable ni anunciable, y el motivo no
                  puede vivir en un `title` porque en touch no existe. */}
              <p id="motivo-inicio" className="muted">
                {cambiosSinGuardar
                  ? "Tenés cambios sin guardar en la alineación."
                  : preflight?.motivo_bloqueo ?? "Todo listo para arrancar."}
              </p>
              <button
                type="button"
                aria-disabled={!preflight?.puede_iniciar || cambiosSinGuardar || empezar.isPending}
                aria-describedby="motivo-inicio"
                onClick={() => {
                  if (!preflight?.puede_iniciar || cambiosSinGuardar || empezar.isPending) return;
                  empezar.mutate(cronometroQuery.data?.tipo_cronometro ?? "Periodos");
                }}
              >
                {empezar.isPending ? "Iniciando…" : "▶ Empezar Partido"}
              </button>
              <button type="button" className="link-button" onClick={() => setResultadoDirectoAbierto(true)}>
                Cargar resultado directo
              </button>
            </>
          )}
          {empezar.isError && <p className="error-text">{apiErrorMessage(empezar.error)}</p>}
        </div>
      )}

      {/* Walkover y reprogramación se mudaron acá desde la fila del dashboard:
          colapsar la fila a un botón sin reubicarlas habría hecho desaparecer
          de la UI una decisión tomada a propósito. Van plegadas, sin competir
          con las dos acciones principales. */}
      <details className="gestionar-partido__otras">
        <summary>Otras acciones</summary>
        {!enCurso && !bloqueado && (
          <EditorFechaPartido
            partidoId={partido.id}
            fechaActual={partido.fecha_partido}
            onGuardar={(fecha) => {
              api
                .PATCH("/api/v1/partidos/{partido_id}", {
                  params: { path: { partido_id: partido.id } },
                  body: { fecha_partido: fecha },
                } as never)
                .then(() => queryClient.invalidateQueries({ queryKey: ["partido", id] }));
            }}
            guardando={false}
          />
        )}
        {enCurso && (
          // Reprogramar con eventos ya cargados los dejaría inconsistentes: el
          // trigger que valida pertenencia mira la fecha del partido, pero es
          // BEFORE INSERT sobre EVENTOS_PARTIDO, no sobre PARTIDOS, así que
          // mover la fecha hacia atrás no revalida nada de lo ya cargado.
          <p className="muted">La fecha no se puede cambiar con el partido en curso.</p>
        )}
        {!bloqueado && partido.equipos_id_local != null && partido.equipos_id_visitante != null && (
          <AccionWalkoverMesa
            equipoLocalId={partido.equipos_id_local}
            equipoVisitanteId={partido.equipos_id_visitante}
            nombreLocal={nombreLocal}
            nombreVisitante={nombreVisitante}
            marcando={false}
            onMarcar={(equipoAusenteId) => {
              api
                .POST("/api/v1/partidos/{partido_id}/walkover", {
                  params: { path: { partido_id: partido.id } },
                  body: { equipo_ausente_id: equipoAusenteId },
                } as never)
                .then(() => {
                  queryClient.invalidateQueries({ queryKey: ["partido", id] });
                  queryClient.invalidateQueries({ queryKey: ["partidos-mesa"] });
                });
            }}
          />
        )}
      </details>

      {/* Panel en vivo: marcador, cronómetro, carga de eventos y timeline.
          Sin su propio botón de "volver" ni de inicio: la navegación y el
          arranque los maneja esta página. */}
      {enCurso && <MesaPanel partidoId={id} />}

      {resultadoDirectoAbierto && partido.equipos_id_local != null && partido.equipos_id_visitante != null && (
        <ModalResultadoDirecto
          partido={{
            id: partido.id,
            equipos_id_local: partido.equipos_id_local,
            equipos_id_visitante: partido.equipos_id_visitante,
            ronda_nombre: partido.ronda_nombre ?? null,
            elegible_desempate: partido.elegible_desempate,
            goles_previos_global_local: partido.goles_previos_global_local,
            goles_previos_global_visitante: partido.goles_previos_global_visitante,
          }}
          nombreEquipo={nombreEquipo}
          onClose={() => setResultadoDirectoAbierto(false)}
          onGuardado={() => {
            queryClient.invalidateQueries({ queryKey: ["partido", id] });
            queryClient.invalidateQueries({ queryKey: ["partidos-mesa"] });
            setResultadoDirectoAbierto(false);
            // control-mesa-reactividad-playoffs-plan.md, Fase 1/2/3 §8:
            // redirect a la vista pública del partido — el operador puede
            // verificar de inmediato que los datos se renderizan bien para
            // el usuario final, en vez de quedarse en /control-de-mesa
            // confiando a ciegas en que el guardado salió bien.
            navigate(`/partidos/${id}`);
          }}
        />
      )}

    </div>
  );
}
