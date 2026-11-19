import type { ReactNode } from "react";
import { Estado } from "./Estado";

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
  if (cargando) return <Estado tipo="cargando" />;
  if (error) return <Estado tipo="error">{typeof error === "string" ? error : undefined}</Estado>;
  if (vacio) return <Estado tipo="vacio">{mensajeVacio}</Estado>;

  return (
    <div className="table-scroll">
      <table>
        {etiqueta && <caption className="sr-only">{etiqueta}</caption>}
        <thead>
          <tr>
            {encabezados.map((e, i) => (
              <th key={i} scope="col">
                {e ?? <span className="sr-only">Acciones</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
