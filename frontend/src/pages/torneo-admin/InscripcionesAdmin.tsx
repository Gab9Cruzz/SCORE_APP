import { useMemo, useState } from "react";
import { apiErrorMessage } from "../../api/client";
import { ResourceForm, type ResourceFieldValue } from "../../components/admin/ResourceForm";
import { ResourceTable } from "../../components/admin/ResourceTable";
import { useResourceCrud } from "../../hooks/useResourceCrud";

interface InscripcionRow {
  id: number;
  torneo_id: number;
  equipo_id: number;
  estado: string;
  fecha: string;
}
interface TorneoRow {
  id: number;
  nombre: string;
}
interface EquipoRow {
  id: number;
  nombre: string;
}

type Modo = { tipo: "lista" } | { tipo: "crear" } | { tipo: "editar"; fila: InscripcionRow };

/** InscripcionTorneo se desvía del scaffold genérico (roles-3-modulos-plan.md,
 * Fase 2, D1 — corrección de la voz externa): no tiene DELETE, el borrado
 * lógico es un PATCH {estado: "Cancelado"} directo — por eso NO usa
 * SimpleResourceAdminPage (su softDelete siempre hace DELETE), reusa
 * ResourceTable/ResourceForm a mano. */
export function InscripcionesAdminPage() {
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });

  const crud = useResourceCrud<InscripcionRow>({ resourceKey: "inscripciones", basePath: "/api/v1/inscripciones" });
  const torneos = useResourceCrud<TorneoRow>({ resourceKey: "torneos", basePath: "/api/v1/torneos" });
  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });

  const nombreTorneo = useMemo(
    () => new Map((torneos.listQuery.data ?? []).map((t) => [t.id, t.nombre])),
    [torneos.listQuery.data],
  );
  const nombreEquipo = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );

  function volver() {
    setModo({ tipo: "lista" });
  }

  function cancelar(fila: InscripcionRow) {
    crud.update.mutate({ id: fila.id, body: { estado: "Cancelado" } as never });
  }

  if (modo.tipo === "crear") {
    return (
      <div className="page">
        <h1>Nueva inscripción</h1>
        <ResourceForm
          fields={[
            {
              name: "torneo_id",
              label: "Torneo",
              type: "reference",
              required: true,
              optionsLoading: torneos.listQuery.isLoading,
              options: (torneos.listQuery.data ?? []).map((t) => ({ value: t.id, label: t.nombre })),
            },
            {
              name: "equipo_id",
              label: "Equipo",
              type: "reference",
              required: true,
              optionsLoading: equipos.listQuery.isLoading,
              options: (equipos.listQuery.data ?? []).map((e) => ({ value: e.id, label: e.nombre })),
            },
          ]}
          onSubmit={(values) => crud.create.mutate(values as never, { onSuccess: volver })}
          submitting={crud.create.isPending}
          submitError={crud.create.isError ? apiErrorMessage(crud.create.error) : null}
          submitLabel="Inscribir"
          onCancel={volver}
        />
      </div>
    );
  }

  if (modo.tipo === "editar") {
    const initialValues: Record<string, ResourceFieldValue> = { estado: modo.fila.estado };
    return (
      <div className="page">
        <h1>Editar inscripción</h1>
        <p className="muted">
          {nombreEquipo.get(modo.fila.equipo_id) ?? `Equipo #${modo.fila.equipo_id}`} en{" "}
          {nombreTorneo.get(modo.fila.torneo_id) ?? `Torneo #${modo.fila.torneo_id}`}
        </p>
        <ResourceForm
          fields={[{ name: "estado", label: "Estado", type: "select", choices: ["Inscrito", "Confirmado", "Cancelado"] }]}
          initialValues={initialValues}
          onSubmit={(values) => crud.update.mutate({ id: modo.fila.id, body: values as never }, { onSuccess: volver })}
          submitting={crud.update.isPending}
          submitError={crud.update.isError ? apiErrorMessage(crud.update.error) : null}
          submitLabel="Guardar cambios"
          onCancel={volver}
        />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page__header">
        <h1>Inscripciones</h1>
        <button type="button" onClick={() => setModo({ tipo: "crear" })}>
          + Nueva
        </button>
      </div>
      <ResourceTable<InscripcionRow>
        rows={crud.listQuery.data ?? []}
        columns={[
          { key: "torneo", label: "Torneo", render: (r) => nombreTorneo.get(r.torneo_id) ?? `#${r.torneo_id}` },
          { key: "equipo", label: "Equipo", render: (r) => nombreEquipo.get(r.equipo_id) ?? `#${r.equipo_id}` },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage="No hay inscripciones todavía."
        onSelect={(fila) => setModo({ tipo: "editar", fila })}
        onSoftDelete={cancelar}
        softDeleteLabel="Cancelar"
        softDeletePending={crud.update.isPending}
        estadosDeBaja={["Cancelado"]}
      />
    </div>
  );
}
