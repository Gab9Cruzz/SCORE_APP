import type { ReactNode } from "react";

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
  } = props;

  if (isLoading) return <p>Cargando...</p>;
  if (isError) return <p className="error-text">No se pudo cargar la lista.</p>;
  if (rows.length === 0) return <p>{emptyMessage}</p>;

  const tieneAcciones = Boolean(onSelect || onSoftDelete);

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
            {tieneAcciones && <th></th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "")}</td>
              ))}
              {tieneAcciones && (
                <td className="table-actions">
                  {onSelect && (
                    <button type="button" onClick={() => onSelect(row)}>
                      Editar
                    </button>
                  )}
                  {onSoftDelete && !estadosDeBaja.includes(row.estado ?? "") && (
                    <button type="button" onClick={() => onSoftDelete(row)} disabled={softDeletePending}>
                      {softDeleteLabel}
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
