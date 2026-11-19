import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Button } from "../ui/Button";
import { Paginacion, type PropsPaginacion } from "../ui/Paginacion";
import { Table } from "../ui/Table";

export interface ResourceTableColumn<T> {
  key: string;
  label: string;
  /** Default: String(row[key]). */
  render?: (row: T) => ReactNode;
}

interface RowConEstado {
  id: number;
  estado?: string;
}

/** Cómo se nombra una fila cuando la pantalla no da `nombreFila`: el
 * primer campo que tenga entre nombre/username, o el id. Se usa en la
 * confirmación de baja y en el nombre accesible de los botones. */
function nombrePorDefecto(row: RowConEstado): string {
  const r = row as unknown as Record<string, unknown>;
  for (const campo of ["nombre", "username"]) {
    if (typeof r[campo] === "string" && r[campo] !== "") return r[campo] as string;
  }
  return `#${row.id}`;
}

interface ResourceTableProps<T extends RowConEstado> {
  rows: T[];
  columns: ResourceTableColumn<T>[];
  isLoading: boolean;
  isError: boolean;
  emptyMessage?: string;
  onSelect?: (row: T) => void;
  onSoftDelete?: (row: T) => void;
  softDeleteLabel?: string;
  softDeletePending?: boolean;
  /** Estados que ya están de baja — no se les muestra el botón de borrar
   * de nuevo (Inactivo/Cancelado según el recurso). Default: ["Inactivo", "Cancelado"]. */
  estadosDeBaja?: string[];
  /** roles-3-modulos-plan.md, Fase 4, D2a: oculta el botón de baja para
   * la fila que es el usuario logueado — cierra preventivamente el click
   * más probable de auto-lockout (el backend ya lo rechaza con 403, esto
   * evita el viaje redondo). Opcional: solo lo usa UsuariosAdmin.tsx. */
  isSelf?: (row: T) => boolean;
  /** Gate adicional para el botón de baja, más allá de estadosDeBaja/isSelf
   * — ej. Traspasos: "Anular" desaparece si el club destino ya jugó desde
   * el traspaso (fixes-datos-traspasos-control-mesa-plan.md), sin que eso
   * dependa del estado de la fila. Default: siempre permitido. */
  puedeSoftDelete?: (row: T) => boolean;
  /** Acciones extra por fila, además de Editar/Dar de baja — ej. un link
   * "Ver perfil" (equipos-jugadores-plan.md, Fase 2, Etapa D). Se
   * renderiza en la misma celda de acciones. */
  extraActions?: (row: T) => ReactNode;
  /** TASK-038 (UX-06): texto de la confirmación de baja, para que cada
   * pantalla explique la consecuencia ("Se cancelará la inscripción; sus
   * jugadores quedarán libres"). Default: "¿<softDeleteLabel> <nombre>?". */
  confirmacion?: (row: T) => string;
  /** TASK-037 (UX-04): nombre de la fila para lectores de pantalla — los
   * botones se anuncian "Editar Halcones FC", no diez "Editar" iguales.
   * Default: `nombre`, `username` o `#id`. */
  nombreFila?: (row: T) => string;
  /** Nombre de la tabla (caption oculto). */
  etiqueta?: string;
  /** TASK-039: pie "1–50 de 312" con anterior y siguiente. */
  paginacion?: Omit<PropsPaginacion, "filasEnPagina">;
}

/** Tabla genérica de listado para el módulo Torneo Admin
 * (roles-3-modulos-plan.md, Fase 2, D1). Comparte el mismo vocabulario de
 * loading/error/vacío que ControlDeMesa.tsx y Dashboard.tsx, no inventa
 * un patrón nuevo. */
