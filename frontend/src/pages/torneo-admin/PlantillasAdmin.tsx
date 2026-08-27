import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiErrorMessage } from "../../api/client";
import { ResourceForm, type ResourceFieldValue } from "../../components/admin/ResourceForm";
import { ResourceTable } from "../../components/admin/ResourceTable";
import { useResourceCrud } from "../../hooks/useResourceCrud";

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

type Modo =
  | { tipo: "lista" }
  | { tipo: "crear" }
  | { tipo: "editar"; fila: PlantillaRow }
  | { tipo: "baja"; fila: PlantillaRow };

/** JugadorEquipo ("plantillas") ya no vincula (jugador, equipo) directo —
 * vincula (perfil-de-jugador-en-una-disciplina, roster-de-un-torneo), ver
 * equipos-jugadores-plan.md. El create form pide Jugador + Disciplina en
 * vez de un perfil ya armado: resuelve-o-crea el perfil (POST /perfiles
 * si no existe todavía para ese par) antes de crear el vínculo — evita
 * mandar al admin a una pantalla aparte a crear el perfil primero. La
 * pantalla dividida de registro por lote (Etapa B del plan) es la que
 * de verdad resuelve esto en un solo flujo pulido; esto es lo mínimo para
 * que la pestaña vuelva a funcionar (Etapa A).
 *
 * Sigue desviándose del scaffold genérico (roles-3-modulos-plan.md, Fase
 * 2, D1 — corrección de la voz externa): su GET no tiene skip/limit/estado,
 * y "dar de baja" es POST /{id}/baja?fecha_fin=X, no un DELETE/PATCH plano. */
export function PlantillasAdminPage() {
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });
  const [errorPerfil, setErrorPerfil] = useState<string | null>(null);
  const [resolviendoPerfil, setResolviendoPerfil] = useState(false);

  const crud = useResourceCrud<PlantillaRow>({ resourceKey: "plantillas", basePath: "/api/v1/plantillas" });
  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });
  const disciplinas = useResourceCrud<DisciplinaRow>({ resourceKey: "disciplinas", basePath: "/api/v1/disciplinas" });
  const perfiles = useResourceCrud<PerfilRow, { jugador_id: number; disciplina_id: number }>({
    resourceKey: "perfiles",
    basePath: "/api/v1/perfiles",
  });
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
  // Para resolver-o-crear el perfil al confirmar el alta: id existente por
  // (jugador_id, disciplina_id), o null si todavía no hay perfil.
  const perfilIdPorJugadorYDisciplina = useMemo(
    () => new Map((perfiles.listQuery.data ?? []).map((p) => [`${p.jugador_id}-${p.disciplina_id}`, p.id])),
    [perfiles.listQuery.data],
  );

  function etiquetaPerfil(perfilId: number): string {
    const p = perfilPorId.get(perfilId);
    if (!p) return `Perfil #${perfilId}`;
    return `${nombreJugador.get(p.jugador_id) ?? `Jugador #${p.jugador_id}`} — ${nombreDisciplina.get(p.disciplina_id) ?? `Disciplina #${p.disciplina_id}`}`;
  }
  function etiquetaInscripcion(inscripcionId: number): string {
    const i = inscripcionPorId.get(inscripcionId);
    if (!i) return `Inscripción #${inscripcionId}`;
    return `${nombreTorneo.get(i.torneo_id) ?? `Torneo #${i.torneo_id}`} — ${nombreEquipo.get(i.equipo_id) ?? `Equipo #${i.equipo_id}`}`;
  }

  function volver() {
    setModo({ tipo: "lista" });
    setErrorPerfil(null);
  }

  async function crearVinculo(values: Record<string, ResourceFieldValue>) {
    setErrorPerfil(null);
    const jugadorId = values.jugador_id as number;
    const disciplinaId = values.disciplina_id as number;
    let perfilId = perfilIdPorJugadorYDisciplina.get(`${jugadorId}-${disciplinaId}`) ?? null;

    if (perfilId == null) {
      setResolviendoPerfil(true);
      try {
        const nuevoPerfil = await perfiles.create.mutateAsync({ jugador_id: jugadorId, disciplina_id: disciplinaId });
        perfilId = nuevoPerfil.id;
      } catch (e) {
        setErrorPerfil(apiErrorMessage(e, "No se pudo crear el perfil del jugador en esa disciplina."));
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
              name: "disciplina_id",
              label: "Disciplina",
              type: "reference",
              required: true,
              optionsLoading: disciplinas.listQuery.isLoading,
              options: (disciplinas.listQuery.data ?? []).map((d) => ({ value: d.id, label: d.nombre })),
            },
            {
              name: "inscripcion_torneo_id",
              label: "Torneo — Equipo",
              type: "reference",
              required: true,
              optionsLoading: inscripciones.listQuery.isLoading || torneos.listQuery.isLoading || equipos.listQuery.isLoading,
              options: (inscripciones.listQuery.data ?? []).map((i) => ({ value: i.id, label: etiquetaInscripcion(i.id) })),
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
    const initialValues: Record<string, ResourceFieldValue> = {
      dorsal: modo.fila.dorsal,
      estado: modo.fila.estado,
    };
    return (
      <div className="page">
        <h1>Editar vínculo</h1>
        <p className="muted">
          {etiquetaPerfil(modo.fila.jugador_perfil_id)} en {etiquetaInscripcion(modo.fila.inscripcion_torneo_id)}
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
          {etiquetaPerfil(modo.fila.jugador_perfil_id)} sale de {etiquetaInscripcion(modo.fila.inscripcion_torneo_id)} — libera el dorsal para otro jugador.
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
        <div>
          <button type="button" onClick={() => setModo({ tipo: "crear" })}>
            + Nuevo vínculo
          </button>{" "}
          <Link to="/torneo-admin/plantillas/lote">
            <button type="button">+ Registro por lote</button>
          </Link>
        </div>
      </div>
      <ResourceTable<PlantillaRow>
        rows={crud.listQuery.data ?? []}
        columns={[
          { key: "perfil", label: "Jugador — Disciplina", render: (r) => etiquetaPerfil(r.jugador_perfil_id) },
          { key: "inscripcion", label: "Torneo — Equipo", render: (r) => etiquetaInscripcion(r.inscripcion_torneo_id) },
          { key: "dorsal", label: "Dorsal", render: (r) => (r.dorsal ? `#${r.dorsal}` : "—") },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage="No hay jugadores vinculados a ningún equipo todavía."
        onSelect={(fila) => setModo({ tipo: "editar", fila })}
        onSoftDelete={(fila) => setModo({ tipo: "baja", fila })}
        softDeleteLabel="Dar de baja"
        estadosDeBaja={["Inactivo", "Traspasado"]}
      />
    </div>
  );
}
