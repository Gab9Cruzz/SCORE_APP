import { Link } from "react-router-dom";
import { Escudo } from "./Escudo";
import { FilaPartido, type FilaPartidoData } from "./FilaPartido";

export interface BloqueTorneoData {
  id: number;
  nombre: string;
  grupo: string;
  pais: string | null;
  logo_url: string | null;
}

/** Cabecera de torneo (logo o iniciales, nombre de competición, país) +
 * lista de filas de partido (portal-publico-feed-partidos-plan.md, T4.2).
 *
 * T5.3: cabecera y filas son elementos clicables HERMANOS, no anidados —
 * un `<Link>` (o `<button>`) dentro de otro es HTML inválido y rompe el
 * teclado. La cabecera entera es un `<Link>` a `/torneos/:id` (T5.3:
 * "clic en la cabecera del torneo -> /torneos/:torneoId"), cada fila es
 * su propio `<Link>` a `/partidos/:id` — ninguno contiene al otro. */
export function BloqueTorneo({ torneo, partidos }: { torneo: BloqueTorneoData; partidos: FilaPartidoData[] }) {
  return (
    <section className="bloque-torneo">
      <Link to={`/torneos/${torneo.id}`} className="bloque-torneo__header">
        <Escudo id={torneo.id} nombre={torneo.grupo} logoUrl={torneo.logo_url} tamano="mediano" />
        <div>
          <div className="bloque-torneo__nombre">{torneo.grupo}</div>
          {torneo.pais && <div className="muted bloque-torneo__pais">{torneo.pais}</div>}
        </div>
      </Link>
      <div className="bloque-torneo__filas">
        {partidos.map((p) => (
          <FilaPartido key={p.partido_id} partido={p} />
        ))}
      </div>
    </section>
  );
}
