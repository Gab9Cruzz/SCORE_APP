import { useMutation } from "@tanstack/react-query";
import { useId, useState } from "react";
import { api, apiErrorMessage } from "../../../api/client";

/** Resolver un reclamo sobre un partido de llave ya cerrado (TASK-009).
 *
 * Decisión del propietario: cuando un equipo ya avanzó, el resultado no se
 * cambia anulando eventos; si prospera un reclamo, se da a favor del equipo
 * que perdió y ese equipo pasa a avanzar. El marcador no cambia. El
 * servidor valida todo (que sea a favor del que perdió, que el partido
 * siguiente no haya empezado); acá solo se junta el equipo y el motivo y se
 * muestra el rechazo tal como viene. */
export function ReclamoPartido({
  partidoId,
  equipos,
  onResuelto,
}: {
  partidoId: number;
  equipos: { id: number; nombre: string }[];
  onResuelto: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [equipoId, setEquipoId] = useState<number | null>(null);
  const [motivo, setMotivo] = useState("");
  const idEquipo = useId();
  const idMotivo = useId();

  const resolver = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/partidos/{partido_id}/reclamo", {
        params: { path: { partido_id: partidoId } },
        body: { equipo_id: equipoId as number, motivo: motivo.trim() },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      setAbierto(false);
      onResuelto();
    },
  });

  if (!abierto) {
    return (
      <button type="button" className="reclamo-partido__abrir" onClick={() => setAbierto(true)}>
        Resolver reclamo
      </button>
    );
  }

  const puedeConfirmar = equipoId !== null && motivo.trim() !== "" && !resolver.isPending;
  return (
    <form
      className="reclamo-partido"
      onSubmit={(e) => {
        e.preventDefault();
        if (puedeConfirmar) resolver.mutate();
      }}
    >
      <p className="muted">
        El equipo elegido pasa a avanzar en lugar del que ganó en cancha. El marcador no cambia.
      </p>
      <label htmlFor={idEquipo}>A favor de</label>
      <select
        id={idEquipo}
        value={equipoId ?? ""}
        onChange={(e) => setEquipoId(e.target.value === "" ? null : Number(e.target.value))}
      >
        <option value="">Elegí el equipo</option>
        {equipos.map((eq) => (
          <option key={eq.id} value={eq.id}>
            {eq.nombre}
          </option>
        ))}
      </select>
      <label htmlFor={idMotivo}>Motivo</label>
      <textarea id={idMotivo} value={motivo} maxLength={500} onChange={(e) => setMotivo(e.target.value)} />
      {resolver.isError && (
        <p className="error-text" role="alert">
          {apiErrorMessage(resolver.error, "No se pudo resolver el reclamo.")}
        </p>
      )}
      <div className="reclamo-partido__acciones">
        <button type="submit" disabled={!puedeConfirmar}>
          Confirmar reclamo
        </button>
        <button type="button" onClick={() => setAbierto(false)}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
