import { useMemo, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { ResourceTable } from "../../../components/admin/ResourceTable";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import type { RegistroLotePreResuelto } from "../RegistroLoteAdmin";
import { ModalAgregarInscripcion } from "./ModalAgregarInscripcion";
import type { TorneoDashboardContext } from "./TorneoDashboard";

interface InscripcionRow {
  id: number;
  torneo_id: number;
  equipo_id: number | null;
  jugador_perfil_id: number | null;
  estado: string;
}
interface EquipoRow {
  id: number;
  nombre: string;
}
interface PlantillaRow {
  id: number;
  inscripcion_torneo_id: number;
  estado: string;
}
interface ModalidadRow {
  id: number;
  tamano_equipo: number;
}
interface PerfilRow {
  id: number;
  jugador_id: number;
}
interface JugadorRow {
  id: number;
  nombre: string;
}

/** Sub-pestaña "Equipos" del dashboard scoped (torneos-admin-plan.md,
 * journey pasos 3-5) — se ramifica por Modalidad.tamano_equipo del torneo
 * (ediciones-catalogo-disciplinas-plan.md, Decisión B1): Individual
 * (tamano_equipo=1) lista Jugadores inscritos DIRECTO (jugador_perfil_id,
 * sin fila en EQUIPOS); Pareja/Conjunto (>=2) siguen listando Equipos
 * inscritos, sin cambios de fondo. A diferencia de EquiposAdmin.tsx
 * (catálogo global de equipos), esto lista solo los INSCRITOS en este
 * torneo puntual — `?torneo_id=` en /inscripciones y /plantillas (D-Eng-3). */
export function EquiposDelTorneoPage() {
  const { torneoId, disciplinaId, torneoContexto, modalidadId } = useOutletContext<TorneoDashboardContext>();
  const navigate = useNavigate();
  const [modalAbierto, setModalAbierto] = useState(false);

  const modalidades = useResourceCrud<ModalidadRow>({ resourceKey: "modalidades", basePath: "/api/v1/modalidades" });
  const tamanoEquipo = (modalidades.listQuery.data ?? []).find((m) => m.id === modalidadId)?.tamano_equipo;
  const esIndividual = tamanoEquipo === 1;

  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
    listParams: { torneo_id: torneoId },
  });

  if (esIndividual) {
    return (
      <VistaIndividual
        torneoId={torneoId}
        disciplinaId={disciplinaId}
        torneoContexto={torneoContexto}
        inscripciones={inscripciones}
        modalAbierto={modalAbierto}
        setModalAbierto={setModalAbierto}
        modalidadId={modalidadId}
      />
    );
  }

  return (
    <VistaEquipo
      torneoId={torneoId}
      torneoContexto={torneoContexto}
      inscripciones={inscripciones}
      esPareja={tamanoEquipo === 2}
      modalAbierto={modalAbierto}
      setModalAbierto={setModalAbierto}
      modalidadId={modalidadId}
      navigate={navigate}
    />
  );
}

/** Individual: sin ningún equipo de por medio — la inscripción ES el
 * jugador. Nombre resuelto vía perfiles+jugadores, mismo patrón que
 * PlantillasDelTorneo.tsx (jugador_perfil_id → jugador_id → nombre). */
