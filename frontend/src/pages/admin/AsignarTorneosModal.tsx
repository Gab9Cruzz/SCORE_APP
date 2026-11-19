import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useResourceCrud } from "../../hooks/useResourceCrud";

interface TorneoRow {
  id: number;
  nombre: string;
  estado: string;
}

interface AsignarTorneosModalProps {
  usuarioId: number;
  nombreUsuario: string;
  onClose: () => void;
}

/** Modal "Gestionar torneos" del panel de Admin General
 * (rbac-licencias-torneos-plan.md, §5.3) — mismo patrón visual/estructural
 * que ModalGestionarPlantilla/ModalPerfilJugador/ModalAgregarInscripcion
 * (`modal-overlay`/`modal-panel`, `useResourceCrud.customAction` como
 * escape hatch para el PATCH que no es un update plano). Lista de
 * checkboxes nativa, sin librería de multiselect — no hay ninguna
 * instalada en el proyecto y no hace falta una para esto (§1 del plan).
 *
 * Focus trap + Escape (Design review, Pass 6 — T12): era el único modal
 * que los tenía; TASK-034 los extrajo a components/ui/Modal.tsx, que es
 * lo que usa ahora. */
export function AsignarTorneosModal({ usuarioId, nombreUsuario, onClose }: AsignarTorneosModalProps) {
  const torneos = useResourceCrud<TorneoRow>({
    resourceKey: "torneos",
    basePath: "/api/v1/torneos",
    listParams: { estado: "Activo" },
  });
  // Instancia separada de useResourceCrud sobre "usuarios" (mismo
  // resourceKey que la de SimpleResourceAdminPage, así que invalidate()
  // acá también refresca la tabla de UsuariosAdmin.tsx) — enabled: false
  // porque este modal no necesita el listQuery de usuarios, solo
  // customAction (corrección post outside-voice, Eng review hallazgo #2:
  // UsuariosAdminPage no tiene su propia instancia expuesta por
  // SimpleResourceAdminPage).
  const usuarios = useResourceCrud<{ id: number }>({
    resourceKey: "usuarios",
    basePath: "/api/v1/usuarios",
    enabled: false,
  });

  const asignadosQuery = useQuery({
    queryKey: ["usuarios", usuarioId, "torneos"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/usuarios/{usuario_id}/torneos", {
        params: { path: { usuario_id: usuarioId } },
      });
      if (error) throw error;
      return data;
    },
  });

  // `null` = "todavía sin ediciones locales" — se deriva directo del
  // último fetch en cada render (sin useEffect: el checklist_item's Pass 2
  // ya cubre loading/error, esto es solo evitar el anti-patrón de
  // "setState sincrónico en un efecto" que rechazó oxlint). En cuanto el
  // usuario tilda/destilda algo, seleccionados deja de ser null y las
  // ediciones locales divergen del servidor a propósito hasta Guardar.
  const [seleccionados, setSeleccionados] = useState<Set<number> | null>(null);
  const seleccionadosActual = seleccionados ?? new Set(asignadosQuery.data ?? []);
  const [error, setError] = useState<string | null>(null);

  function alternar(torneoId: number) {
    const next = new Set(seleccionadosActual);
    if (next.has(torneoId)) next.delete(torneoId);
    else next.add(torneoId);
    setSeleccionados(next);
  }

  function guardar() {
    setError(null);
    usuarios.customAction.mutate(
      {
        path: `/api/v1/usuarios/${usuarioId}/torneos`,
        method: "PATCH",
        body: { torneo_ids: Array.from(seleccionadosActual) },
      },
      {
        onSuccess: onClose,
        onError: (e) => setError(apiErrorMessage(e, "No se pudieron guardar los torneos asignados.")),
      },
    );
  }

  const cargando = torneos.listQuery.isLoading || asignadosQuery.isLoading;
  const errorCarga = torneos.listQuery.isError || asignadosQuery.isError;

  return (
    <Modal titulo={`Gestionar torneos — ${nombreUsuario}`} onCerrar={onClose}>
      {cargando && <p>Cargando...</p>}
      {!cargando && errorCarga && <p className="error-text">No se pudo cargar la lista.</p>}
      {/* Estado vacío explícito (Design review, Pass 2 — T13): sin esto,
            un sistema sin torneos activos mostraba una lista en blanco sin
            explicación. */}
      {!cargando && !errorCarga && (torneos.listQuery.data ?? []).length === 0 && (
        <p className="muted">No hay torneos activos para asignar.</p>
      )}
      {!cargando && !errorCarga && (torneos.listQuery.data ?? []).length > 0 && (
        <div className="modal-panel__checklist">
          {(torneos.listQuery.data ?? []).map((t) => (
            <label key={t.id} className="checklist-item">
              <input type="checkbox" checked={seleccionadosActual.has(t.id)} onChange={() => alternar(t.id)} />
              {t.nombre}
            </label>
          ))}
        </div>
      )}

      {error && <p className="error-text">{error}</p>}

      <div className="resource-form__actions">
        <Button variante="enlace" onClick={onClose}>
          Cancelar
        </Button>
        <Button
          variante="primario"
          disabled={cargando || errorCarga || usuarios.customAction.isPending}
          onClick={guardar}
        >
          {usuarios.customAction.isPending ? "Guardando..." : "Guardar"}
        </Button>
      </div>
    </Modal>
  );
}
