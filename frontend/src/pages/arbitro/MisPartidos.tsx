import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { ESTADOS_OPERABLES, totalDeRespuesta } from "../../lib/partidosOperables";
import { useAuth } from "../../auth/useAuth";
import { useNavigate } from "react-router-dom";
import { LOCALE, parsearFecha } from "../../lib/fechas";
import { Button } from "../../components/ui/Button";
import { useTituloPagina } from "../../hooks/useTituloPagina";

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
  useTituloPagina("Mis partidos");
  const { session, recargarUsuario } = useAuth();
  const navigate = useNavigate();
  const [reintentando, setReintentando] = useState(false);
  const [reintentoFallido, setReintentoFallido] = useState(false);

  async function reintentar() {
    setReintentando(true);
    setReintentoFallido(!(await recargarUsuario()));
    setReintentando(false);
  }

  const partidosQuery = useQuery({
    queryKey: ["mis-partidos", session?.id],
    queryFn: async () => {
      // TASK-012 (FUN-06): el filtro a Programado/En curso (D6) y el orden
      // los hace el servidor; X-Total-Count dice si quedó algo afuera.
      const { data, error, response } = await api.GET("/api/v1/partidos", {
        params: {
          query: { limit: 200, arbitro_id: session!.id, estado: [...ESTADOS_OPERABLES], orden: "fecha" },
        },
      });
      if (error) throw error;
      return { partidos: data, total: totalDeRespuesta(response) };
    },
    // session.id puede tardar en llegar (se pide a /auth/me después del
    // login, D2) o quedar undefined si esa llamada falló — sin id no hay
    // forma de armar el filtro, así que la query ni se dispara.
    enabled: session?.id !== undefined,
  });

  const activos = partidosQuery.data?.partidos ?? [];
  const total = partidosQuery.data?.total ?? null;

  return (
    <div className="page">
      <h1>Mis partidos</h1>
      {session?.id === undefined && (
        // TASK-036 (FE-05): antes solo decía "volvé a iniciar sesión".
        <div className="aviso-reintento" role="alert">
          <p className="error-text">
            No pudimos confirmar tu usuario, así que todavía no sabemos qué partidos tenés asignados.
          </p>
          {reintentoFallido && <p className="muted">Sigue sin responder. Probá de nuevo en un momento.</p>}
          <Button variante="primario" onClick={reintentar} disabled={reintentando}>
            {reintentando ? "Reintentando..." : "Reintentar"}
          </Button>
        </div>
      )}
      {partidosQuery.isLoading && <p role="status">Cargando tus partidos...</p>}
      {partidosQuery.isError && <p role="alert" className="error-text">No se pudieron cargar tus partidos.</p>}
      {!partidosQuery.isLoading && session?.id !== undefined && activos.length === 0 && (
        <p>No tenés partidos asignados por ahora.</p>
      )}
      {total !== null && total > activos.length && (
        <p className="muted">
          Mostrando {activos.length} de {total} partidos asignados (los más próximos primero).
        </p>
      )}
      <ul className="partidos-list partidos-list--tappable">
        {activos.map((p) => (
          <li key={p.id}>
            <button type="button" onClick={() => navigate(`/control-de-mesa/partido/${p.id}`)}>
              <span className="badge">{p.estado}</span>
              Partido #{p.id} ·{" "}
              {parsearFecha(p.fecha_partido).toLocaleString(LOCALE, { dateStyle: "short", timeStyle: "short" })}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
