import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import type { Equipo as EquipoRow } from "../../../api/types";
import { api, apiErrorMessage } from "../../../api/client";
import { ResourceTable } from "../../../components/admin/ResourceTable";
import { SelectorJugadorBuscable, type JugadorBuscadoRow } from "../../../components/admin/SelectorJugadorBuscable";
import { LIMITE_LISTA, useResourceCrud } from "../../../hooks/useResourceCrud";
import { useEtiquetaJugadorPorPerfil } from "../../../hooks/useEtiquetaJugadorPorPerfil";
import { useNombrePorIdConFaltantes } from "../../../hooks/useFetchFaltantes";
import type { TorneoDashboardContext } from "./TorneoDashboard";

interface TraspasoRow {
  id: number;
  jugador_perfil_id: number;
  inscripcion_origen_id: number | null;
  inscripcion_destino_id: number;
  motivo: string | null;
  fecha_traspaso: string;
  estado: string;
  // fixes-datos-traspasos-control-mesa-plan.md: computado por el backend
  // (TraspasoService._puede_anularse) — False una vez que el club destino
  // ya arrancó un partido desde este traspaso, o si ya está Anulado.
  puede_anularse: boolean;
}
interface JugadorRow {
  id: number;
  nombre: string;
}
interface PerfilRow {
  id: number;
  jugador_id: number;
}
interface InscripcionRow {
  id: number;
  equipo_id: number;
}
interface PlantillaHistRow {
  id: number;
  inscripcion_torneo_id: number;
  dorsal: number | null;
  estado: string;
}

type Modo = { tipo: "lista" } | { tipo: "crear" };

const formatearFecha = (iso: string) => new Date(iso).toLocaleString("es-AR");

/** D3 (fixes-datos-traspasos-control-mesa-plan.md): jugador activo en ESTE
 * torneo → equipo de origen; sin membresía activa → "Agencia Libre" (texto
 * literal, no vacío — Flujo 2, Estados de interacción). `GET /plantillas`
 * ya acepta `jugador_perfil_id` + `torneo_id` juntos (P7 del plan), sin
 * backend nuevo. */
function useOrigenActualDelPerfil(
  perfilId: number | null,
  torneoId: number,
  nombreEquipoDeInscripcion: (inscripcionId: number) => string,
) {
  const query = useQuery({
    queryKey: ["plantillas", "historial-torneo", perfilId, torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/plantillas", {
        params: { query: { jugador_perfil_id: perfilId as number, torneo_id: torneoId } },
      });
      if (error) throw error;
      return data as PlantillaHistRow[];
    },
    enabled: perfilId != null,
  });
  // EC-Tr3 del plan: si hubiera más de una fila Activo (no debería, la
  // exclusividad de torneo lo impide) se toma la primera — un dato
  // inconsistente ahí ya rompería otras partes del sistema, no es algo
  // que este hook deba resolver.
  const activa = (query.data ?? []).find((p) => p.estado === "Activo") ?? null;
  return {
    isLoading: perfilId != null && query.isLoading,
    inscripcionOrigenId: activa?.inscripcion_torneo_id ?? null,
    etiqueta: activa ? nombreEquipoDeInscripcion(activa.inscripcion_torneo_id) : "Agencia Libre",
  };
}

/** D3: historial de dorsales del jugador en CUALQUIER torneo — mismo
 * endpoint sin `torneo_id` (P7). Deduplica, ignora `null`. */
function useDorsalesHistoricos(perfilId: number | null): number[] {
  const query = useQuery({
    queryKey: ["plantillas", "historial-jugador", perfilId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/plantillas", {
        params: { query: { jugador_perfil_id: perfilId as number } },
      });
      if (error) throw error;
      return data as PlantillaHistRow[];
    },
    enabled: perfilId != null,
  });
  return useMemo(() => {
    const set = new Set<number>();
    for (const p of query.data ?? []) if (p.dorsal != null) set.add(p.dorsal);
    return [...set];
  }, [query.data]);
}

