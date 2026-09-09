import { useState } from "react";

/** Walkover ("no se presentó") — mudado desde `PartidosDelTorneo.tsx`
 * (Sección 16 del plan): mismo botón chico inline que tenía ahí, ahora
 * junto a "Cargar resultado directo" — ambas cierran el partido sin
 * cronómetro en vivo, así que viven en el mismo lugar. El backend
 * re-valida todo igual (estado, habilitación de Liga/grupos, etc.). */
export function AccionWalkoverMesa(props: {
  equipoLocalId: number;
  equipoVisitanteId: number;
  nombreLocal: string;
  nombreVisitante: string;
  onMarcar: (equipoAusenteId: number) => void;
  marcando: boolean;
}) {
  const { equipoLocalId, equipoVisitanteId, nombreLocal, nombreVisitante, onMarcar, marcando } = props;
  const [abierto, setAbierto] = useState(false);

  if (!abierto) {
    return (
      <button type="button" className="link-button" onClick={() => setAbierto(true)}>
        Walkover
      </button>
    );
  }

  return (
    <span className="accion-walkover">
      <span className="muted">¿Quién no se presentó?</span>
      <button
        type="button"
        disabled={marcando}
        onClick={() => {
          onMarcar(equipoLocalId);
          setAbierto(false);
        }}
      >
        {nombreLocal}
      </button>
      <button
        type="button"
        disabled={marcando}
        onClick={() => {
          onMarcar(equipoVisitanteId);
          setAbierto(false);
        }}
      >
        {nombreVisitante}
      </button>
      <button type="button" className="link-button" onClick={() => setAbierto(false)}>
        Cancelar
      </button>
    </span>
  );
}
