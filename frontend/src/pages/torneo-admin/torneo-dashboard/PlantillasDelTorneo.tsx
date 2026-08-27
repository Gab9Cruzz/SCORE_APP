import { useMemo, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { apiErrorMessage } from "../../../api/client";
import { ResourceForm, type ResourceFieldValue } from "../../../components/admin/ResourceForm";
import { ResourceTable } from "../../../components/admin/ResourceTable";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import type { RegistroLoteAlcanceTorneo } from "../RegistroLoteAdmin";
import type { TorneoDashboardContext } from "./TorneoDashboard";

interface PlantillaRow {
  id: number;
  jugador_perfil_id: number;
  inscripcion_torneo_id: number;
  dorsal: number | null;
  fecha_inicio: string;
  fecha_fin: string | null;
  estado: string;
}
interface JugadorRow {
  id: number;
  nombre: string;
}
interface PerfilRow {
  id: number;
  jugador_id: number;
  disciplina_id: number;
}
interface InscripcionRow {
  id: number;
  equipo_id: number;
}
interface EquipoRow {
  id: number;
  nombre: string;
}

type Modo = { tipo: "lista" } | { tipo: "crear" } | { tipo: "editar"; fila: PlantillaRow } | { tipo: "baja"; fila: PlantillaRow };

/** Sub-pestaña "Plantillas" del dashboard scoped, con el mismo alcance
 * funcional que la extinta pestaña global PlantillasAdmin.tsx (Fase 3 del
 * plan: consolidación) — alta/edición/baja de vínculos jugador↔equipo,
 * pero acotado a este torneo y sin volver a preguntar la Disciplina (ya la
 * fija el torneo, `disciplinaId` del contexto). */
export function PlantillasDelTorneoPage() {
  const { torneoId, disciplinaId, torneoContexto } = useOutletContext<TorneoDashboardContext>();
  const navigate = useNavigate();
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });
  const [errorPerfil, setErrorPerfil] = useState<string | null>(null);
  const [resolviendoPerfil, setResolviendoPerfil] = useState(false);

  const crud = useResourceCrud<PlantillaRow>({
    resourceKey: "plantillas",
    basePath: "/api/v1/plantillas",
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
  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });

  const nombreJugador = useMemo(
    () => new Map((jugadores.listQuery.data ?? []).map((j) => [j.id, j.nombre])),
    [jugadores.listQuery.data],
  );
  const nombreEquipoDeInscripcion = useMemo(() => {
    const inscripcionAEquipo = new Map((inscripciones.listQuery.data ?? []).map((i) => [i.id, i.equipo_id]));
    const equipoANombre = new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre]));
    return (inscripcionId: number) =>
      equipoANombre.get(inscripcionAEquipo.get(inscripcionId) ?? -1) ?? `Inscripción #${inscripcionId}`;
  }, [inscripciones.listQuery.data, equipos.listQuery.data]);
  const perfilPorId = useMemo(
    () => new Map((perfiles.listQuery.data ?? []).map((p) => [p.id, p])),
    [perfiles.listQuery.data],
  );
  const perfilIdPorJugador = useMemo(
    () => new Map((perfiles.listQuery.data ?? []).map((p) => [p.jugador_id, p.id])),
    [perfiles.listQuery.data],
  );

  function etiquetaJugador(perfilId: number): string {
    const p = perfilPorId.get(perfilId);
    return p ? (nombreJugador.get(p.jugador_id) ?? `Jugador #${p.jugador_id}`) : `Perfil #${perfilId}`;
  }

  function volver() {
    setModo({ tipo: "lista" });
    setErrorPerfil(null);
  }

  // Mismo patrón resolve-o-crea-el-perfil que ya usaba PlantillasAdmin.tsx
  // (equipos-jugadores-plan.md) — acá la Disciplina no se pregunta, la fija
  // el torneo, así que un alta nueva es un solo campo real: el Jugador.
  async function crearVinculo(values: Record<string, ResourceFieldValue>) {
    setErrorPerfil(null);
    const jugadorId = values.jugador_id as number;
    let perfilId = perfilIdPorJugador.get(jugadorId) ?? null;

    if (perfilId == null) {
      setResolviendoPerfil(true);
      try {
        const nuevoPerfil = await perfiles.create.mutateAsync({ jugador_id: jugadorId, disciplina_id: disciplinaId });
        perfilId = nuevoPerfil.id;
      } catch (e) {
        setErrorPerfil(apiErrorMessage(e, "No se pudo crear el perfil del jugador en esta disciplina."));
        setResolviendoPerfil(false);
        return;
      }
      setResolviendoPerfil(false);
    }

    crud.create.mutate(
      {
        jugador_perfil_id: perfilId,
        inscripcion_torneo_id: values.inscripcion_torneo_id,
        dorsal: values.dorsal,
        fecha_inicio: values.fecha_inicio,
      } as never,
      { onSuccess: volver },
    );
  }

  function irARegistroLote() {
    const alcance: RegistroLoteAlcanceTorneo = { torneoId, volverA: `/torneo-admin/torneos/${torneoId}/plantillas` };
    navigate("/torneo-admin/plantillas/lote", { state: alcance });
  }

  if (modo.tipo === "crear") {
    return (
      <div>
        <h2>Nuevo vínculo — {torneoContexto}</h2>
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
              name: "inscripcion_torneo_id",
              label: "Equipo",
              type: "reference",
              required: true,
              optionsLoading: inscripciones.listQuery.isLoading || equipos.listQuery.isLoading,
              options: (inscripciones.listQuery.data ?? []).map((i) => ({
                value: i.id,
                label: nombreEquipoDeInscripcion(i.id),
              })),
            },
            { name: "dorsal", label: "Dorsal", type: "number" },
            { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
          ]}
          onSubmit={crearVinculo}
          submitting={resolviendoPerfil || crud.create.isPending}
          submitError={errorPerfil ?? (crud.create.isError ? apiErrorMessage(crud.create.error) : null)}
          submitLabel="Vincular"
          onCancel={volver}
        />
      </div>
    );
  }

  if (modo.tipo === "editar") {
    const initialValues: Record<string, ResourceFieldValue> = { dorsal: modo.fila.dorsal, estado: modo.fila.estado };
    return (
      <div>
        <h2>Editar vínculo</h2>
        <p className="muted">
          {etiquetaJugador(modo.fila.jugador_perfil_id)} en {nombreEquipoDeInscripcion(modo.fila.inscripcion_torneo_id)}
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
      <div>
        <h2>Dar de baja</h2>
        <p className="muted">
          {etiquetaJugador(modo.fila.jugador_perfil_id)} sale de {nombreEquipoDeInscripcion(modo.fila.inscripcion_torneo_id)} —
          libera el dorsal para otro jugador.
        </p>
        <ResourceForm
          fields={[{ name: "fecha_fin", label: "Fecha de baja", type: "date", required: true }]}
          onSubmit={(values) =>
            crud.customAction.mutate(
              { path: `/api/v1/plantillas/${modo.fila.id}/baja`, query: { fecha_fin: values.fecha_fin } },
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
    <div>
      <div className="page__header">
        <h2>Plantillas de esta edición</h2>
        <div>
          <button type="button" onClick={() => setModo({ tipo: "crear" })}>
            + Nuevo vínculo
          </button>{" "}
          <button type="button" onClick={irARegistroLote}>
            + Registro por lote
          </button>
        </div>
      </div>
      <ResourceTable<PlantillaRow>
        rows={crud.listQuery.data ?? []}
        columns={[
          { key: "jugador", label: "Jugador", render: (r) => etiquetaJugador(r.jugador_perfil_id) },
          { key: "equipo", label: "Equipo", render: (r) => nombreEquipoDeInscripcion(r.inscripcion_torneo_id) },
          { key: "dorsal", label: "Dorsal", render: (r) => (r.dorsal ? `#${r.dorsal}` : "—") },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage="Sin jugadores registrados todavía en esta edición."
        onSelect={(fila) => setModo({ tipo: "editar", fila })}
        onSoftDelete={(fila) => setModo({ tipo: "baja", fila })}
        softDeleteLabel="Dar de baja"
        estadosDeBaja={["Inactivo", "Traspasado"]}
      />
    </div>
  );
}
