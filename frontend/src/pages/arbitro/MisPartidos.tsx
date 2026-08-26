import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { MesaPanel } from "../ControlDeMesa";

/** Landing del módulo Árbitro (roles-3-modulos-plan.md, Fase 3).
 *
 * Ruta única `/arbitro`, sin layout/Outlet (D3) — hoy es la única
 * pantalla del módulo. Filtra a `GET /partidos?arbitro_id=session.id`
 * (D1, server-side) y, del lado del cliente, a Programado/En curso (D6 —
 * mismo patrón que `ControlDeMesaPage`; se consideró y se rechazó
 * agregar además un guard de estado dentro de `MesaPanel`, ver Failure
 * modes de la sección de Fase 3 en el plan). Al elegir un partido,
 * reusa `MesaPanel` tal cual (D4) — sin duplicar la carga de eventos.
 */
export function MisPartidosPage() {
  const { session } = useAuth();
  const [partidoId, setPartidoId] = useState<number | null>(null);

  const partidosQuery = useQuery({
    queryKey: ["mis-partidos", session?.id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos", {
        params: { query: { limit: 100, arbitro_id: session!.id } },
      });
      if (error) throw error;
      return data;
    },
    // session.id puede tardar en llegar (se pide a /auth/me después del
    // login, D2) o quedar undefined si esa llamada falló — sin id no hay
    // forma de armar el filtro, así que la query ni se dispara.
    enabled: session?.id !== undefined,
  });

  const activos = (partidosQuery.data ?? []).filter(
    (p) => p.estado === "Programado" || p.estado === "En curso",
  );

  if (partidoId !== null) {
    return <MesaPanel partidoId={partidoId} onVolver={() => setPartidoId(null)} />;
  }

  return (
    <div className="page">
      <h1>Mis partidos</h1>
      {session?.id === undefined && (
        <p className="error-text">
          No pudimos confirmar tu usuario. Volvé a iniciar sesión para ver tus partidos asignados.
        </p>
      )}
      {partidosQuery.isLoading && <p>Cargando tus partidos...</p>}
      {partidosQuery.isError && <p className="error-text">No se pudieron cargar tus partidos.</p>}
      {!partidosQuery.isLoading && session?.id !== undefined && activos.length === 0 && (
        <p>No tenés partidos asignados por ahora.</p>
      )}
      <ul className="partidos-list partidos-list--tappable">
        {activos.map((p) => (
          <li key={p.id}>
            <button type="button" onClick={() => setPartidoId(p.id)}>
              <span className="badge">{p.estado}</span>
              Partido #{p.id} ·{" "}
              {new Date(p.fecha_partido).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
