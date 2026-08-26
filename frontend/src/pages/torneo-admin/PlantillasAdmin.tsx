import { useMemo, useState } from "react";
import { apiErrorMessage } from "../../api/client";
import { ResourceForm, type ResourceFieldValue } from "../../components/admin/ResourceForm";
import { ResourceTable } from "../../components/admin/ResourceTable";
import { useResourceCrud } from "../../hooks/useResourceCrud";

interface PlantillaRow {
  id: number;
  jugador_id: number;
  equipo_id: number;
  dorsal: number | null;
  fecha_inicio: string;
  fecha_fin: string | null;
  estado: string;
}
interface JugadorRow {
  id: number;
  nombre: string;
}
interface EquipoRow {
  id: number;
  nombre: string;
}

type Modo =
  | { tipo: "lista" }
  | { tipo: "crear" }
  | { tipo: "editar"; fila: PlantillaRow }
  | { tipo: "baja"; fila: PlantillaRow };

/** JugadorEquipo ("plantillas") es el que más se desvía del scaffold
 * genérico (roles-3-modulos-plan.md, Fase 2, D1 — corrección de la voz
 * externa): su GET no tiene skip/limit/estado (los ignora, no rompe), y
 * "dar de baja" es POST /{id}/baja?fecha_fin=X — no un DELETE ni un PATCH
 * plano. El resto (crear/editar dorsal-estado) sí es un PATCH normal. */
export function PlantillasAdminPage() {
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });

  const crud = useResourceCrud<PlantillaRow>({ resourceKey: "plantillas", basePath: "/api/v1/plantillas" });
  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });
  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });

  const nombreJugador = useMemo(
    () => new Map((jugadores.listQuery.data ?? []).map((j) => [j.id, j.nombre])),
    [jugadores.listQuery.data],
  );
  const nombreEquipo = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );

  function volver() {
    setModo({ tipo: "lista" });
  }

  if (modo.tipo === "crear") {
    return (
      <div className="page">
        <h1>Nuevo vínculo — Plantilla</h1>
        <ResourceForm
          fields={[
            {
              name: "jugador_id",
              label: "Jugador",
              type: "reference",
              required: true,
              optionsLoading: jugadores.listQuery.isLoading,
              options: (jugadores.listQuery.data ?? []).map((j) => ({ value: j.id, label: j.nombre })),
            },
            {
              name: "equipo_id",
              label: "Equipo",
              type: "reference",
              required: true,
              optionsLoading: equipos.listQuery.isLoading,
              options: (equipos.listQuery.data ?? []).map((e) => ({ value: e.id, label: e.nombre })),
            },
            { name: "dorsal", label: "Dorsal", type: "number" },
            { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
          ]}
          onSubmit={(values) => crud.create.mutate(values as never, { onSuccess: volver })}
          submitting={crud.create.isPending}
          submitError={crud.create.isError ? apiErrorMessage(crud.create.error) : null}
          submitLabel="Vincular"
          onCancel={volver}
        />
      </div>
    );
  }

  if (modo.tipo === "editar") {
    const initialValues: Record<string, ResourceFieldValue> = {
      dorsal: modo.fila.dorsal,
      estado: modo.fila.estado,
    };
    return (
      <div className="page">
        <h1>Editar vínculo</h1>
        <p className="muted">
          {nombreJugador.get(modo.fila.jugador_id) ?? `Jugador #${modo.fila.jugador_id}`} en{" "}
          {nombreEquipo.get(modo.fila.equipo_id) ?? `Equipo #${modo.fila.equipo_id}`}
        </p>
        <ResourceForm
          fields={[
            { name: "dorsal", label: "Dorsal", type: "number" },
            { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo", "Suspendido"] },
          ]}
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

  if (modo.tipo === "baja") {
    return (
      <div className="page">
        <h1>Dar de baja</h1>
        <p className="muted">
          {nombreJugador.get(modo.fila.jugador_id) ?? `Jugador #${modo.fila.jugador_id}`} sale de{" "}
          {nombreEquipo.get(modo.fila.equipo_id) ?? `Equipo #${modo.fila.equipo_id}`} — libera el dorsal para otro jugador.
        </p>
        <ResourceForm
          fields={[{ name: "fecha_fin", label: "Fecha de baja", type: "date", required: true }]}
          onSubmit={(values) =>
            crud.customAction.mutate(
              {
                path: `/api/v1/plantillas/${modo.fila.id}/baja`,
                query: { fecha_fin: values.fecha_fin },
              },
              { onSuccess: volver },
            )
          }
          submitting={crud.customAction.isPending}
          submitError={crud.customAction.isError ? apiErrorMessage(crud.customAction.error) : null}
          submitLabel="Confirmar baja"
          onCancel={volver}
        />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page__header">
        <h1>Plantillas</h1>
        <button type="button" onClick={() => setModo({ tipo: "crear" })}>
          + Nuevo vínculo
        </button>
      </div>
      <ResourceTable<PlantillaRow>
        rows={crud.listQuery.data ?? []}
        columns={[
          { key: "jugador", label: "Jugador", render: (r) => nombreJugador.get(r.jugador_id) ?? `#${r.jugador_id}` },
          { key: "equipo", label: "Equipo", render: (r) => nombreEquipo.get(r.equipo_id) ?? `#${r.equipo_id}` },
          { key: "dorsal", label: "Dorsal", render: (r) => (r.dorsal ? `#${r.dorsal}` : "—") },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage="No hay jugadores vinculados a ningún equipo todavía."
        onSelect={(fila) => setModo({ tipo: "editar", fila })}
        onSoftDelete={(fila) => setModo({ tipo: "baja", fila })}
        softDeleteLabel="Dar de baja"
        estadosDeBaja={["Inactivo"]}
      />
    </div>
  );
}