export function ResourceTable<T extends RowConEstado>(props: ResourceTableProps<T>) {
  const {
    rows,
    columns,
    isLoading,
    isError,
    emptyMessage = "No hay elementos.",
    onSelect,
    onSoftDelete,
    softDeleteLabel = "Dar de baja",
    softDeletePending = false,
    estadosDeBaja = ["Inactivo", "Cancelado"],
    isSelf,
    puedeSoftDelete,
    extraActions,
    confirmacion,
    nombreFila = nombrePorDefecto,
    etiqueta,
    paginacion,
  } = props;

  // TASK-038 (UX-06): la baja no se ejecuta con un clic. El botón abre una
  // confirmación en la misma fila; el foco va a "Volver" (la opción segura)
  // y Escape la cierra devolviendo el foco al botón que la abrió.
  const [confirmandoId, setConfirmandoId] = useState<number | null>(null);
  const volverRef = useRef<HTMLButtonElement>(null);
  const disparadores = useRef(new Map<number, HTMLButtonElement>());
  const devolverFocoA = useRef<number | null>(null);

  useEffect(() => {
    if (confirmandoId != null) {
      volverRef.current?.focus();
    } else if (devolverFocoA.current != null) {
      disparadores.current.get(devolverFocoA.current)?.focus();
      devolverFocoA.current = null;
    }
  }, [confirmandoId]);

  function cerrarConfirmacion(id: number) {
    devolverFocoA.current = id;
    setConfirmandoId(null);
  }

  function alPresionarTecla(e: KeyboardEvent, id: number) {
    if (e.key === "Escape") {
      e.stopPropagation();
      cerrarConfirmacion(id);
    }
  }

  const tieneAcciones = Boolean(onSelect || onSoftDelete || extraActions);
  const encabezados: (ReactNode | null)[] = columns.map((c) => c.label);
  if (tieneAcciones) encabezados.push(null);

  return (
    <>
      <Table
        encabezados={encabezados}
        cargando={isLoading}
        error={isError}
        vacio={rows.length === 0}
        mensajeVacio={emptyMessage}
        etiqueta={etiqueta}
      >
        {rows.map((row) => (
          <tr key={row.id}>
            {columns.map((c) => (
              <td key={c.key}>{c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "")}</td>
            ))}
            {tieneAcciones && confirmandoId === row.id && onSoftDelete && (
              <td className="table-actions table-actions--confirmando" onKeyDown={(e) => alPresionarTecla(e, row.id)}>
                <span role="alert" className="table-actions__pregunta">
                  {confirmacion ? confirmacion(row) : `¿${softDeleteLabel} «${nombreFila(row)}»?`}
                </span>
                <Button
                  variante="peligro"
                  disabled={softDeletePending}
                  onClick={() => {
                    setConfirmandoId(null);
                    onSoftDelete(row);
                  }}
                >
                  Confirmar
                </Button>
                <Button ref={volverRef} onClick={() => cerrarConfirmacion(row.id)}>
                  Volver
                </Button>
              </td>
            )}
            {tieneAcciones && confirmandoId !== row.id && (
              <td className="table-actions">
                {onSelect && (
                  <Button aria-label={`Editar ${nombreFila(row)}`} onClick={() => onSelect(row)}>
                    Editar
                  </Button>
                )}
                {onSoftDelete &&
                  !estadosDeBaja.includes(row.estado ?? "") &&
                  !isSelf?.(row) &&
                  (puedeSoftDelete?.(row) ?? true) && (
                    <Button
                      aria-label={`${softDeleteLabel} ${nombreFila(row)}`}
                      ref={(el) => {
                        if (el) disparadores.current.set(row.id, el);
                        else disparadores.current.delete(row.id);
                      }}
                      onClick={() => setConfirmandoId(row.id)}
                      disabled={softDeletePending}
                    >
                      {softDeleteLabel}
                    </Button>
                  )}
                {extraActions?.(row)}
              </td>
            )}
          </tr>
        ))}
      </Table>
      {paginacion && !isLoading && !isError && <Paginacion {...paginacion} filasEnPagina={rows.length} />}
    </>
  );
}
