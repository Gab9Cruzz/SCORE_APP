import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { BloqueTorneo, type BloqueTorneoData } from "../../components/publico/BloqueTorneo";
import type { FilaPartidoData } from "../../components/publico/FilaPartido";

interface FeedResponse {
  fecha_pedida: string;
  fecha_efectiva: string;
  total_disponible: number;
  partidos: (FilaPartidoData & { torneo: BloqueTorneoData; disciplina_id: number; disciplina: string })[];
}

const LIMITE_INICIAL = 60;

function sumarDias(fechaISO: string, dias: number): string {
  const fecha = new Date(fechaISO + "T00:00:00");
  fecha.setDate(fecha.getDate() + dias);
  return fecha.toISOString().slice(0, 10);
}

function formatearFechaLarga(fechaISO: string): string {
  const fecha = new Date(fechaISO + "T00:00:00");
  const texto = fecha.toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long" });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function nombreDeporte(slug: string): string {
  return slug.charAt(0).toUpperCase() + slug.slice(1).replace(/-/g, " ");
}

/** Home pública — Feed de Partidos del Día (portal-publico-feed-partidos-
 * plan.md, T4.1-T4.7). Consume GET /partidos/feed (R2), agrupa las filas
 * planas por torneo en el cliente (T4.4) preservando el orden del
 * backend (torneo_grupo → torneo → fecha → id, E-M6 — los partidos de un
 * mismo torneo ya llegan contiguos).
 *
 * E-G3 (Final Gate, supersede C1/D3): sin `fecha` en la URL, el feed abre
 * DIRECTO en la próxima jornada con partidos — no hay estado intermedio
 * de "hoy vacío + disculpa". Por eso la cabecera SIEMPRE rotula la fecha
 * real que muestra (nunca "Hoy" a secas, D10/E-G3b): un martes podría
 * estar mostrando el domingo pasado. El fallback (`ventana_fallback_dias`)
 * solo aplica quando no hay `fecha` explícita en la URL — navegar con
 * las flechas manda `ventana_fallback_dias=0` (D3): ese día se ve tal
 * cual, con su propio empty state si no tiene partidos.
 */
export function FeedPartidosPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const deporteSlug = searchParams.get("deporte");
  const fechaUrl = searchParams.get("fecha");

  const query = useQuery({
    queryKey: ["feed-partidos", deporteSlug, fechaUrl],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/feed", {
        params: {
          query: {
            deporte: deporteSlug ?? undefined,
            fecha: fechaUrl ?? undefined,
            limit: LIMITE_INICIAL,
            // D3: el fallback de ±7 días solo corre en la carga inicial
            // (sin `fecha` en la URL) — navegar explícito no cae a otra.
            ventana_fallback_dias: fechaUrl ? 0 : 7,
          },
        },
      } as never);
      if (error) throw error;
      return data as FeedResponse;
    },
  });

  const bloques = useMemo(() => {
    const orden: number[] = [];
    const mapa = new Map<number, { torneo: BloqueTorneoData; partidos: FilaPartidoData[] }>();
    for (const p of query.data?.partidos ?? []) {
      if (!mapa.has(p.torneo.id)) {
        orden.push(p.torneo.id);
        mapa.set(p.torneo.id, { torneo: p.torneo, partidos: [] });
      }
      mapa.get(p.torneo.id)!.partidos.push(p);
    }
    return orden.map((id) => mapa.get(id)!);
  }, [query.data]);

  function navegarDia(delta: number) {
    const base = query.data?.fecha_efectiva ?? new Date().toISOString().slice(0, 10);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("fecha", sumarDias(base, delta));
      return next;
    });
  }

  function irADisciplina(slug: string | null) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (slug) next.set("deporte", slug);
      else next.delete("deporte");
      next.delete("fecha");
      return next;
    });
  }

  const actualizado = new Date().toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="page publico feed-partidos">
      <div className="feed-partidos__toolbar">
        <div className="feed-partidos__selector-fecha">
          <button type="button" className="link-button" onClick={() => navegarDia(-1)} aria-label="Día anterior">
            ←
          </button>
          <span className="feed-partidos__fecha-label">
            {query.data ? formatearFechaLarga(query.data.fecha_efectiva) : " "}
          </span>
          <button type="button" className="link-button" onClick={() => navegarDia(1)} aria-label="Día siguiente">
            →
          </button>
        </div>
        {/* D9: el detalle de partido refresca cada 5s y este feed no
            (C14) — sin este rótulo, alguien que ve un marcador moverse
            ahí y vuelve acá concluye que el feed está roto. */}
        <div className="feed-partidos__frescura muted">
          Actualizado {actualizado}{" "}
          <button type="button" className="link-button" onClick={() => query.refetch()}>
            Recargar
          </button>
        </div>
      </div>

      {query.isLoading && <EsqueletoFeed />}
      {query.isError && <p className="error-text">{apiErrorMessage(query.error)}</p>}

      {query.data && query.data.partidos.length === 0 && (
        <p className="muted feed-partidos__vacio">
          {deporteSlug
            ? `No hay partidos de ${nombreDeporte(deporteSlug)} esta semana.`
            : "No hay partidos programados esta semana."}{" "}
          {deporteSlug && (
            <button type="button" className="link-button" onClick={() => irADisciplina(null)}>
              Ver todos los deportes
            </button>
          )}
        </p>
      )}

      {bloques.map(({ torneo, partidos }) => (
        <BloqueTorneo key={torneo.id} torneo={torneo} partidos={partidos} />
      ))}

      {/* D4/F7: un campo del envelope que ningún componente pinta es un
          feed que termina en seco sin avisar. */}
      {query.data && query.data.partidos.length > 0 && query.data.partidos.length < query.data.total_disponible && (
        <p className="muted feed-partidos__truncado">
          Mostrando los primeros {query.data.partidos.length} de {query.data.total_disponible} partidos.
        </p>
      )}
    </div>
  );
}

/** D10: skeleton con la misma métrica del grid de D1 (no un spinner
 * genérico — el feed tiene forma conocida). */
function EsqueletoFeed() {
  return (
    <div className="feed-partidos__esqueleto" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div key={i} className="feed-partidos__esqueleto-fila" />
      ))}
    </div>
  );
}
