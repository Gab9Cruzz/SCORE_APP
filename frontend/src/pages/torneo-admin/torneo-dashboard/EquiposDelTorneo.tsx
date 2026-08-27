import { useMemo, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { ResourceTable } from "../../../components/admin/ResourceTable";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import type { RegistroLotePreResuelto } from "../RegistroLoteAdmin";
import { ModalAgregarEquipo } from "./ModalAgregarEquipo";
import type { TorneoDashboardContext } from "./TorneoDashboard";

interface InscripcionRow {
  id: number;
  torneo_id: number;
  equipo_id: number;
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

/** Sub-pestaña "Equipos" del dashboard scoped (torneos-admin-plan.md,
 * journey pasos 3-5). A diferencia de EquiposAdmin.tsx (catálogo global de
 * equipos), esto lista solo los INSCRITOS en este torneo puntual —
 * `?torneo_id=` en /inscripciones y /plantillas (D-Eng-3). */
export function EquiposDelTorneoPage() {
  const { torneoId, torneoContexto, modalidadId } = useOutletContext<TorneoDashboardContext>();
  const navigate = useNavigate();
  const [modalAbierto, setModalAbierto] = useState(false);

  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
    listParams: { torneo_id: torneoId },
  });
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

  const inscritosIds = new Set((inscripciones.listQuery.data ?? []).map((i) => i.equipo_id));

  function irARegistroLote(fila: InscripcionRow) {
    // EC-22 del plan: un equipo con 0 jugadores es válido — este link
    // reusa el mismo destino que "Crear equipo nuevo" para completar la
    // plantilla más tarde, sin duplicar la pantalla dividida.
    const contexto: RegistroLotePreResuelto = {
      inscripcionTorneoId: fila.id,
      contexto: `${nombreEquipo.get(fila.equipo_id) ?? `Equipo #${fila.equipo_id}`} — ${torneoContexto}`,
      volverA: `/torneo-admin/torneos/${torneoId}/equipos`,
    };
    navigate("/torneo-admin/plantillas/lote", { state: contexto });
  }

  return (
    <div>
      <div className="page__header">
        <h2>Equipos inscritos</h2>
        <button type="button" onClick={() => setModalAbierto(true)}>
          + Agregar Equipo
        </button>
      </div>
      <ResourceTable<InscripcionRow>
        rows={inscripciones.listQuery.data ?? []}
        columns={[
          { key: "equipo", label: "Equipo", render: (r) => nombreEquipo.get(r.equipo_id) ?? `#${r.equipo_id}` },
          { key: "jugadores", label: "Jugadores", render: (r) => String(rosterCount.get(r.id) ?? 0) },
          { key: "estado", label: "Estado" },
        ]}
        isLoading={inscripciones.listQuery.isLoading || equipos.listQuery.isLoading}
        isError={inscripciones.listQuery.isError}
        emptyMessage="Sin equipos inscritos todavía en esta edición."
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
        <ModalAgregarEquipo
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
