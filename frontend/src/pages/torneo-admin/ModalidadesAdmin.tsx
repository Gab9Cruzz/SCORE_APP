import { useMemo } from "react";
import { useResourceCrud } from "../../hooks/useResourceCrud";
import { SimpleResourceAdminPage } from "./SimpleResourceAdminPage";

interface ModalidadRow {
  id: number;
  disciplina_id: number;
  nombre: string;
  tamano_equipo: number;
  estado: string;
}
interface DisciplinaRow {
  id: number;
  nombre: string;
}

/** disciplina_id es un campo "reference" (necesita las opciones cargadas
 * de /disciplinas), así que a diferencia de JugadoresAdmin/DisciplinasAdmin
 * los fields no pueden ser un literal a nivel de módulo — se arman adentro
 * del componente, mismo motivo que TorneosAdmin.tsx. */
export function ModalidadesAdminPage() {
  const disciplinas = useResourceCrud<DisciplinaRow>({ resourceKey: "disciplinas", basePath: "/api/v1/disciplinas" });

  const opcionesDisciplina = useMemo(
    () => (disciplinas.listQuery.data ?? []).map((d) => ({ value: d.id, label: d.nombre })),
    [disciplinas.listQuery.data],
  );
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
    options: opcionesDisciplina,
  };

  return (
    <SimpleResourceAdminPage<ModalidadRow>
      resourceKey="modalidades"
      basePath="/api/v1/modalidades"
      title="Modalidades"
      emptyMessage="No hay modalidades creadas todavía."
      createFields={[
        campoDisciplina,
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "tamano_equipo", label: "Tamaño de equipo", type: "number", required: true },
      ]}
      editFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "tamano_equipo", label: "Tamaño de equipo", type: "number", required: true },
        { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo"] },
      ]}
      columns={[
        { key: "disciplina_id", label: "Disciplina", render: (r) => nombreDisciplina.get(r.disciplina_id) ?? `#${r.disciplina_id}` },
        { key: "nombre", label: "Nombre" },
        { key: "tamano_equipo", label: "Tamaño de equipo" },
        { key: "estado", label: "Estado" },
      ]}
    />
  );
}
