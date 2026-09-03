import { useState } from "react";
import { useAuth } from "../../auth/useAuth";
import { useResourceCrud } from "../../hooks/useResourceCrud";
import { SimpleResourceAdminPage } from "../torneo-admin/SimpleResourceAdminPage";
import { AsignarTorneosModal } from "./AsignarTorneosModal";

interface UsuarioRow {
  id: number;
  username: string;
  nombre: string;
  rol: string;
  estado: string;
  licencia_activa: boolean;
  fecha_registro: string;
}

const ROLES = ["AdminGeneral", "TorneoAdmin", "Arbitro", "Publico"];

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR");

/** Toggle de licencia (rbac-licencias-torneos-plan.md, §5.3) — checkbox
 * nativo, no un switch custom (Design review, Pass 5: ningún switch
 * custom existe hoy en el repo para un solo uso, mismo criterio que
 * Section 5/CEO — Code Quality de este plan rechaza superficie nueva no
 * justificada). `licenciaMutation` es la instancia de useResourceCrud que
 * pasa UsuariosAdminPage, compartida por todas las filas — un solo
 * `customAction.isPending` global es aceptable acá (no hay dos toggles
 * distintos en vuelo a la vez en la práctica), pero SÍ se deshabilita el
 * control mientras cualquier PATCH de licencia está en curso, para que un
 * doble-click no dispare dos requests (Design review, Pass 2). */
function ToggleLicencia({
  usuario,
  disabled,
  onToggle,
}: {
  usuario: UsuarioRow;
  disabled: boolean;
  onToggle: (usuario: UsuarioRow) => void;
}) {
  return (
    <input
      type="checkbox"
      aria-label={`Licencia activa — ${usuario.username}`}
      checked={usuario.licencia_activa}
      disabled={disabled}
      onChange={() => onToggle(usuario)}
    />
  );
}

/** Gestión de usuarios (roles-3-modulos-plan.md, Fase 4) — mismo patrón
 * exacto que TorneosAdmin.tsx (D1 de Fase 2), reusado sin cambios de
 * fondo: el backend de esta pantalla ya existía completo desde Fase 1/2.
 *
 * rbac-licencias-torneos-plan.md, §5.3: extiende esta página existente
 * (columna de licencia + botón "Gestionar torneos") en vez de
 * reemplazarla — no se toca SimpleResourceAdminPage.tsx ni
 * ResourceTable.tsx, ambos ya exponen los slots necesarios
 * (`columns[].render`, `renderRowExtra`). */
export function UsuariosAdminPage() {
  const { session } = useAuth();
  const [modalUsuario, setModalUsuario] = useState<UsuarioRow | null>(null);

  // Instancia separada de "usuarios" (mismo resourceKey que la de
  // SimpleResourceAdminPage — invalidate() acá también refresca su tabla),
  // enabled: false porque no hace falta un segundo GET de lista, solo
  // customAction (corrección post outside-voice, Eng review hallazgo #2).
  const licenciaMutation = useResourceCrud<UsuarioRow>({
    resourceKey: "usuarios",
    basePath: "/api/v1/usuarios",
    enabled: false,
  });

  function alternarLicencia(usuario: UsuarioRow) {
    licenciaMutation.customAction.mutate({
      path: `/api/v1/usuarios/${usuario.id}/licencia`,
      method: "PATCH",
      body: { activa: !usuario.licencia_activa },
    });
  }

  return (
    <>
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
          {
            // Licencia ANTES que Estado de la cuenta (Design review, Pass
            // 1 — Information Architecture): es la señal de mayor
            // autoridad, jerarquía de validación superior sobre el
            // resto (rbac-licencias-torneos-plan.md, spec §2).
            key: "licencia_activa",
            label: "Licencia",
            render: (r) =>
              // isSelf (mismo criterio que ResourceTable ya usa para
              // ocultar "Dar de baja" en la propia fila): el backend ya
              // bloquea la auto-revocación, esto evita el viaje redondo.
              r.id === session?.id ? (
                <span className="muted" title="No podés revocar tu propia licencia">
                  {r.licencia_activa ? "Activa" : "Inactiva"}
                </span>
              ) : (
                <ToggleLicencia
                  usuario={r}
                  disabled={licenciaMutation.customAction.isPending}
                  onToggle={alternarLicencia}
                />
              ),
          },
          { key: "estado", label: "Estado" },
          { key: "fecha_registro", label: "Registrado", render: (r) => formatearFecha(r.fecha_registro) },
        ]}
        // "Gestionar torneos" (rbac-licencias-torneos-plan.md, §5.3) — solo
        // visible para TorneoAdmin: asignar torneos a un Árbitro o Publico
        // no tiene sentido de negocio (mismo chequeo que ya hace
        // AsignacionTorneoAdminService.set_torneos_asignados del lado del
        // backend, acá evita el viaje redondo).
        renderRowExtra={(r) =>
          r.rol === "TorneoAdmin" ? (
            <button type="button" className="link-button" onClick={() => setModalUsuario(r)}>
              Gestionar torneos
            </button>
          ) : null
        }
      />
      {modalUsuario && (
        <AsignarTorneosModal
          usuarioId={modalUsuario.id}
          nombreUsuario={modalUsuario.nombre}
          onClose={() => setModalUsuario(null)}
        />
      )}
    </>
  );
}
