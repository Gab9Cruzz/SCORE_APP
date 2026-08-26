import { useState } from "react";
import { apiErrorMessage } from "../../api/client";
import { ResourceForm, type ResourceFieldValue, type ResourceFormField } from "../../components/admin/ResourceForm";
import { ResourceTable, type ResourceTableColumn } from "../../components/admin/ResourceTable";
import { useResourceCrud } from "../../hooks/useResourceCrud";

interface RowBase {
  id: number;
  estado?: string;
}

type Modo<TOut> = { tipo: "lista" } | { tipo: "crear" } | { tipo: "editar"; fila: TOut };

interface SimpleResourceAdminPageProps<TOut extends RowBase> {
  resourceKey: string;
  basePath: string;
  title: string;
  createFields: ResourceFormField[];
  editFields: ResourceFormField[];
  columns: ResourceTableColumn<TOut>[];
  emptyMessage?: string;
}

/** Página de gestión CRUD para un recurso "simple" (Torneo, Equipo,
 * Jugador — roles-3-modulos-plan.md, Fase 2, D1): comparten la misma
 * forma de página (lista ↔ crear ↔ editar), solo cambia la config de
 * campos/columnas. Partido, InscripcionTorneo y JugadorEquipo NO usan
 * esto — se desvían demasiado del patrón (ver PartidosAdmin.tsx,
 * InscripcionesAdmin.tsx, PlantillasAdmin.tsx). */
export function SimpleResourceAdminPage<TOut extends RowBase>(props: SimpleResourceAdminPageProps<TOut>) {
  const { resourceKey, basePath, title, createFields, editFields, columns, emptyMessage } = props;
  const crud = useResourceCrud<TOut>({ resourceKey, basePath });
  const [modo, setModo] = useState<Modo<TOut>>({ tipo: "lista" });

  function volver() {
    setModo({ tipo: "lista" });
  }

  if (modo.tipo === "crear") {
    return (
      <div className="page">
        <h1>Nuevo — {title}</h1>
        <ResourceForm
          fields={createFields}
          onSubmit={(values) => crud.create.mutate(values as never, { onSuccess: volver })}
          submitting={crud.create.isPending}
          submitError={crud.create.isError ? apiErrorMessage(crud.create.error) : null}
          submitLabel="Crear"
          onCancel={volver}
        />
      </div>
    );
  }

  if (modo.tipo === "editar") {
    const fila = modo.fila;
    const initialValues: Record<string, ResourceFieldValue> = {};
    for (const f of editFields) {
      const v = (fila as Record<string, unknown>)[f.name];
      initialValues[f.name] = typeof v === "number" || typeof v === "string" ? v : null;
    }
    return (
      <div className="page">
        <h1>Editar — {title}</h1>
        <ResourceForm
          fields={editFields}
          initialValues={initialValues}
          onSubmit={(values) => crud.update.mutate({ id: fila.id, body: values as never }, { onSuccess: volver })}
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
        <h1>{title}</h1>
        <button type="button" onClick={() => setModo({ tipo: "crear" })}>
          + Nuevo
        </button>
      </div>
      <ResourceTable<TOut>
        rows={crud.listQuery.data ?? []}
        columns={columns}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage={emptyMessage}
        onSelect={(fila) => setModo({ tipo: "editar", fila })}
        onSoftDelete={(fila) => crud.softDelete.mutate(fila.id)}
        softDeletePending={crud.softDelete.isPending}
      />
    </div>
  );
}
