import { Link } from "react-router-dom";
import { Escudo } from "./Escudo";

export interface FilaPartidoData {
  partido_id: number;
  local: { id: number; nombre: string; logo_url: string | null; goles: number };
  visitante: { id: number; nombre: string; logo_url: string | null; goles: number };
  fecha_partido: string;
  estado: "Programado" | "En curso" | "Finalizado" | "Cancelado";
}

const formatearHora = (iso: string) =>
  new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });

/** Fila de partido del feed público (portal-publico-feed-partidos-plan.md,
 * T4.3/D1/D2). Grid explícito de 3 columnas — hora/minuto, equipos (dos
 * renglones apilados), marcador — en vez de una enumeración horizontal
 * de 6 elementos que no entra en 400px con nombres reales ("Deportivo
 * Municipal" vs "Atlético Independiente").
 *
 * D2 — 4 valores de PARTIDOS.Estado (chk_partidos_estado), 3 visibles acá
 * (Cancelado ya viene excluido del feed, ver vw_feed_partidos):
 * Programado muestra la hora sin marcador; En curso muestra un indicador
 * "EN VIVO" con marcador visible (el feed no trae el minuto en vivo —
 * eso exigiría una consulta de cronómetro por fila, fuera de alcance de
 * este endpoint); Finalizado muestra "FIN" con el marcador en tono
 * apagado. Distinguir en curso de finalizado es la razón por la que
 * alguien abre un portal de resultados — no pueden compartir el mismo
 * marcador neutro.
 *
 * Cabecera de torneo y esta fila son elementos clicables HERMANOS
 * (T5.3) — un `<Link>` dentro de otro es HTML inválido y rompe el
 * teclado; `BloqueTorneo` los monta uno al lado del otro, no anidados. */
export function FilaPartido({ partido }: { partido: FilaPartidoData }) {
  const enCurso = partido.estado === "En curso";
  const finalizado = partido.estado === "Finalizado";
  const muestraMarcador = enCurso || finalizado;

  return (
    <Link
      to={`/partidos/${partido.partido_id}`}
      className={`fila-partido${finalizado ? " fila-partido--finalizado" : ""}`}
    >
      <div className="fila-partido__hora">
        {enCurso ? (
          <span className="fila-partido__en-vivo">
            <span className="fila-partido__en-vivo-punto" aria-hidden="true" />
            EN VIVO
          </span>
        ) : finalizado ? (
          "FIN"
        ) : (
          formatearHora(partido.fecha_partido)
        )}
      </div>
      <div className="fila-partido__equipos">
        <div className="fila-partido__equipo">
          <Escudo id={partido.local.id} nombre={partido.local.nombre} logoUrl={partido.local.logo_url} tamano="chico" />
          <span className="fila-partido__nombre-equipo">{partido.local.nombre}</span>
        </div>
        <div className="fila-partido__equipo">
          <Escudo id={partido.visitante.id} nombre={partido.visitante.nombre} logoUrl={partido.visitante.logo_url} tamano="chico" />
          <span className="fila-partido__nombre-equipo">{partido.visitante.nombre}</span>
        </div>
      </div>
      <div className="fila-partido__marcador">
        {muestraMarcador ? (
          <>
            <span>{partido.local.goles}</span>
            <span>{partido.visitante.goles}</span>
          </>
        ) : (
          <span className="muted">—</span>
        )}
      </div>
    </Link>
  );
}
