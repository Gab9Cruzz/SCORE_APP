import { SimpleResourceAdminPage } from "./SimpleResourceAdminPage";

interface TorneoRow {
  id: number;
  nombre: string;
  disciplina: string;
  fecha_inicio: string;
  fecha_fin: string;
  estado: string;
}

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR");

export function TorneosAdminPage() {
  return (
    <SimpleResourceAdminPage<TorneoRow>
      resourceKey="torneos"
      basePath="/api/v1/torneos"
      title="Torneos"
      emptyMessage="No hay torneos creados todavía."
      createFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "disciplina", label: "Disciplina", type: "text", required: true },
        { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
        { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
      ]}
      editFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "disciplina", label: "Disciplina", type: "text", required: true },
        { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
        { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
        { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo", "Finalizado"] },
      ]}
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "disciplina", label: "Disciplina" },
        { key: "fecha_inicio", label: "Inicio", render: (r) => formatearFecha(r.fecha_inicio) },
        { key: "fecha_fin", label: "Fin", render: (r) => formatearFecha(r.fecha_fin) },
        { key: "estado", label: "Estado" },
      ]}
    />
  );
}
