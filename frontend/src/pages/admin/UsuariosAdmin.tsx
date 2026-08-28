import { useAuth } from "../../auth/useAuth";
import { SimpleResourceAdminPage } from "../torneo-admin/SimpleResourceAdminPage";

interface UsuarioRow {
  id: number;
  username: string;
  nombre: string;
  rol: string;
  estado: string;
  fecha_registro: string;
}

const ROLES = ["AdminGeneral", "TorneoAdmin", "Arbitro", "Publico"];

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR");

/** Gestión de usuarios (roles-3-modulos-plan.md, Fase 4) — mismo patrón
 * exacto que TorneosAdmin.tsx (D1 de Fase 2), reusado sin cambios de
 * fondo: el backend de esta pantalla ya existía completo desde Fase 1/2. */
export function UsuariosAdminPage() {
  const { session } = useAuth();

  return (
    <SimpleResourceAdminPage<UsuarioRow>
      resourceKey="usuarios"
      basePath="/api/v1/usuarios"
      title="Usuarios"
      emptyMessage="No hay usuarios creados todavía."
      isSelf={(row) => row.id === session?.id}
      createFields={[
        { name: "username", label: "Usuario", type: "text", required: true },
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "password", label: "Contraseña", type: "password", required: true },
        { name: "rol", label: "Rol", type: "select", choices: ROLES, required: true },
      ]}
      editFields={[
        { name: "nombre", label: "Nombre", type: "text", required: true },
        { name: "rol", label: "Rol", type: "select", choices: ROLES, required: true },
        { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo"] },
        // No required: dejar en blanco = no cambiar (UsuarioUpdate.password
        // es opcional, roles-3-modulos-plan.md Fase 4).
        { name: "password", label: "Nueva contraseña (dejar en blanco para no cambiar)", type: "password" },
      ]}
      columns={[
        { key: "username", label: "Usuario" },
        { key: "nombre", label: "Nombre" },
        { key: "rol", label: "Rol" },
        { key: "estado", label: "Estado" },
        { key: "fecha_registro", label: "Registrado", render: (r) => formatearFecha(r.fecha_registro) },
      ]}
    />
  );
}
