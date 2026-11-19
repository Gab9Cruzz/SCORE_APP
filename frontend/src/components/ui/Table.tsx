import type { ReactNode } from "react";

interface TableProps {
  /** Títulos de columna. `null` deja la celda de encabezado vacía a la
   * vista pero con un nombre para lectores de pantalla ("Acciones"). */
  encabezados: (ReactNode | null)[];
  /** Las filas (`<tr>`) del cuerpo. */
  children: ReactNode;
  cargando?: boolean;
  /** `true` muestra el mensaje genérico; un string, ese texto. */
  error?: boolean | string;
  vacio?: boolean;
  mensajeVacio?: ReactNode;
  /** Nombre accesible de la tabla cuando la página tiene más de una. */
  etiqueta?: string;
}

/** Tabla base (TASK-034): los tres estados de DESIGN.md (carga, error,
 * vacío) con el mismo texto en todas las pantallas, y el contenedor con
 * scroll horizontal propio para que una tabla ancha no desborde la
 * página en el celular. */
export function Table({
  encabezados,
  children,
  cargando = false,
  error = false,
  vacio = false,
  mensajeVacio = "No hay elementos.",
  etiqueta,
}: TableProps) {
  if (cargando) return <p>Cargando...</p>;
  if (error) return <p className="error-text">{typeof error === "string" ? error : "No se pudo cargar la lista."}</p>;
  if (vacio) return <p>{mensajeVacio}</p>;

  return (
    <div className="table-scroll tabla">
      <table aria-label={etiqueta}>
        <thead>
          <tr>
            {encabezados.map((e, i) => (
              <th key={i}>{e ?? <span className="sr-only">Acciones</span>}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
