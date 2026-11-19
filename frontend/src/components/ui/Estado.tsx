import type { ReactNode } from "react";

const POR_DEFECTO = {
  cargando: "Cargando...",
  error: "No se pudo cargar la lista.",
  vacio: "No hay elementos.",
} as const;

/** Estados de una lista o bloque que carga datos (DESIGN.md, "Estados";
 * TASK-037, WCAG 4.1.3). Carga se anuncia como `status` (cortés, no
 * interrumpe) y error como `alert`; antes eran párrafos mudos para un
 * lector de pantalla. Vacío no se anuncia: es el contenido. */
export function Estado({ tipo, children }: { tipo: "cargando" | "error" | "vacio"; children?: ReactNode }) {
  const texto = children ?? POR_DEFECTO[tipo];
  if (tipo === "cargando") return <p role="status">{texto}</p>;
  if (tipo === "error")
    return (
      <p role="alert" className="error-text">
        {texto}
      </p>
    );
  return <p>{texto}</p>;
}
