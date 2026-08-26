import { SimpleResourceAdminPage } from "./SimpleResourceAdminPage";

interface JugadorRow {
  id: number;
  nombre: string;
  estado: string;
}

export function JugadoresAdminPage() {
  return (
    <SimpleResourceAdminPage<JugadorRow>
      resourceKey="jugadores"
      basePath="/api/v1/jugadores"
      title="Jugadores"
      emptyMessage="No hay jugadores creados todavía."
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
