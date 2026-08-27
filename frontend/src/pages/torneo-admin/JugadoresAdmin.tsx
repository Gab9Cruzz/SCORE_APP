import { Link } from "react-router-dom";
import { SimpleResourceAdminPage } from "./SimpleResourceAdminPage";

interface JugadorRow {
  id: number;
  nombre: string;
  cedula: string;
  correo_electronico: string;
  estado: string;
}

export function JugadoresAdminPage() {
  return (
    <SimpleResourceAdminPage<JugadorRow>
      resourceKey="jugadores"
      basePath="/api/v1/jugadores"
      title="Jugadores"
      emptyMessage="No hay jugadores creados todavía."
      createFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "cedula", label: "Cédula", type: "text", required: true },
        { name: "correo_electronico", label: "Correo electrónico", type: "text", required: true },
      ]}
      editFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "cedula", label: "Cédula", type: "text", required: true },
        { name: "correo_electronico", label: "Correo electrónico", type: "text", required: true },
        { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo"] },
      ]}
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "cedula", label: "Cédula" },
        { key: "correo_electronico", label: "Correo" },
        { key: "estado", label: "Estado" },
      ]}
      renderRowExtra={(r) => (
        <Link key="perfil" to={`/torneo-admin/jugadores/${r.id}/perfil`}>
          Ver perfil
        </Link>
      )}
    />
  );
}
