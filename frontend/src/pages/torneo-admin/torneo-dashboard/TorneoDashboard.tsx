import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../../api/client";

interface TorneoRow {
  id: number;
  nombre: string;
  torneo_grupo_id: number;
  numero_edicion: number;
  disciplina_id: number;
  modalidad_id: number | null;
  estado: string;
  fecha_inicio: string;
  fecha_fin: string;
}
interface TorneoGrupoRow {
  id: number;
  nombre: string;
}

/** Contexto que cada sub-pestaña recibe vía `useOutletContext` — evita
 * repetir el fetch de `/torneos/{id}` en cada una (torneos-admin-plan.md,
 * Fase 2: "panel específico de ese torneo"). */
export interface TorneoDashboardContext {
  torneoId: number;
  torneoGrupoId: number;
  disciplinaId: number;
  modalidadId: number | null;
  /** "{grupo.nombre} — Edición {n}" ya compuesto — lo reusan el modal
   * Agregar Equipo y RegistroLoteAdminPage para el texto de contexto
   * (torneos-admin-plan.md, Decision Audit Trail #3: nunca se persiste
   * concatenado, pero para MOSTRARLO en una sub-pantalla sí conviene
   * componerlo una sola vez acá arriba). */
  torneoContexto: string;
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

  return (
    <div className="page">
      <div className="torneo-dashboard__header">
        <h1>{torneoContexto}</h1>
        <p className="muted">Estado: {torneo.estado}</p>
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
          } satisfies TorneoDashboardContext
        }
      />
    </div>
  );
}
