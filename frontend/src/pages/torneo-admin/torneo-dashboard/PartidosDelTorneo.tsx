import { useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import type { Equipo as EquipoRow } from "../../../api/types";
import { apiErrorMessage } from "../../../api/client";
import { ResourceForm, type ResourceFieldValue } from "../../../components/admin/ResourceForm";
import { ResourceTable } from "../../../components/admin/ResourceTable";
import { LIMITE_LISTA, useResourceCrud } from "../../../hooks/useResourceCrud";
import { MotorFormatosPanel } from "./MotorFormatosPanel";
import type { TorneoDashboardContext } from "./TorneoDashboard";

interface PartidoRow {
  id: number;
  equipos_id_local: number | null;
  equipos_id_visitante: number | null;
  fecha_partido: string;
  jornada: number | null;
  fase: string;
  grupo: string | null;
  fase_id: number | null;
  grupo_id: number | null;
  estado: string;
  arbitro_id: number | null;
  // 3B-13 (docs/plans/cierre-backlog-todos-plan.md).
  es_walkover: boolean;
  walkover_equipo_ausente_id: number | null;
}
interface InscripcionRow {
  id: number;
  equipo_id: number;
  estado: string;
}
interface UsuarioRow {
  id: number;
  username: string;
  nombre: string;
}

const FASES = ["Regular", "Grupos", "Octavos", "Cuartos", "Semifinal", "Final", "Tercer puesto"];
const ESTADOS = ["Programado", "En curso", "Finalizado", "Cancelado"];

type Modo = { tipo: "lista" } | { tipo: "crear" } | { tipo: "editar"; fila: PartidoRow };

const formatearFecha = (iso: string) => new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });

/** Sub-pestaña "Partidos" del dashboard scoped — mismo alcance funcional
 * que la extinta pestaña global PartidosAdmin.tsx (Fase 3: consolidación).
 * torneo_id ya no se pregunta (es el de este dashboard); el picker de
 * equipos sigue acotado a los inscritos y no cancelados, como ya hacía la
 * página global (trg_partidos_validar_inscripcion en 06_triggers.sql
 * rechaza si no, esto es solo UX). */
export function PartidosDelTorneoPage() {
  const { torneoId, torneoContexto, formato } = useOutletContext<TorneoDashboardContext>();
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });

  const crud = useResourceCrud<PartidoRow>({
    resourceKey: "partidos",
    basePath: "/api/v1/partidos",
    listParams: { torneo_id: torneoId },
  });
  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });
  const inscritos = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
    listParams: { torneo_id: torneoId },
  });

  const nombreEquipo = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );
  const equiposInscritos = useMemo(() => {
    const filas = inscritos.listQuery.data ?? [];
    return filas
      .filter((i) => i.estado === "Inscrito" || i.estado === "Confirmado")
      .map((i) => ({ value: i.equipo_id, label: nombreEquipo.get(i.equipo_id) ?? `#${i.equipo_id}` }));
  }, [inscritos.listQuery.data, nombreEquipo]);

  function volver() {
    setModo({ tipo: "lista" });
  }

  if (modo.tipo === "crear") {
    return (
      <CrearPartidoDelTorneo
        torneoId={torneoId}
        torneoContexto={torneoContexto}
        equiposInscritos={equiposInscritos}
        cargandoEquipos={inscritos.listQuery.isLoading}
        onDone={volver}
        onCancel={volver}
      />
    );
  }
  if (modo.tipo === "editar") {
    return <EditarPartidoDelTorneo fila={modo.fila} onDone={volver} onCancel={volver} />;
  }

  return (
    <div>
      <MotorFormatosPanel
        torneoId={torneoId}
        formato={formato}
        partidos={crud.listQuery.data ?? []}
        equiposInscritosCount={equiposInscritos.length}
      />
      <div className="page__header">
        <h2>Partidos de esta edición</h2>
        <button type="button" onClick={() => setModo({ tipo: "crear" })}>
          + Nuevo
        </button>
      </div>
      {crud.truncado && (
        <p className="muted">Mostrando los primeros {LIMITE_LISTA} partidos de esta edición.</p>
      )}
      {crud.customAction.isError && <p className="error-text">{apiErrorMessage(crud.customAction.error)}</p>}
      <ResourceTable<PartidoRow>
        rows={crud.listQuery.data ?? []}
        columns={[
          {
            key: "partido",
            label: "Partido",
            render: (r) =>
              `${r.equipos_id_local != null ? (nombreEquipo.get(r.equipos_id_local) ?? "?") : "Por definir"} vs ${
                r.equipos_id_visitante != null ? (nombreEquipo.get(r.equipos_id_visitante) ?? "?") : "Por definir"
              }`,
          },
          { key: "fecha_partido", label: "Fecha", render: (r) => formatearFecha(r.fecha_partido) },
          { key: "fase", label: "Fase" },
          {
            key: "estado",
            label: "Estado",
            render: (r) => (
              <>
                {r.estado}
                {r.es_walkover && (
                  <span className="badge badge--archivado" title="Cerrado por walkover (ausencia)">
                    {" "}
                    W.O.
                  </span>
                )}
              </>
            ),
          },
        ]}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage="Sin partidos programados todavía en esta edición."
        onSelect={(fila) => setModo({ tipo: "editar", fila })}
        onSoftDelete={(fila) => crud.softDelete.mutate(fila.id)}
        softDeleteLabel="Cancelar"
        softDeletePending={crud.softDelete.isPending}
        estadosDeBaja={["Cancelado"]}
        extraActions={(fila) => (
          <AccionWalkover
            partido={fila}
            nombreLocal={fila.equipos_id_local != null ? (nombreEquipo.get(fila.equipos_id_local) ?? "?") : null}
            nombreVisitante={
              fila.equipos_id_visitante != null ? (nombreEquipo.get(fila.equipos_id_visitante) ?? "?") : null
            }
            onMarcar={(equipoAusenteId) =>
              crud.customAction.mutate({
                path: `/api/v1/partidos/${fila.id}/walkover`,
                body: { equipo_ausente_id: equipoAusenteId },
              })
            }
            marcando={crud.customAction.isPending}
          />
        )}
      />
    </div>
  );
}