function VistaIndividual(props: {
  torneoId: number;
  disciplinaId: number;
  torneoContexto: string;
  inscripciones: ReturnType<typeof useResourceCrud<InscripcionRow>>;
  modalAbierto: boolean;
  setModalAbierto: (v: boolean) => void;
  modalidadId: number;
}) {
  const { torneoId, disciplinaId, torneoContexto, inscripciones, modalAbierto, setModalAbierto, modalidadId } = props;

  const perfiles = useResourceCrud<PerfilRow>({
    resourceKey: "perfiles",
    basePath: "/api/v1/perfiles",
    listParams: { disciplina_id: disciplinaId },
  });
  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });

  const nombreJugador = useMemo(
    () => new Map((jugadores.listQuery.data ?? []).map((j) => [j.id, j.nombre])),
    [jugadores.listQuery.data],
  );
  const nombrePorPerfilId = useMemo(() => {
    const jugadorIdPorPerfil = new Map((perfiles.listQuery.data ?? []).map((p) => [p.id, p.jugador_id]));
    return (perfilId: number | null) =>
      perfilId != null ? (nombreJugador.get(jugadorIdPorPerfil.get(perfilId) ?? -1) ?? `Perfil #${perfilId}`) : "—";
  }, [perfiles.listQuery.data, nombreJugador]);

  return (
    <div>
      <div className="page__header">
        <h2>Jugadores inscritos</h2>
        <button type="button" onClick={() => setModalAbierto(true)}>
          + Agregar Jugador
        </button>
      </div>
      <ResourceTable<InscripcionRow>
        rows={inscripciones.listQuery.data ?? []}
        columns={[
          { key: "jugador", label: "Jugador", render: (r) => nombrePorPerfilId(r.jugador_perfil_id) },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={inscripciones.listQuery.isLoading || perfiles.listQuery.isLoading || jugadores.listQuery.isLoading}
        isError={inscripciones.listQuery.isError}
        emptyMessage="Sin jugadores inscritos todavía en esta edición."
        onSoftDelete={(fila) => inscripciones.update.mutate({ id: fila.id, body: { estado: "Cancelado" } as never })}
        softDeleteLabel="Cancelar inscripción"
        softDeletePending={inscripciones.update.isPending}
        estadosDeBaja={["Cancelado"]}
      />
      {modalAbierto && (
        <ModalAgregarInscripcion
          torneoId={torneoId}
          torneoContexto={torneoContexto}
          torneoModalidadId={modalidadId}
          equiposYaInscritosIds={new Set()}
          onClose={() => setModalAbierto(false)}
        />
      )}
    </div>
  );
}

/** Pareja/Conjunto: camino de Equipo, sin cambios de fondo respecto a
 * antes de ediciones-catalogo-disciplinas-plan.md — solo el título/botón
 * cambian según sea Pareja o Conjunto. */
function VistaEquipo(props: {
  torneoId: number;
  torneoContexto: string;
  inscripciones: ReturnType<typeof useResourceCrud<InscripcionRow>>;
  esPareja: boolean;
  modalAbierto: boolean;
  setModalAbierto: (v: boolean) => void;
  modalidadId: number;
  navigate: ReturnType<typeof useNavigate>;
}) {
  const { torneoId, torneoContexto, inscripciones, esPareja, modalAbierto, setModalAbierto, modalidadId, navigate } = props;

  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });
  const plantillas = useResourceCrud<PlantillaRow>({
    resourceKey: "plantillas",
    basePath: "/api/v1/plantillas",
    listParams: { torneo_id: torneoId },
  });

  const nombreEquipo = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );
  const rosterCount = useMemo(() => {
    const m = new Map<number, number>();
    for (const p of plantillas.listQuery.data ?? []) {
      if (p.estado !== "Activo") continue;
      m.set(p.inscripcion_torneo_id, (m.get(p.inscripcion_torneo_id) ?? 0) + 1);
    }
    return m;
  }, [plantillas.listQuery.data]);

  const inscritosIds = new Set(
    (inscripciones.listQuery.data ?? []).flatMap((i) => (i.equipo_id != null ? [i.equipo_id] : [])),
  );

  function irARegistroLote(fila: InscripcionRow) {
    // EC-22 del plan: un equipo con 0 jugadores es válido — este link
    // reusa el mismo destino que "Crear equipo nuevo" para completar la
    // plantilla más tarde, sin duplicar la pantalla dividida.
    const contexto: RegistroLotePreResuelto = {
      inscripcionTorneoId: fila.id,
      contexto: `${nombreEquipo.get(fila.equipo_id ?? -1) ?? `Equipo #${fila.equipo_id}`} — ${torneoContexto}`,
      volverA: `/torneo-admin/torneos/${torneoId}/equipos`,
    };
    navigate("/torneo-admin/plantillas/lote", { state: contexto });
  }

  return (
    <div>
      <div className="page__header">
        <h2>{esPareja ? "Parejas inscritas" : "Equipos inscritos"}</h2>
        <button type="button" onClick={() => setModalAbierto(true)}>
          {esPareja ? "+ Agregar Pareja" : "+ Agregar Equipo"}
        </button>
      </div>
      <ResourceTable<InscripcionRow>
        rows={inscripciones.listQuery.data ?? []}
        columns={[
          { key: "equipo", label: esPareja ? "Pareja" : "Equipo", render: (r) => nombreEquipo.get(r.equipo_id ?? -1) ?? `#${r.equipo_id}` },
          { key: "jugadores", label: "Jugadores", render: (r) => String(rosterCount.get(r.id) ?? 0) },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={inscripciones.listQuery.isLoading || equipos.listQuery.isLoading}
        isError={inscripciones.listQuery.isError}
        emptyMessage={esPareja ? "Sin parejas inscritas todavía en esta edición." : "Sin equipos inscritos todavía en esta edición."}
        // Cancelar una inscripción reemplaza acá lo que hacía la extinta
        // pestaña global Inscripciones (Fase 3: consolidación) — mismo PATCH
        // directo {estado: "Cancelado"} que ya usaba InscripcionesAdmin.tsx,
        // no un DELETE (la tabla no lo tiene).
        onSoftDelete={(fila) => inscripciones.update.mutate({ id: fila.id, body: { estado: "Cancelado" } as never })}
        softDeleteLabel="Cancelar inscripción"
        softDeletePending={inscripciones.update.isPending}
        estadosDeBaja={["Cancelado"]}
        extraActions={(fila) => (
          <button type="button" className="link-button" onClick={() => irARegistroLote(fila)}>
            + Agregar jugadores
          </button>
        )}
      />
      {modalAbierto && (
        <ModalAgregarInscripcion
          torneoId={torneoId}
          torneoContexto={torneoContexto}
          torneoModalidadId={modalidadId}
          equiposYaInscritosIds={inscritosIds}
          onClose={() => setModalAbierto(false)}
        />
      )}
    </div>
  );
}
