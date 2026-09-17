import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../../api/client";
import { ResourceForm, type ResourceFormField } from "../../../components/admin/ResourceForm";
import { useNombrePorIdConFaltantes } from "../../../hooks/useFetchFaltantes";

interface TorneoRow {
  id: number;
  nombre: string;
  torneo_grupo_id: number;
  numero_edicion: number;
  disciplina_id: number;
  modalidad_id: number;
  estado: string;
  fecha_inicio: string;
  fecha_fin: string;
  formato: "Liga" | "Eliminacion" | "Grupos_Playoffs";
  incluye_tercer_lugar: boolean;
  // Cierre de Fase Regular + Llaves + Playoffs (Fase A1/D).
  campeon_equipo_id: number | null;
  subcampeon_equipo_id: number | null;
  tercer_puesto_equipo_id: number | null;
  fecha_cierre: string | null;
}
interface EdicionResumen {
  id: number;
  numero_edicion: number;
  estado: string;
  fecha_inicio: string;
  fecha_fin: string;
}
interface TorneoGrupoRow {
  id: number;
  nombre: string;
  ediciones: EdicionResumen[];
}

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR");

const camposNuevaEdicion: ResourceFormField[] = [
  { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
  { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
];

/** Contexto que cada sub-pestaña recibe vía `useOutletContext` — evita
 * repetir el fetch de `/torneos/{id}` en cada una (torneos-admin-plan.md,
 * Fase 2: "panel específico de ese torneo"). */
export interface TorneoDashboardContext {
  torneoId: number;
  torneoGrupoId: number;
  disciplinaId: number;
  modalidadId: number;
  /** "{grupo.nombre} — Edición {n}" ya compuesto — lo reusan el modal
   * Agregar Equipo y RegistroLoteAdminPage para el texto de contexto
   * (torneos-admin-plan.md, Decision Audit Trail #3: nunca se persiste
   * concatenado, pero para MOSTRARLO en una sub-pantalla sí conviene
   * componerlo una sola vez acá arriba). */
  torneoContexto: string;
  /** Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
   * requerimiento #4) — decide qué pantalla de Partidos mostrar (Generar
   * Fixture / Hacer Sorteo / bracket) y si Estadísticas necesita filtrar
   * por grupo (EC-54). */
  formato: "Liga" | "Eliminacion" | "Grupos_Playoffs";
  incluyeTercerLugar: boolean;
  /** Cierre de Fase Regular + Llaves + Playoffs (Fase E4/D8) — para el
   * banner persistente de "torneo cerrado" en Partidos/Control de Mesa;
   * evita que cada sub-pestaña pida `GET /torneos/{id}` de nuevo solo
   * para esto. */
  torneoEstado: "Activo" | "Inactivo" | "Finalizado";
  fechaCierre: string | null;
}

const SUBPESTANIAS = [
  { to: "equipos", label: "Equipos" },
  { to: "plantillas", label: "Plantillas" },
  { to: "traspasos", label: "Traspasos" },
  { to: "partidos", label: "Partidos" },
  { to: "estadisticas", label: "Estadísticas" },
];

/** Panel scoped de UN torneo (una edición puntual) — reemplaza, para las
 * sub-pestañas de acá adentro, a las pestañas GLOBALES de
 * TorneoAdminLayout.tsx (Equipos/Plantillas/Traspasos/Partidos), que
 * siguen existiendo tal cual para quien las use directo — ver la nota de
 * alcance en el plan sobre qué quedó fuera de esta pasada. */
export function TorneoDashboardPage() {
  const { torneoId } = useParams<{ torneoId: string }>();
  const id = Number(torneoId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [creandoEdicion, setCreandoEdicion] = useState(false);

  const torneoQuery = useQuery({
    queryKey: ["torneos", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}", {
        params: { path: { torneo_id: id } },
      } as never);
      if (error) throw error;
      return data as TorneoRow;
    },
  });

  const grupoQuery = useQuery({
    queryKey: ["torneo-grupos", torneoQuery.data?.torneo_grupo_id],
    enabled: torneoQuery.data != null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneo-grupos/{torneo_grupo_id}", {
        params: { path: { torneo_grupo_id: torneoQuery.data!.torneo_grupo_id } },
      } as never);
      if (error) throw error;
      return data as TorneoGrupoRow;
    },
  });

  // Crea una edición nueva del MISMO grupo sin salir del dashboard —
  // Disciplina/Modalidad se heredan del lado del backend (D-Eng-5), este
  // formulario solo pide fechas (mismo contrato que "+ Nueva edición" en
  // la Pestaña Torneos, TorneosAdmin.tsx). Al confirmar, navega derecho a
  // la edición recién creada.
  const crearEdicion = useMutation({
    mutationFn: async (body: { fecha_inicio: string; fecha_fin: string }) => {
      const { data, error } = await api.POST("/api/v1/torneos", {
        body: { torneo_grupo_id: torneoQuery.data?.torneo_grupo_id, ...body },
      } as never);
      if (error) throw error;
      return data as TorneoRow;
    },
    onSuccess: (nuevaEdicion) => {
      queryClient.invalidateQueries({ queryKey: ["torneo-grupos"] });
      setCreandoEdicion(false);
      // Pedido C de equipos-disciplina-navegacion-plan.md: la pestaña
      // Agregar Equipo de la edición nueva, explícita en la URL. Antes
      // llegaba ahí igual por el <Route index> que redirige a "equipos",
      // pero dependía de esa redirección; ahora los dos caminos a "Nueva
      // edición" (acá y TorneosAdmin) apuntan al mismo destino escrito.
      navigate(`/torneo-admin/torneos/${nuevaEdicion.id}/equipos`);
    },
  });

  // Cierre de Fase Regular + Llaves + Playoffs (Fase A4/D13): el podio
  // vive UNA sola vez, acá — MotorFormatosPanel devuelve null cuando el
  // torneo está cerrado. Nombres resueltos con el mismo hook de siempre
  // (Bug 2, D2): un campeón recién inscripto no cae al fallback "#ID".
  const idsPodio = [
    torneoQuery.data?.campeon_equipo_id,
    torneoQuery.data?.subcampeon_equipo_id,
    torneoQuery.data?.tercer_puesto_equipo_id,
  ].filter((id): id is number => id != null);
  const nombreEquipoPodio = useNombrePorIdConFaltantes("/api/v1/equipos", new Map(), idsPodio);

  const [confirmandoReabrir, setConfirmandoReabrir] = useState(false);
  const reabrir = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/torneos/{torneo_id}/reabrir", {
        params: { path: { torneo_id: id } },
      } as never);
      if (error) throw error;
      return data as TorneoRow;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["torneos", id] });
      setConfirmandoReabrir(false);
    },
  });

  // D13 (Design review, Pass 3): un solo reveal al coronar — el modal ya
  // cierra solo, esto agrega el scroll hacia el podio recién aparecido.
  // `prefers-reduced-motion` respetado (sin softeo animado si el sistema
  // lo pide).
  const podioRef = useRef<HTMLDivElement>(null);
  const estadoAnteriorRef = useRef<string | null>(null);
  useEffect(() => {
    const estadoActual = torneoQuery.data?.estado ?? null;
    if (estadoAnteriorRef.current === "Activo" && estadoActual === "Finalizado") {
      const prefiereMenosMovimiento = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      podioRef.current?.scrollIntoView({ behavior: prefiereMenosMovimiento ? "auto" : "smooth" });
    }
    estadoAnteriorRef.current = estadoActual;
  }, [torneoQuery.data?.estado]);

  if (torneoQuery.isLoading) {
    return (
      <div className="page">
        <p>Cargando...</p>
      </div>
    );
  }
  if (torneoQuery.isError || !torneoQuery.data) {
    return (
      <div className="page">
        <p className="error-text">{apiErrorMessage(torneoQuery.error, "No se pudo cargar este torneo.")}</p>
      </div>
    );
  }
  const torneo = torneoQuery.data;
  const torneoContexto = `${grupoQuery.data?.nombre ?? "…"} — Edición ${torneo.numero_edicion}`;
  // Ordenadas desc por numero_edicion desde el backend (TorneoRepository.
  // listar_ediciones_del_grupo) — se muestran tal cual vienen.
  const ediciones = grupoQuery.data?.ediciones ?? [];

  return (
    <div className="page">
      <div className="torneo-dashboard__header">
        <h1>{torneoContexto}</h1>
        <p className="muted">Estado: {torneo.estado}</p>
        {torneo.estado === "Finalizado" && (
          <div ref={podioRef} className="podio">
            <div className="podio__fila podio__fila--1">
              <span className="podio__puesto">1°</span>
              <span>{nombreEquipoPodio.get(torneo.campeon_equipo_id as number) ?? `Equipo #${torneo.campeon_equipo_id}`}</span>
            </div>
            {torneo.subcampeon_equipo_id != null && (
              <div className="podio__fila podio__fila--2">
                <span className="podio__puesto">2°</span>
                <span>{nombreEquipoPodio.get(torneo.subcampeon_equipo_id) ?? `Equipo #${torneo.subcampeon_equipo_id}`}</span>
              </div>
            )}
            <div className="podio__fila podio__fila--3">
              <span className="podio__puesto">3°</span>
              {torneo.tercer_puesto_equipo_id != null ? (
                <span>{nombreEquipoPodio.get(torneo.tercer_puesto_equipo_id) ?? `Equipo #${torneo.tercer_puesto_equipo_id}`}</span>
              ) : (
                <span className="muted--cuerpo">Sin tercer puesto (torneo de 2 equipos).</span>
              )}
            </div>
            {torneo.fecha_cierre && (
              <p className="podio__provenance muted--cuerpo">Podio confirmado el {formatearFecha(torneo.fecha_cierre)}.</p>
            )}
            {!confirmandoReabrir ? (
              <button type="button" className="boton-cierre-forzado" onClick={() => setConfirmandoReabrir(true)}>
                Reabrir torneo
              </button>
            ) : (
              <div className="cierre-forzado-confirmar">
                <p className="cierre-forzado-confirmar__titulo">¿Reabrir este torneo?</p>
                <p className="muted--cuerpo">Se borra el podio registrado; el orden manual se conserva.</p>
                {reabrir.isError && <p className="error-text">{apiErrorMessage(reabrir.error)}</p>}
                <div className="resource-form__actions">
                  <button type="button" className="link-button" onClick={() => setConfirmandoReabrir(false)}>
                    Cancelar
                  </button>
                  <button type="button" disabled={reabrir.isPending} onClick={() => reabrir.mutate()}>
                    {reabrir.isPending ? "Reabriendo..." : "Reabrir torneo"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
        <div className="torneo-dashboard__edicion-selector">
          <label htmlFor="selector-edicion-dashboard">Edición:</label>
          <select
            id="selector-edicion-dashboard"
            value={torneo.id}
            onChange={(e) => navigate(`/torneo-admin/torneos/${e.target.value}`)}
          >
            {ediciones.map((e) => (
              <option key={e.id} value={e.id}>
                Edición {e.numero_edicion} — {e.estado} ({formatearFecha(e.fecha_inicio)} a {formatearFecha(e.fecha_fin)})
              </option>
            ))}
          </select>
          {!creandoEdicion && (
            <button type="button" onClick={() => setCreandoEdicion(true)}>
              + Nueva edición
            </button>
          )}
        </div>
        {creandoEdicion && (
          <ResourceForm
            fields={camposNuevaEdicion}
            onSubmit={(values) =>
              crearEdicion.mutate({ fecha_inicio: String(values.fecha_inicio), fecha_fin: String(values.fecha_fin) })
            }
            submitting={crearEdicion.isPending}
            submitError={crearEdicion.isError ? apiErrorMessage(crearEdicion.error) : null}
            submitLabel="Crear edición"
            onCancel={() => setCreandoEdicion(false)}
          />
        )}
      </div>
      <nav className="admin-nav">
        {SUBPESTANIAS.map((p) => (
          <NavLink key={p.to} to={p.to} className={({ isActive }) => (isActive ? "active" : undefined)}>
            {p.label}
          </NavLink>
        ))}
      </nav>
      <Outlet
        context={
          {
            torneoId: torneo.id,
            torneoGrupoId: torneo.torneo_grupo_id,
            disciplinaId: torneo.disciplina_id,
            modalidadId: torneo.modalidad_id,
            torneoContexto,
            formato: torneo.formato,
            incluyeTercerLugar: torneo.incluye_tercer_lugar,
            torneoEstado: torneo.estado as "Activo" | "Inactivo" | "Finalizado",
            fechaCierre: torneo.fecha_cierre,
          } satisfies TorneoDashboardContext
        }
      />
    </div>
  );
}
