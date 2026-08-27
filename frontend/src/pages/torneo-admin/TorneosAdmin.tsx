import { useMemo } from "react";
import { useResourceCrud } from "../../hooks/useResourceCrud";
import { SimpleResourceAdminPage } from "./SimpleResourceAdminPage";

interface TorneoRow {
  id: number;
  nombre: string;
  disciplina_id: number;
  modalidad_id: number | null;
  fecha_inicio: string;
  fecha_fin: string;
  estado: string;
}
interface DisciplinaRow {
  id: number;
  nombre: string;
}
interface ModalidadRow {
  id: number;
  nombre: string;
}

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR");

/** disciplina_id/modalidad_id son campos "reference" — a diferencia de
 * JugadoresAdmin.tsx, los fields/columns no pueden ser un literal a nivel
 * de módulo, necesitan las listas cargadas. modalidad_id NO es
 * `required`: la base decide si hace falta según Disciplina.Tipo
 * (fn_validar_torneo_modalidad, 06_triggers.sql) — el form no filtra las
 * opciones de Modalidad por la Disciplina elegida (ResourceForm no
 * soporta campos condicionados entre sí todavía), así que un torneo de
 * disciplina "Equipo" con una modalidad elegida por error se rechaza con
 * el mensaje del trigger, no se previene acá. */
export function TorneosAdminPage() {
  const disciplinas = useResourceCrud<DisciplinaRow>({ resourceKey: "disciplinas", basePath: "/api/v1/disciplinas" });
  const modalidades = useResourceCrud<ModalidadRow>({ resourceKey: "modalidades", basePath: "/api/v1/modalidades" });

  const nombreDisciplina = useMemo(
    () => new Map((disciplinas.listQuery.data ?? []).map((d) => [d.id, d.nombre])),
    [disciplinas.listQuery.data],
  );

  const campoDisciplina = {
    name: "disciplina_id",
    label: "Disciplina",
    type: "reference" as const,
    required: true,
    optionsLoading: disciplinas.listQuery.isLoading,
    options: (disciplinas.listQuery.data ?? []).map((d) => ({ value: d.id, label: d.nombre })),
  };
  const campoModalidad = {
    name: "modalidad_id",
    label: "Modalidad (solo disciplinas individuales)",
    type: "reference" as const,
    optionsLoading: modalidades.listQuery.isLoading,
    options: (modalidades.listQuery.data ?? []).map((m) => ({ value: m.id, label: m.nombre })),
  };

  return (
    <SimpleResourceAdminPage<TorneoRow>
      resourceKey="torneos"
      basePath="/api/v1/torneos"
      title="Torneos"
      emptyMessage="No hay torneos creados todavía."
      createFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        campoDisciplina,
        campoModalidad,
        { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
        { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
      ]}
      editFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        campoDisciplina,
        campoModalidad,
        { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
        { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
        { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo", "Finalizado"] },
      ]}
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "disciplina_id", label: "Disciplina", render: (r) => nombreDisciplina.get(r.disciplina_id) ?? `#${r.disciplina_id}` },
        { key: "fecha_inicio", label: "Inicio", render: (r) => formatearFecha(r.fecha_inicio) },
        { key: "fecha_fin", label: "Fin", render: (r) => formatearFecha(r.fecha_fin) },
        { key: "estado", label: "Estado" },
      ]}
    />
  );
}
