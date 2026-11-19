import { Button } from "./Button";

export interface PropsPaginacion {
  /** Página actual, desde 0. */
  pagina: number;
  tamano: number;
  /** Total de filas según `X-Total-Count`; `null` si el servidor no lo dio. */
  total: number | null;
  /** Filas que trajo la página actual. */
  filasEnPagina: number;
  onCambiar: (pagina: number) => void;
  /** Mientras llega la página pedida, los botones no repiten el pedido. */
  cargando?: boolean;
}

const numero = new Intl.NumberFormat("es");

/** Pie de tabla "1–50 de 312" con Anterior y Siguiente (TASK-039).
 *
 * Sin total (un servidor que no manda la cabecera) igual se puede avanzar
 * mientras la página llegue llena; solo falta el "de N". Con una sola
 * página no se muestra: un "1–7 de 7" sin botones no le dice nada a nadie. */
export function Paginacion({ pagina, tamano, total, filasEnPagina, onCambiar, cargando = false }: PropsPaginacion) {
  const desde = filasEnPagina === 0 ? 0 : pagina * tamano + 1;
  const hasta = pagina * tamano + filasEnPagina;
  const haySiguiente = total !== null ? hasta < total : filasEnPagina === tamano;
  const hayAnterior = pagina > 0;
  if (!hayAnterior && !haySiguiente) return null;

  return (
    <nav className="paginacion" aria-label="Paginación">
      <p className="paginacion__rango" aria-live="polite">
        {numero.format(desde)}–{numero.format(hasta)}
        {total !== null && <> de {numero.format(total)}</>}
      </p>
      <Button disabled={!hayAnterior || cargando} onClick={() => onCambiar(pagina - 1)}>
        ← Anterior
      </Button>
      <Button disabled={!haySiguiente || cargando} onClick={() => onCambiar(pagina + 1)}>
        Siguiente →
      </Button>
    </nav>
  );
}
