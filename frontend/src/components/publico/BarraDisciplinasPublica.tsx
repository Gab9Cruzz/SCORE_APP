import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { iconoDisciplina, inicialDisciplina } from "../iconosDisciplina";

interface DisciplinaConPartidos {
  id: number;
  slug: string;
  nombre: string;
}

interface BarraDisciplinasPublicaProps {
  /** Slug elegido por la URL (D12: `/?deporte=<slug>`) — puede no estar
   * entre `disciplinas` todavía (carrera de datos) o directamente no
   * tener contenido hoy (D5c): en ambos casos su pill se muestra igual,
   * activa. */
  deporteSeleccionado: string | null;
  onSeleccionar: (slug: string | null) => void;
}

/** Barra pública de disciplinas — header global, visible sin sesión
 * (portal-publico-feed-partidos-plan.md, T2.2/T2.3).
 *
 * Se alimenta de `GET /disciplinas/con-partidos` (E-L4/E-M3), NO de
 * `useCatalogo()` — eso traería las 28 disciplinas del catálogo maestro
 * en vez de solo las que tienen partidos hoy (C8). El endpoint resuelve
 * su propia fecha con fallback ±7 días en el servidor, así que esta
 * barra nunca queda vacía por casualidad mientras el feed tenga
 * contenido en algún deporte, y funciona igual en CUALQUIER página
 * (se monta en el NavBar global, no solo en el feed — F18).
 *
 * `staleTime: Infinity` (F17): la barra se "congela" con el contenido de
 * la primera respuesta del `QueryClient` — no se refetchea sola en cada
 * cambio de filtro/fecha, evitando que pills vecinas aparezcan/desaparezcan
 * bajo el dedo del usuario (D5b). El botón de recarga manual del feed
 * (D9) invalida esta key para "descongelarla" a propósito.
 *
 * Con ≤1 disciplina con contenido, la barra no se renderiza (C8): 27
 * pills muertas son peores que ninguna barra.
 */
export function BarraDisciplinasPublica(props: BarraDisciplinasPublicaProps) {
  const { deporteSeleccionado, onSeleccionar } = props;

  const query = useQuery({
    queryKey: ["disciplinas-con-partidos"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/disciplinas/con-partidos", {} as never);
      if (error) throw error;
      return data as DisciplinaConPartidos[];
    },
    staleTime: Infinity,
  });

  const disciplinas = query.data ?? [];

  // D5a: altura reservada desde el primer render — un contenedor vacío
  // durante la carga no debe empujar el feed hacia abajo cuando la
  // respuesta llega justo cuando el usuario va a tocar la primera fila.
  if (query.isLoading) {
    return <div className="barra-disciplinas-publica barra-disciplinas-publica--cargando" aria-hidden="true" />;
  }

  // D5c: la disciplina pedida por URL no está en el sidecar (fuera de la
  // ventana de fallback, o un feriado sin ese deporte) — se muestra igual,
  // activa, en vez de hacer desaparecer el control que el usuario acaba
  // de usar. Sin nombre real disponible, se usa el slug como label.
  const seleccionadaEnLista = disciplinas.some((d) => d.slug === deporteSeleccionado);
  const chips =
    deporteSeleccionado && !seleccionadaEnLista
      ? [...disciplinas, { id: -1, slug: deporteSeleccionado, nombre: deporteSeleccionado }]
      : disciplinas;

  if (chips.length <= 1) return null;

  return (
    <div className="barra-disciplinas-publica" role="tablist" aria-label="Filtrar por deporte">
      {chips.map((d) => {
        const activo = deporteSeleccionado === d.slug;
        const emoji = iconoDisciplina(d.nombre);
        return (
          <button
            key={d.slug}
            type="button"
            role="tab"
            className={`chip-disciplina chip-disciplina--publico${activo ? " chip-disciplina--activo" : ""}`}
            aria-pressed={activo}
            aria-selected={activo}
            onClick={() => onSeleccionar(activo ? null : d.slug)}
          >
            <span className="chip-disciplina__icono" aria-hidden="true">
              {emoji ?? inicialDisciplina(d.nombre)}
            </span>
            {d.nombre}
          </button>
        );
      })}
    </div>
  );
}