/** Sub-pestaña "Traspasos" del dashboard scoped — mismo alcance funcional
 * que la extinta pestaña global TraspasosAdmin.tsx (Fase 3: consolidación),
 * pero el Jugador y los pickers de origen/destino se filtran a la
 * disciplina y al torneo de ESTA edición: un perfil de otra disciplina no
 * tiene sentido como candidato acá.
 *
 * Requerimiento A / D3 (fixes-datos-traspasos-control-mesa-plan.md): el
 * jugador se busca por nombre/cédula (SelectorJugadorBuscable, mismo
 * `?q=` que la Plantilla Base) en vez de un `<select>` con IDs crudos, el
 * origen se autocompleta (no lo elige el operador) y el dorsal ofrece el
 * historial del jugador como sugerencia con un clic. */
export function TraspasosDelTorneoPage() {
  const { torneoId, disciplinaId, torneoContexto } = useOutletContext<TorneoDashboardContext>();
  const queryClient = useQueryClient();
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });

  const crud = useResourceCrud<TraspasoRow>({
    resourceKey: "traspasos",
    basePath: "/api/v1/traspasos",
    listParams: { torneo_id: torneoId },
  });
  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });
  const perfiles = useResourceCrud<PerfilRow, { jugador_id: number; disciplina_id: number }>({
    resourceKey: "perfiles",
    basePath: "/api/v1/perfiles",
    listParams: { disciplina_id: disciplinaId },
  });
  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
    listParams: { torneo_id: torneoId },
  });
  // Bug 2 (D2, parte C): solo equipos de esta disciplina — mismo criterio
  // que EquiposDelTorneo.tsx, reduce la ventana de LIMITE_LISTA.
  const equipos = useResourceCrud<EquipoRow>({
    resourceKey: "equipos",
    basePath: "/api/v1/equipos",
    listParams: { disciplina_id: disciplinaId },
  });

  const nombreJugadorBase = useMemo(
    () => new Map((jugadores.listQuery.data ?? []).map((j) => [j.id, j.nombre])),
    [jugadores.listQuery.data],
  );
  const nombreEquipoBase = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );
  // Bug 2 (D2, parte B): resolución dirigida para IDs fuera de la ventana
  // de LIMITE_LISTA — sin esto, un equipo/perfil recién creado en un
  // entorno con muchas filas previas se veía como "#ID"/"Perfil #ID"
  // aunque el nombre real estuviera perfecto en la base (P3 del plan).
  const nombreEquipo = useNombrePorIdConFaltantes(
    "/api/v1/equipos",
    nombreEquipoBase,
    (inscripciones.listQuery.data ?? []).map((i) => i.equipo_id),
  );
  const perfilPorId = useMemo(
    () => new Map((perfiles.listQuery.data ?? []).map((p) => [p.id, p])),
    [perfiles.listQuery.data],
  );
  const etiquetaJugador = useEtiquetaJugadorPorPerfil(
    (crud.listQuery.data ?? []).map((t) => t.jugador_perfil_id),
    perfilPorId,
    nombreJugadorBase,
  );
  const nombreEquipoDeInscripcion = useMemo(() => {
    const inscripcionAEquipo = new Map((inscripciones.listQuery.data ?? []).map((i) => [i.id, i.equipo_id]));
    return (inscripcionId: number | null) =>
      inscripcionId == null ? "Agencia libre" : (nombreEquipo.get(inscripcionAEquipo.get(inscripcionId) ?? -1) ?? `#${inscripcionId}`);
  }, [inscripciones.listQuery.data, nombreEquipo]);

  function volver() {
    setModo({ tipo: "lista" });
  }

  if (modo.tipo === "crear") {
    return (
      <FormularioNuevoTraspaso
        torneoId={torneoId}
        disciplinaId={disciplinaId}
        torneoContexto={torneoContexto}
        inscripciones={inscripciones.listQuery.data ?? []}
        inscripcionesLoading={inscripciones.listQuery.isLoading}
        nombreEquipoDeInscripcion={(id) => nombreEquipoDeInscripcion(id)}
        perfiles={perfiles}
        onCrear={(body) =>
          crud.create.mutateAsync(body as never).then(() => {
            queryClient.invalidateQueries({ queryKey: ["plantillas"] });
            volver();
          })
        }
        creando={crud.create.isPending}
        errorCrear={crud.create.isError ? apiErrorMessage(crud.create.error) : null}
        onCancel={volver}
      />
    );
  }

  return (
    <div>
      <div className="page__header">
        <h2>Traspasos de esta edición</h2>
        <button type="button" onClick={() => setModo({ tipo: "crear" })}>
          + Nuevo traspaso
        </button>
      </div>
      {crud.customAction.isError && <p className="error-text">{apiErrorMessage(crud.customAction.error)}</p>}
      {crud.truncado && (
        <p className="muted">Mostrando los primeros {LIMITE_LISTA} traspasos de esta edición.</p>
      )}
      <ResourceTable<TraspasoRow>
        rows={crud.listQuery.data ?? []}
        columns={[
          { key: "fecha", label: "Fecha", render: (r) => formatearFecha(r.fecha_traspaso) },
          { key: "jugador", label: "Jugador", render: (r) => etiquetaJugador(r.jugador_perfil_id) },
          {
            key: "movimiento",
            label: "Origen → Destino",
            render: (r) => `${nombreEquipoDeInscripcion(r.inscripcion_origen_id)} → ${nombreEquipoDeInscripcion(r.inscripcion_destino_id)}`,
          },
          { key: "motivo", label: "Motivo", render: (r) => r.motivo ?? "—" },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage="Sin traspasos en esta edición todavía."
        onSoftDelete={(fila) =>
          crud.customAction.mutate(
            { path: `/api/v1/traspasos/${fila.id}/anular` },
            // Anular ahora revierte JUGADOR_EQUIPO de verdad (D del plan) —
            // Plantillas necesita refrescarse, no solo la lista de traspasos.
            { onSuccess: () => queryClient.invalidateQueries({ queryKey: ["plantillas"] }) },
          )
        }
        softDeleteLabel="Anular"
        softDeletePending={crud.customAction.isPending}
        estadosDeBaja={["Anulado"]}
        // fixes-datos-traspasos-control-mesa-plan.md: el botón desaparece
        // en cuanto el club destino ya arrancó un partido desde este
        // traspaso — a partir de ahí corresponde un traspaso inverso, no
        // un "deshacer" (backend, TraspasoService._puede_anularse).
        puedeSoftDelete={(fila) => fila.puede_anularse}
      />
    </div>
  );
}

interface TraspasoBody {
  jugador_perfil_id: number;
  inscripcion_origen_id: number | null;
  inscripcion_destino_id: number;
  dorsal_nuevo: number | null;
  motivo: string | null;
}

/** Flujo 2 del plan — formulario "Nuevo traspaso": jugador buscable →
 * origen derivado → destino elegido → dorsal, en ese orden causal
 * (Litmus scorecard, Jerarquía de información: 9/10). */
function FormularioNuevoTraspaso(props: {
  torneoId: number;
  disciplinaId: number;
  torneoContexto: string;
  inscripciones: InscripcionRow[];
  inscripcionesLoading: boolean;
  nombreEquipoDeInscripcion: (inscripcionId: number) => string;
  perfiles: ReturnType<typeof useResourceCrud<PerfilRow, { jugador_id: number; disciplina_id: number }>>;
  onCrear: (body: TraspasoBody) => Promise<unknown>;
  creando: boolean;
  errorCrear: string | null;
  onCancel: () => void;
}) {
  const {
    disciplinaId,
    torneoId,
    torneoContexto,
    inscripciones,
    inscripcionesLoading,
    nombreEquipoDeInscripcion,
    perfiles,
    onCrear,
    creando,
    errorCrear,
    onCancel,
  } = props;

  const [jugadorElegido, setJugadorElegido] = useState<JugadorBuscadoRow | null>(null);
  const [perfilId, setPerfilId] = useState<number | null>(null);
  const [resolviendoPerfil, setResolviendoPerfil] = useState(false);
  const [errorPerfil, setErrorPerfil] = useState<string | null>(null);
  const [inscripcionDestinoId, setInscripcionDestinoId] = useState<number | null>(null);
  const [dorsalNuevo, setDorsalNuevo] = useState("");
  const [motivo, setMotivo] = useState("");

  const origen = useOrigenActualDelPerfil(perfilId, torneoId, nombreEquipoDeInscripcion);
  const dorsalesHistoricos = useDorsalesHistoricos(perfilId);

  // Resuelve-o-crea el perfil del jugador en ESTA disciplina, mismo
  // patrón que PlantillasDelTorneo.crearVinculo — un traspaso opera sobre
  // JUGADOR_PERFIL_DISCIPLINA, no sobre JUGADOR directo. Confirma con un
  // GET filtrado server-side (no la lista capada a LIMITE_LISTA) antes de
  // crear, para no duplicar un perfil que exista pero esté fuera de esa
  // ventana.
  async function resolverPerfilId(jugadorId: number): Promise<number> {
    const { data, error } = await api.GET("/api/v1/perfiles", {
      params: { query: { jugador_id: jugadorId, disciplina_id: disciplinaId, limit: 1 } },
    });
    if (!error && data && data.length > 0) return data[0].id;
    const nuevo = await perfiles.create.mutateAsync({ jugador_id: jugadorId, disciplina_id: disciplinaId });
    return nuevo.id;
  }

  async function elegirJugador(j: JugadorBuscadoRow) {
    setJugadorElegido(j);
    setPerfilId(null);
    setErrorPerfil(null);
    setResolviendoPerfil(true);
    try {
      setPerfilId(await resolverPerfilId(j.id));
    } catch (e) {
      setErrorPerfil(apiErrorMessage(e, "No se pudo resolver el perfil del jugador en esta disciplina."));
    } finally {
      setResolviendoPerfil(false);
    }
  }

  // Estado de interacción del plan: cambiar el jugador buscado resetea
  // origen/dorsal-sugerido — evita mostrar el origen del jugador anterior
  // con el nombre del nuevo.
  function cambiarJugador() {
    setJugadorElegido(null);
    setPerfilId(null);
    setErrorPerfil(null);
    setDorsalNuevo("");
  }

  const puedeTraspasar = perfilId != null && inscripcionDestinoId != null && !resolviendoPerfil;

  async function confirmar() {
    if (!puedeTraspasar) return;
    await onCrear({
      jugador_perfil_id: perfilId as number,
      inscripcion_origen_id: origen.inscripcionOrigenId,
      inscripcion_destino_id: inscripcionDestinoId as number,
      dorsal_nuevo: dorsalNuevo.trim() === "" ? null : Number(dorsalNuevo),
      motivo: motivo.trim() === "" ? null : motivo.trim(),
    });
  }

  return (
    <div>
      <h2>Nuevo traspaso — {torneoContexto}</h2>
      <div className="resource-form">
        <SelectorJugadorBuscable
          label="Jugador"
          elegido={jugadorElegido}
          onElegir={(j) => void elegirJugador(j)}
          onCambiar={cambiarJugador}
        />
        {resolviendoPerfil && <p className="muted">Resolviendo perfil...</p>}
        {errorPerfil && <p className="error-text">{errorPerfil}</p>}

        {jugadorElegido && perfilId != null && (
          <>
            <div className="campo-derivado">
              <span className="campo-derivado__etiqueta">Equipo de origen</span>
              <strong>{origen.isLoading ? "Cargando..." : origen.etiqueta}</strong>
            </div>

            <label>
              Equipo destino
              <select
                aria-label="Equipo destino"
                value={inscripcionDestinoId ?? ""}
                onChange={(e) => setInscripcionDestinoId(e.target.value ? Number(e.target.value) : null)}
                disabled={inscripcionesLoading}
              >
                <option value="">Elegir...</option>
                {inscripciones.map((i) => (
                  <option key={i.id} value={i.id}>
                    {nombreEquipoDeInscripcion(i.id)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Dorsal nuevo
              <input
                aria-label="Dorsal nuevo"
                type="number"
                value={dorsalNuevo}
                onChange={(e) => setDorsalNuevo(e.target.value)}
              />
            </label>
            {dorsalesHistoricos.length > 0 && (
              <div className="dorsal-chips">
                {dorsalesHistoricos.map((d) => (
                  <button key={d} type="button" className="dorsal-chip" onClick={() => setDorsalNuevo(String(d))}>
                    {d}
                  </button>
                ))}
              </div>
            )}

            <label>
              Motivo (opcional)
              <input aria-label="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
            </label>
          </>
        )}

        {errorCrear && <p className="error-text">{errorCrear}</p>}
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={onCancel}>
            Cancelar
          </button>
          <button type="button" disabled={!puedeTraspasar || creando} onClick={() => void confirmar()}>
            {creando ? "Traspasando..." : "Traspasar"}
          </button>
        </div>
      </div>
    </div>
  );
}
