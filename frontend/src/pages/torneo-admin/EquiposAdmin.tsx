import { SimpleResourceAdminPage } from "./SimpleResourceAdminPage";

interface EquipoRow {
  id: number;
  nombre: string;
  estado: string;
}

export function EquiposAdminPage() {
  return (
    <SimpleResourceAdminPage<EquipoRow>
      resourceKey="equipos"
      basePath="/api/v1/equipos"
      title="Equipos"
      emptyMessage="No hay equipos creados todavía."
      createFields={[{ name: "nombre", label: "Nombre", type: "text", required: true }]}
      editFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo"] },
      ]}
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "estado", label: "Estado" },
      ]}
    />
  );
}