/** 3B-13 (docs/plans/cierre-backlog-todos-plan.md): "no se presentó" para
 * UN partido puntual — botón chico, sin pantalla aparte, mismo criterio
 * que el resto de las acciones de fila de este dashboard. Solo se ofrece
 * cuando tiene sentido (partido con los dos equipos definidos, todavía no
 * cerrado) — el backend igual re-valida todo (estado, habilitación de
 * Liga/grupos, etc.), esto es solo para no mostrar el botón donde ya se
 * sabe que va a fallar. */
function AccionWalkover(props: {
  partido: PartidoRow;
  nombreLocal: string | null;
  nombreVisitante: string | null;
  onMarcar: (equipoAusenteId: number) => void;
  marcando: boolean;
}) {
  const { partido, nombreLocal, nombreVisitante, onMarcar, marcando } = props;
  const [abierto, setAbierto] = useState(false);

  const puedeOfrecerse =
    (partido.estado === "Programado" || partido.estado === "En curso") &&
    partido.equipos_id_local != null &&
    partido.equipos_id_visitante != null;
  if (!puedeOfrecerse) return null;

  if (!abierto) {
    return (
      <button type="button" className="link-button" onClick={() => setAbierto(true)}>
        Walkover
      </button>
    );
  }

  return (
    <span className="accion-walkover">
      <span className="muted">¿Quién no se presentó?</span>
      <button
        type="button"
        disabled={marcando}
        onClick={() => {
          onMarcar(partido.equipos_id_local as number);
          setAbierto(false);
        }}
      >
        {nombreLocal}
      </button>
      <button
        type="button"
        disabled={marcando}
        onClick={() => {
          onMarcar(partido.equipos_id_visitante as number);
          setAbierto(false);
        }}
      >
        {nombreVisitante}
      </button>
      <button type="button" className="link-button" onClick={() => setAbierto(false)}>
        Cancelar
      </button>
    </span>
  );
}

interface CrearPartidoProps {
  torneoId: number;
  torneoContexto: string;
  equiposInscritos: { value: number; label: string }[];
  cargandoEquipos: boolean;
  onDone: () => void;
  onCancel: () => void;
}

