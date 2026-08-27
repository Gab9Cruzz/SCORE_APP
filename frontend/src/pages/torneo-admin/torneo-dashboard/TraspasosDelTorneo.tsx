import { useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { apiErrorMessage } from "../../../api/client";
import { ResourceForm } from "../../../components/admin/ResourceForm";
import { ResourceTable } from "../../../components/admin/ResourceTable";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import type { TorneoDashboardContext } from "./TorneoDashboard";

interface TraspasoRow {
  id: number;
  jugador_perfil_id: number;
  inscripcion_origen_id: number | null;
  inscripcion_destino_id: number;
  motivo: string | null;
  fecha_traspaso: string;
  estado: string;
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
interface EquipoRow {
  id: number;
  nombre: string;
}

type Modo = { tipo: "lista" } | { tipo: "crear" };

const formatearFecha = (iso: string) => new Date(iso).toLocaleString("es-AR");

/** Sub-pestaña "Traspasos" del dashboard scoped — mismo alcance funcional
 * que la extinta pestaña global TraspasosAdmin.tsx (Fase 3: consolidación),
 * pero el Jugador y los pickers de origen/destino se filtran a la
 * disciplina y al torneo de ESTA edición: un perfil de otra disciplina no
 * tiene sentido como candidato acá. */
export function TraspasosDelTorneoPage() {
  const { torneoId, disciplinaId, torneoContexto } = useOutletContext<TorneoDashboardContext>();
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });

  const crud = useResourceCrud<TraspasoRow>({
    resourceKey: "traspasos",
    basePath: "/api/v1/traspasos",
    listParams: { torneo_id: torneoId },
  });
  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });
  const perfiles = useResourceCrud<PerfilRow>({
    resourceKey: "perfiles",
    basePath: "/api/v1/perfiles",
    listParams: { disciplina_id: disciplinaId },
  });
  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
    listParams: { torneo_id: torneoId },
  });
  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });

  const nombreJugador = useMemo(
    () => new Map((jugadores.listQuery.data ?? []).map((j) => [j.id, j.nombre])),
    [jugadores.listQuery.data],
  );
  const nombreEquipoDeInscripcion = useMemo(() => {
    const inscripcionAEquipo = new Map((inscripciones.listQuery.data ?? []).map((i) => [i.id, i.equipo_id]));
    const equipoANombre = new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre]));
    return (inscripcionId: number | null) =>
      inscripcionId == null ? "Agencia libre" : (equipoANombre.get(inscripcionAEquipo.get(inscripcionId) ?? -1) ?? `#${inscripcionId}`);
  }, [inscripciones.listQuery.data, equipos.listQuery.data]);
  const etiquetaJugador = useMemo(() => {
    const perfilAJugador = new Map((perfiles.listQuery.data ?? []).map((p) => [p.id, p.jugador_id]));
    return (perfilId: number) => nombreJugador.get(perfilAJugador.get(perfilId) ?? -1) ?? `Perfil #${perfilId}`;
  }, [perfiles.listQuery.data, nombreJugador]);

  function volver() {
    setModo({ tipo: "lista" });
  }

  if (modo.tipo === "crear") {
    return (
      <div>
        <h2>Nuevo traspaso — {torneoContexto}</h2>
        <ResourceForm
          fields={[
            {
              name: "jugador_perfil_id",
              label: "Jugador",
              type: "reference",
              required: true,
              optionsLoading: perfiles.listQuery.isLoading,
              options: (perfiles.listQuery.data ?? []).map((p) => ({ value: p.id, label: etiquetaJugador(p.id) })),
            },
            {
              name: "inscripcion_origen_id",
              label: "Equipo de origen (vacío = ficha desde agencia libre)",
              type: "reference",
              optionsLoading: inscripciones.listQuery.isLoading,
              options: (inscripciones.listQuery.data ?? []).map((i) => ({
                value: i.id,
                label: nombreEquipoDeInscripcion(i.id),
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
                label: nombreEquipoDeInscripcion(i.id),
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
    <div>
      <div className="page__header">
        <h2>Traspasos de esta edición</h2>
        <button type="button" onClick={() => setModo({ tipo: "crear" })}>
          + Nuevo traspaso
        </button>
      </div>
      {crud.customAction.isError && <p className="error-text">{apiErrorMessage(crud.customAction.error)}</p>}
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
        onSoftDelete={(fila) => crud.customAction.mutate({ path: `/api/v1/traspasos/${fila.id}/anular` })}
        softDeleteLabel="Anular"
        softDeletePending={crud.customAction.isPending}
        estadosDeBaja={["Anulado"]}
      />
    </div>
  );
}
