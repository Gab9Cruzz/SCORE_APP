import { SimpleResourceAdminPage } from "./SimpleResourceAdminPage";

interface DisciplinaRow {
  id: number;
  nombre: string;
  tipo: string;
  estado: string;
}

/** Catálogo de disciplinas (equipos-jugadores-plan.md, Fase 1 backend) —
 * reemplaza al texto libre que antes tenía TORNEO.Disciplina. Tipo="Equipo"
 * no necesita Modalidad en el torneo; "Individual" sí la exige
 * (fn_validar_torneo_modalidad, ver TorneosAdmin.tsx). */
export function DisciplinasAdminPage() {
  return (
    <SimpleResourceAdminPage<DisciplinaRow>
      resourceKey="disciplinas"
      basePath="/api/v1/disciplinas"
      title="Disciplinas"
      emptyMessage="No hay disciplinas creadas todavía."
      createFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "tipo", label: "Tipo", type: "select", required: true, choices: ["Equipo", "Individual"] },
      ]}
      editFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "tipo", label: "Tipo", type: "select", required: true, choices: ["Equipo", "Individual"] },
        { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo"] },
      ]}
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "tipo", label: "Tipo" },
        { key: "estado", label: "Estado" },
      ]}
    />
  );
}