function CrearPartidoDelTorneo({ torneoId, torneoContexto, equiposInscritos, cargandoEquipos, onDone, onCancel }: CrearPartidoProps) {
  const [equipoLocal, setEquipoLocal] = useState<number | null>(null);
  const [equipoVisitante, setEquipoVisitante] = useState<number | null>(null);
  const [fechaPartido, setFechaPartido] = useState("");
  const [jornada, setJornada] = useState("");
  const [fase, setFase] = useState("Regular");
  const [grupo, setGrupo] = useState("");

  const crud = useResourceCrud<PartidoRow>({ resourceKey: "partidos", basePath: "/api/v1/partidos" });

  const puedeConfirmar = equipoLocal !== null && equipoVisitante !== null && equipoLocal !== equipoVisitante && fechaPartido !== "";

  function confirmar() {
    if (!puedeConfirmar) return;
    crud.create.mutate(
      {
        torneo_id: torneoId,
        equipos_id_local: equipoLocal,
        equipos_id_visitante: equipoVisitante,
        fecha_partido: fechaPartido,
        jornada: jornada ? Number(jornada) : null,
        fase,
        grupo: grupo || null,
      } as never,
      { onSuccess: onDone },
    );
  }

  return (
    <div>
      <h2>Nuevo partido — {torneoContexto}</h2>
      <div className="resource-form">
        {!cargandoEquipos && equiposInscritos.length < 2 && (
          <p className="error-text">Este torneo tiene menos de 2 equipos inscritos — inscribí equipos antes de programar un partido.</p>
        )}
        <label>
          Equipo local
          <select
            value={equipoLocal ?? ""}
            onChange={(e) => setEquipoLocal(e.target.value ? Number(e.target.value) : null)}
            disabled={cargandoEquipos}
          >
            <option value="">{cargandoEquipos ? "Cargando..." : "Elegir..."}</option>
            {equiposInscritos.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Equipo visitante
          <select
            value={equipoVisitante ?? ""}
            onChange={(e) => setEquipoVisitante(e.target.value ? Number(e.target.value) : null)}
            disabled={cargandoEquipos}
          >
            <option value="">{cargandoEquipos ? "Cargando..." : "Elegir..."}</option>
            {equiposInscritos
              .filter((o) => o.value !== equipoLocal)
              .map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
          </select>
        </label>
        <label>
          Fecha y hora
          <input type="datetime-local" value={fechaPartido} onChange={(e) => setFechaPartido(e.target.value)} />
        </label>
        <label>
          Jornada
          <input type="number" value={jornada} onChange={(e) => setJornada(e.target.value)} />
        </label>
        <label>
          Fase
          <select value={fase} onChange={(e) => setFase(e.target.value)}>
            {FASES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label>
          Grupo
          <input type="text" value={grupo} onChange={(e) => setGrupo(e.target.value)} />
        </label>
        {crud.create.isError && <p className="error-text">{apiErrorMessage(crud.create.error)}</p>}
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={onCancel}>
            Cancelar
          </button>
          <button type="button" onClick={confirmar} disabled={!puedeConfirmar || crud.create.isPending}>
            {crud.create.isPending ? "Guardando..." : "Crear partido"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditarPartidoDelTorneo({ fila, onDone, onCancel }: { fila: PartidoRow; onDone: () => void; onCancel: () => void }) {
  const crud = useResourceCrud<PartidoRow>({ resourceKey: "partidos", basePath: "/api/v1/partidos" });
  const arbitros = useResourceCrud<UsuarioRow>({
    resourceKey: "usuarios-arbitros",
    basePath: "/api/v1/usuarios",
    listParams: { rol: "Arbitro" },
  });

  const initialValues: Record<string, ResourceFieldValue> = {
    fecha_partido: fila.fecha_partido.slice(0, 16),
    jornada: fila.jornada,
    fase: fila.fase,
    grupo: fila.grupo,
    estado: fila.estado,
    arbitro_id: fila.arbitro_id,
  };

  return (
    <div>
      <h2>Editar partido #{fila.id}</h2>
      <ResourceForm
        fields={[
          { name: "fecha_partido", label: "Fecha y hora", type: "datetime", required: true },
          { name: "jornada", label: "Jornada", type: "number" },
          { name: "fase", label: "Fase", type: "select", choices: FASES },
          { name: "grupo", label: "Grupo", type: "text" },
          { name: "estado", label: "Estado", type: "select", choices: ESTADOS },
          {
            name: "arbitro_id",
            label: "Árbitro asignado",
            type: "reference",
            optionsLoading: arbitros.listQuery.isLoading,
            options: (arbitros.listQuery.data ?? []).map((a) => ({ value: a.id, label: `${a.nombre} (${a.username})` })),
          },
        ]}
        initialValues={initialValues}
        onSubmit={(values) => crud.update.mutate({ id: fila.id, body: values as never }, { onSuccess: onDone })}
        submitting={crud.update.isPending}
        submitError={crud.update.isError ? apiErrorMessage(crud.update.error) : null}
        submitLabel="Guardar cambios"
        onCancel={onCancel}
      />
    </div>
  );
}
