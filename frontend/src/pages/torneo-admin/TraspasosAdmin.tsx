import { useMemo, useState } from "react";
import { apiErrorMessage } from "../../api/client";
import { ResourceForm } from "../../components/admin/ResourceForm";
import { ResourceTable } from "../../components/admin/ResourceTable";
import { useResourceCrud } from "../../hooks/useResourceCrud";

interface TraspasoRow {
  id: number;
  jugador_perfil_id: number;
  inscripcion_origen_id: number | null;
  inscripcion_destino_id: number;
  dorsal_nuevo: number | null;
  motivo: string | null;
  fecha_traspaso: string;
  estado: string;
}
interface JugadorRow {
  id: number;
  nombre: string;
}
interface DisciplinaRow {
  id: number;
  nombre: string;
}
interface PerfilRow {
  id: number;
  jugador_id: number;
  disciplina_id: number;
}
interface EquipoRow {
  id: number;
  nombre: string;
}
interface TorneoRow {
  id: number;
  nombre: string;
}
interface InscripcionRow {
  id: number;
  torneo_id: number;
  equipo_id: number;
}

type Modo = { tipo: "lista" } | { tipo: "crear" };

const formatearFecha = (iso: string) => new Date(iso).toLocaleString("es-AR");

/** Traspasos (equipos-jugadores-plan.md, Fase 2, Etapa C). Página custom,
 * mismo motivo que PlantillasAdmin.tsx: necesita resolver nombres de
 * varios recursos relacionados para las columnas/labels, no encaja en
 * SimpleResourceAdminPage. "Anular" reusa el mecanismo genérico de
 * ResourceTable (onSoftDelete/estadosDeBaja) aunque semánticamente sea un
 * POST a /anular, no un DELETE — mismo patrón que PlantillasAdmin usa
 * para "dar de baja" vía customAction. */
export function TraspasosAdminPage() {
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });

  const crud = useResourceCrud<TraspasoRow>({ resourceKey: "traspasos", basePath: "/api/v1/traspasos" });
  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });
  const disciplinas = useResourceCrud<DisciplinaRow>({ resourceKey: "disciplinas", basePath: "/api/v1/disciplinas" });
  const perfiles = useResourceCrud<PerfilRow>({ resourceKey: "perfiles", basePath: "/api/v1/perfiles" });
  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });
  const torneos = useResourceCrud<TorneoRow>({ resourceKey: "torneos", basePath: "/api/v1/torneos" });
  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
  });

  const nombreJugador = useMemo(
    () => new Map((jugadores.listQuery.data ?? []).map((j) => [j.id, j.nombre])),
    [jugadores.listQuery.data],
  );
  const nombreDisciplina = useMemo(
    () => new Map((disciplinas.listQuery.data ?? []).map((d) => [d.id, d.nombre])),
    [disciplinas.listQuery.data],
  );
  const nombreEquipo = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );
  const nombreTorneo = useMemo(
    () => new Map((torneos.listQuery.data ?? []).map((t) => [t.id, t.nombre])),
    [torneos.listQuery.data],
  );
  const inscripcionPorId = useMemo(
    () => new Map((inscripciones.listQuery.data ?? []).map((i) => [i.id, i])),
    [inscripciones.listQuery.data],
  );
  const perfilPorId = useMemo(
    () => new Map((perfiles.listQuery.data ?? []).map((p) => [p.id, p])),
    [perfiles.listQuery.data],
  );

  function etiquetaPerfil(perfilId: number): string {
    const p = perfilPorId.get(perfilId);
    if (!p) return `Perfil #${perfilId}`;
    return `${nombreJugador.get(p.jugador_id) ?? `Jugador #${p.jugador_id}`} — ${nombreDisciplina.get(p.disciplina_id) ?? `Disciplina #${p.disciplina_id}`}`;
  }
  function etiquetaInscripcion(inscripcionId: number | null): string {
    if (inscripcionId == null) return "Agencia libre";
    const i = inscripcionPorId.get(inscripcionId);
    if (!i) return `Inscripción #${inscripcionId}`;
    return `${nombreTorneo.get(i.torneo_id) ?? `Torneo #${i.torneo_id}`} — ${nombreEquipo.get(i.equipo_id) ?? `Equipo #${i.equipo_id}`}`;
  }

  function volver() {
    setModo({ tipo: "lista" });
  }

  if (modo.tipo === "crear") {
    return (
      <div className="page">
        <h1>Nuevo traspaso</h1>
        <ResourceForm
          fields={[
            {
              name: "jugador_perfil_id",
              label: "Jugador — Disciplina",
              type: "reference",
              required: true,
              optionsLoading: perfiles.listQuery.isLoading,
              options: (perfiles.listQuery.data ?? []).map((p) => ({ value: p.id, label: etiquetaPerfil(p.id) })),
            },
            {
              name: "inscripcion_origen_id",
              label: "Equipo de origen (vacío = ficha desde agencia libre)",
              type: "reference",
              optionsLoading: inscripciones.listQuery.isLoading,
              options: (inscripciones.listQuery.data ?? []).map((i) => ({
                value: i.id,
                label: etiquetaInscripcion(i.id),
              })),
            },
            {
              name: "inscripcion_destino_id",
              label: "Equipo de destino",
              type: "reference",
              required: true,
              optionsLoading: inscripciones.listQuery.isLoading,
              options: (inscripciones.listQuery.data ?? []).map((i) => ({
                value: i.id,
                label: etiquetaInscripcion(i.id),
              })),
            },
            { name: "dorsal_nuevo", label: "Dorsal nuevo", type: "number" },
            { name: "motivo", label: "Motivo", type: "text" },
          ]}
          onSubmit={(values) => crud.create.mutate(values as never, { onSuccess: volver })}
          submitting={crud.create.isPending}
          submitError={crud.create.isError ? apiErrorMessage(crud.create.error) : null}
          submitLabel="Traspasar"
          onCancel={volver}
        />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page__header">
        <h1>Traspasos</h1>
        <button type="button" onClick={() => setModo({ tipo: "crear" })}>
          + Nuevo traspaso
        </button>
      </div>
      {crud.customAction.isError && <p className="error-text">{apiErrorMessage(crud.customAction.error)}</p>}
      <ResourceTable<TraspasoRow>
        rows={crud.listQuery.data ?? []}
        columns={[
          { key: "fecha", label: "Fecha", render: (r) => formatearFecha(r.fecha_traspaso) },
          { key: "perfil", label: "Jugador — Disciplina", render: (r) => etiquetaPerfil(r.jugador_perfil_id) },
          {
            key: "movimiento",
            label: "Origen → Destino",
            render: (r) => `${etiquetaInscripcion(r.inscripcion_origen_id)} → ${etiquetaInscripcion(r.inscripcion_destino_id)}`,
          },
          { key: "motivo", label: "Motivo", render: (r) => r.motivo ?? "—" },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage="No hay traspasos registrados todavía."
        onSoftDelete={(fila) =>
          crud.customAction.mutate({ path: `/api/v1/traspasos/${fila.id}/anular` })
        }
        softDeleteLabel="Anular"
        softDeletePending={crud.customAction.isPending}
        estadosDeBaja={["Anulado"]}
      />
    </div>
  );
}
