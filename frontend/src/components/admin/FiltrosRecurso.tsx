export interface FiltroSelectOption {
  value: string;
  label: string;
}

export interface FiltroSelect {
  name: string;
  label: string;
  value: string;
  options: FiltroSelectOption[];
  /** Texto de la opción "sin filtrar". Default: "Todas". */
  labelTodas?: string;
  onChange: (value: string) => void;
}

interface FiltrosRecursoProps {
  selects: FiltroSelect[];
  busqueda?: {
    value: string;
    placeholder?: string;
    label: string;
    onChange: (value: string) => void;
  };
  /** Se muestra solo si hay al menos un filtro aplicado — el botón que
   * saca al admin del estado "filtré y no veo nada". */
  hayFiltrosAplicados: boolean;
  onLimpiar: () => void;
}

/** Barra de filtros genérica para una grilla de recurso
 * (equipos-disciplina-navegacion-plan.md, Fase 2 parte A: "componentizada
 * para crecer"). Es tonta a propósito — no sabe de la API ni del recurso
 * que filtra: recibe selects ya armados y devuelve el string elegido. Un
 * eje de filtro nuevo es una entrada más en el array `selects`, no un
 * cambio acá adentro.
 *
 * Los valores viajan como string (no como number) porque eso es lo que da
 * un `<select>`; quien lo consume convierte a id si le hace falta. La
 * alternativa — un select genérico con valores tipados — obligaría a
 * parametrizar el componente entero por el tipo de cada filtro para
 * ahorrar un `Number()` en el llamador. */
export function FiltrosRecurso(props: FiltrosRecursoProps) {
  const { selects, busqueda, hayFiltrosAplicados, onLimpiar } = props;

  return (
    <div className="filtros-recurso">
      {selects.map((s) => (
        <label key={s.name}>
          {s.label}
          <select value={s.value} onChange={(e) => s.onChange(e.target.value)}>
            <option value="">{s.labelTodas ?? "Todas"}</option>
            {s.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      ))}
      {busqueda && (
        <input
          type="search"
          aria-label={busqueda.label}
          placeholder={busqueda.placeholder ?? "Buscar..."}
          value={busqueda.value}
          onChange={(e) => busqueda.onChange(e.target.value)}
        />
      )}
      {hayFiltrosAplicados && (
        <button type="button" className="link-button" onClick={onLimpiar}>
          Limpiar filtros
        </button>
      )}
    </div>
  );
}
